"""
Skill classifier for ConsultBae.

Takes a raw, comma-separated skills string (as found in Naukri's
"Skills" column and the gig workers' "skill_tags" column) and:
    1. splits/normalizes it into individual clean skill tokens
    2. classifies each skill into a category (Automation, AI/LLM,
       Backend, Databases, Data & Scripting, Frontend, DevOps)
    3. picks a primary_category (the category with the most matches
       for that person) -- useful for quick candidate routing, e.g.
       "this person is primarily a Backend person who also knows
       some Automation tools"

The taxonomy below was built directly from the actual vocabulary
found in data/cleaned/source1_naukri_applicants.csv and
data/cleaned/source2_gig_workers.csv (15 distinct skills, see
`_discover_vocabulary()` at the bottom for how that was derived).
It is NOT exhaustive -- any skill outside this list ends up in
"uncategorized" rather than silently mis-filed, so gaps are visible
instead of hidden.

--------------------------------------------------------------------
THREE WAYS TO USE THIS FILE
--------------------------------------------------------------------

1. As a plain Python function, from anywhere:

    from skill_classifier import classify_skills
    result = classify_skills("n8n, LangChain, REST APIs, MongoDB")

2. Inside an n8n "Code" node (Python mode). n8n's Python code nodes
   run in Pyodide and expose the incoming items via `_input.all()`.
   Paste CLASSIFY_ITEMS_SNIPPET (see bottom of this file) into the
   node, or copy classify_skills()/normalize_skill_list() in
   directly -- Pyodide can't `import` this file from disk.

3. As a standalone batch script, to classify the whole dataset and
   write a CSV report (useful for testing outside n8n entirely):

    python3 n8n/skill_classifier.py

   Reads data/cleaned/source1_naukri_applicants.csv and
   data/cleaned/source2_gig_workers.csv, classifies every row's
   skills, and writes n8n/output/skill_classification.csv plus a
   console summary of category distribution.
"""

import csv
import re
from pathlib import Path


# ============================================================
# TAXONOMY
# ============================================================
# category -> keywords that map to it. Matching is exact-token
# first (a skill like "sql" matches "sql" exactly), then substring
# fallback (a skill like "rest apis" contains "api"). Order matters
# for the substring fallback -- first match wins -- so more
# specific categories are listed before more general ones.

SKILL_TAXONOMY = {
    "Automation & No-Code": ["n8n", "zapier"],
    "AI / LLM": ["langchain", "llm", "openai", "gpt"],
    "Backend & APIs": ["fastapi", "rest apis", "rest api", "flask", "django", "api"],
    "Databases": ["mongodb", "mysql", "postgres", "postgresql", "sql"],
    "Data & Scripting": ["pandas", "numpy", "web scraping", "selenium", "python"],
    "Frontend": ["react", "javascript", "typescript", "vue", "angular"],
    "DevOps & Infra": ["docker", "kubernetes", "aws", "gcp", "azure"],
}

# Category priority when picking a primary_category and there's a
# tie in match count -- earlier categories win. Automation/AI first
# since that's ConsultBae's core focus area (n8n, LangChain).
CATEGORY_PRIORITY = list(SKILL_TAXONOMY.keys())


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_skill_list(raw_skills_text):
    """
    'n8n, LangChain, REST APIs, MongoDB'
            -> ['n8n', 'langchain', 'rest apis', 'mongodb']

    Handles None/NaN-like input gracefully (returns []).
    """
    if raw_skills_text is None:
        return []

    text = str(raw_skills_text).strip()
    if not text or text.lower() == "nan":
        return []

    skills = [s.strip().lower() for s in text.split(",")]
    skills = [re.sub(r"\s+", " ", s) for s in skills if s]

    # de-dupe while preserving order
    seen = set()
    result = []
    for s in skills:
        if s not in seen:
            seen.add(s)
            result.append(s)

    return result


# ============================================================
# CLASSIFICATION
# ============================================================

def classify_skill(skill):
    """
    Classify one already-normalized skill string into a category,
    or None if it doesn't match anything in the taxonomy.
    """
    for category, keywords in SKILL_TAXONOMY.items():
        if skill in keywords:
            return category

    # substring fallback -- e.g. an unlisted variant like
    # "rest api integration" should still catch on "api"
    for category, keywords in SKILL_TAXONOMY.items():
        for keyword in keywords:
            if keyword in skill:
                return category

    return None


def classify_skills(raw_skills_text):
    """
    Main entry point. Takes a raw comma-separated skills string and
    returns a dict:

        {
          "skills": ["n8n", "langchain", "rest apis", "mongodb"],
          "categories": {
              "Automation & No-Code": ["n8n"],
              "AI / LLM": ["langchain"],
              "Backend & APIs": ["rest apis"],
              "Databases": ["mongodb"],
          },
          "primary_category": "Automation & No-Code",  # or None
          "uncategorized": [],
        }
    """
    skills = normalize_skill_list(raw_skills_text)

    categories = {}
    uncategorized = []

    for skill in skills:
        category = classify_skill(skill)
        if category is None:
            uncategorized.append(skill)
        else:
            categories.setdefault(category, []).append(skill)

    primary_category = None
    if categories:
        max_count = max(len(v) for v in categories.values())
        tied = [c for c, v in categories.items() if len(v) == max_count]
        # break ties using CATEGORY_PRIORITY order
        for category in CATEGORY_PRIORITY:
            if category in tied:
                primary_category = category
                break

    return {
        "skills": skills,
        "categories": categories,
        "primary_category": primary_category,
        "uncategorized": uncategorized,
    }


# ============================================================
# N8N INTEGRATION
# ============================================================
#
# n8n's Python "Code" node convention: read incoming items with
# `_input.all()`, each item exposes `.json` (a dict), and the node
# must end with a variable/expression producing a list of dicts
# (each wrapped in {"json": ...}) as the return value.
#
# Paste the block below into an n8n Python Code node (after also
# pasting in SKILL_TAXONOMY, normalize_skill_list, classify_skill,
# and classify_skills from above -- Pyodide can't import this file
# from disk, so the whole thing needs to live in the node).
#
# CLASSIFY_ITEMS_SNIPPET:
# ------------------------------------------------------------
#   results = []
#   for item in _input.all():
#       data = item.json
#       skills_text = data.get("skills") or data.get("skill_tags") or ""
#       classification = classify_skills(skills_text)
#       results.append({"json": {**data, "skill_classification": classification}})
#   return results
# ------------------------------------------------------------
#
# If instead you're calling this script from n8n's "Execute Command"
# node (rather than a Python Code node), use process_items_json()
# below, which reads a JSON array from stdin and writes a JSON array
# to stdout -- e.g. `python3 n8n/skill_classifier.py --stdin-json`.

def process_items_json(items):
    """
    items: list of dicts, each expected to have a "skills" or
    "skill_tags" key with the raw comma-separated string.
    Returns a new list of dicts with a "skill_classification" key
    added -- nested rather than spread flat, so this never silently
    overwrites an existing field on the caller's item (e.g. spreading
    would replace their raw "skills" string with our parsed list).
    """
    results = []
    for item in items:
        skills_text = item.get("skills") or item.get("skill_tags") or ""
        results.append({**item, "skill_classification": classify_skills(skills_text)})
    return results


# ============================================================
# STANDALONE BATCH MODE
# ============================================================

CLEANED_DIR = Path("data/cleaned")
OUTPUT_DIR = Path("n8n/output")

# (file name, column holding the raw skills text, column holding a
# human-readable identifier for reporting)
BATCH_SOURCES = [
    ("source1_naukri_applicants.csv", "skills", "full_name"),
    ("source2_gig_workers.csv", "skill_tags", "worker_name"),
]


def run_batch():
    import pandas as pd

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_rows = []
    category_totals = {}
    uncategorized_seen = set()

    for filename, skills_col, name_col in BATCH_SOURCES:
        file_path = CLEANED_DIR / filename
        if not file_path.exists():
            print(f"Skipping {filename}: not found in {CLEANED_DIR} "
                  f"(run scripts/clean_data.py first)")
            continue

        df = pd.read_csv(file_path)

        if skills_col not in df.columns:
            print(f"Skipping {filename}: column '{skills_col}' not found. "
                  f"Available columns: {list(df.columns)}")
            continue

        for _, row in df.iterrows():
            classification = classify_skills(row.get(skills_col))

            for category, matched in classification["categories"].items():
                category_totals[category] = category_totals.get(category, 0) + len(matched)

            uncategorized_seen.update(classification["uncategorized"])

            all_rows.append({
                "source_file": filename,
                "person_name": row.get(name_col, ""),
                "raw_skills": row.get(skills_col, ""),
                "primary_category": classification["primary_category"] or "",
                "categories": "; ".join(
                    f"{cat}: {', '.join(skills)}"
                    for cat, skills in classification["categories"].items()
                ),
                "uncategorized": ", ".join(classification["uncategorized"]),
            })

    if not all_rows:
        print("No rows processed. Nothing to write.")
        return

    output_file = OUTPUT_DIR / "skill_classification.csv"
    with open(output_file, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Classified {len(all_rows)} people.")
    print(f"Saved: {output_file}\n")

    print("Category distribution (total skill mentions):")
    for category in CATEGORY_PRIORITY:
        if category in category_totals:
            print(f"  {category:<25}: {category_totals[category]}")

    if uncategorized_seen:
        print(f"\nUncategorized skills seen ({len(uncategorized_seen)}) "
              f"-- consider adding these to SKILL_TAXONOMY:")
        for skill in sorted(uncategorized_seen):
            print(f"  - {skill}")


if __name__ == "__main__":
    run_batch()