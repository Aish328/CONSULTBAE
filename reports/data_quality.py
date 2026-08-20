
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

RAW_DIR = Path("data")
CLEANED_DIR = Path("data/cleaned")
MATCHED_FILE = Path("data/matched/matching_results.csv")
OUTPUT_DIR = Path("reports/output")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Collects (severity, message) tuples as the report runs, so we can
# print a consolidated "issues found" section at the end instead of
# making the reader hunt through the whole report for problems.
# severity is one of: "CRITICAL", "WARNING", "INFO"
ISSUES = []


def flag(severity, message):
    ISSUES.append((severity, message))


# ============================================================
# OUTPUT HELPERS
# ============================================================

# Everything printed also gets buffered here so the same content
# can be written to the saved report file.
_LINES = []


def line(text=""):
    print(text)
    _LINES.append(text)


def section(title):
    line("\n" + "=" * 70)
    line(title)
    line("=" * 70)


# ============================================================
# 1. RAW SOURCE FILES
# ============================================================

def find_column(df, possible_names):
  
    columns = {
        str(c).strip().lower().replace(" ", "_"): c
        for c in df.columns
    }
    for name in possible_names:
        if name.lower() in columns:
            return columns[name.lower()]
    return None


NAME_ALIASES = ["name", "full_name", "fullname", "candidate_name",
                "worker_name", "person_name"]
EMAIL_ALIASES = ["email", "email_address", "email_id", "mail"]
PHONE_ALIASES = ["phone", "phone_number", "mobile", "mobile_number",
                  "contact", "contact_number"]


def report_raw_files():
    section("1. RAW SOURCE FILES (data/*.csv)")

    csv_files = sorted(
        f for f in RAW_DIR.glob("*.csv")
        if "clean" not in f.stem.lower()
    )

    if not csv_files:
        line("No raw CSV files found in data/.")
        flag("CRITICAL", "No raw source CSV files found in data/.")
        return {}

    raw_stats = {}

    for file_path in csv_files:
        try:
            df = pd.read_csv(file_path)
        except Exception as exc:
            line(f"\n{file_path.name}: ERROR reading file -- {exc}")
            flag("CRITICAL", f"{file_path.name} could not be read: {exc}")
            continue

        name_col = find_column(df, NAME_ALIASES)
        email_col = find_column(df, EMAIL_ALIASES)
        phone_col = find_column(df, PHONE_ALIASES)

        exact_dupes = df.duplicated().sum()
        missing_name = df[name_col].isna().sum() if name_col else None
        missing_email = df[email_col].isna().sum() if email_col else None
        missing_phone = df[phone_col].isna().sum() if phone_col else None

        line(f"\n{file_path.name}")
        line(f"  Rows                 : {len(df)}")
        line(f"  Columns              : {len(df.columns)}")
        line(f"  Exact duplicate rows : {exact_dupes}")
        line(f"  Missing name         : {missing_name if name_col else 'n/a (no name column found)'}")
        line(f"  Missing email        : {missing_email if email_col else 'n/a (no email column found)'}")
        line(f"  Missing phone        : {missing_phone if phone_col else 'n/a (no phone column found)'}")

        if name_col is None:
            flag("WARNING", f"{file_path.name}: no recognizable name column.")
        if email_col is None and phone_col is None:
            flag(
                "CRITICAL",
                f"{file_path.name}: no email AND no phone column found "
                "-- these records can't be matched to anyone.",
            )
        if exact_dupes > 0:
            flag("WARNING", f"{file_path.name}: {exact_dupes} exact duplicate rows.")

        raw_stats[file_path.stem] = {
            "rows": len(df),
            "exact_dupes": int(exact_dupes),
        }

    return raw_stats


# ============================================================
# 2. CLEANING IMPACT
# ============================================================

def report_cleaning_impact(raw_stats):
    section("2. CLEANING IMPACT (data/*.csv -> data/cleaned/*.csv)")

    if not CLEANED_DIR.exists():
        line("data/cleaned/ does not exist -- run scripts/clean_data.py first.")
        flag("CRITICAL", "data/cleaned/ missing. Cleaning step has not been run.")
        return

    cleaned_files = sorted(CLEANED_DIR.glob("*.csv"))

    if not cleaned_files:
        line("No cleaned files found -- run scripts/clean_data.py first.")
        flag("CRITICAL", "data/cleaned/ is empty. Cleaning step has not been run.")
        return

    for file_path in cleaned_files:
        try:
            df = pd.read_csv(file_path)
        except Exception as exc:
            line(f"\n{file_path.name}: ERROR reading file -- {exc}")
            flag("CRITICAL", f"cleaned/{file_path.name} could not be read: {exc}")
            continue

        stem = file_path.stem
        raw_rows = raw_stats.get(stem, {}).get("rows")
        cleaned_rows = len(df)

        line(f"\n{file_path.name}")
        if raw_rows is not None:
            removed = raw_rows - cleaned_rows
            pct = (removed / raw_rows * 100) if raw_rows else 0
            line(f"  Raw rows      : {raw_rows}")
            line(f"  Cleaned rows  : {cleaned_rows}")
            line(f"  Removed       : {removed} ({pct:.1f}%)")

            if raw_rows > 0 and pct > 30:
                flag(
                    "WARNING",
                    f"{file_path.name}: cleaning removed {pct:.1f}% of rows "
                    "-- worth a manual look in case something upstream broke.",
                )
        else:
            line(f"  Cleaned rows  : {cleaned_rows} (no matching raw file to compare against)")

        for norm_col, label in [
            ("name_normalized", "name"),
            ("email_normalized", "email"),
            ("phone_normalized", "phone"),
        ]:
            if norm_col in df.columns:
                missing = df[norm_col].isna().sum()
                line(f"  Missing {label:<6}(post-clean): {missing}")


# ============================================================
# 3. MATCHING QUALITY
# ============================================================

def report_matching_quality():
    section("3. MATCHING QUALITY (data/matched/matching_results.csv)")

    if not MATCHED_FILE.exists():
        line("matching_results.csv not found -- run scripts/match_people.py first.")
        flag("CRITICAL", "matching_results.csv missing. Matching step has not been run.")
        return

    df = pd.read_csv(MATCHED_FILE, dtype={"phone": "string"})

    total_records = len(df)
    unique_persons = df["person_id"].nunique()

    line(f"\nTotal source records : {total_records}")
    line(f"Unique persons        : {unique_persons}")

    line("\nMatch type breakdown:")
    type_counts = df["match_type"].value_counts()
    for match_type, count in type_counts.items():
        line(f"  {match_type:<25}: {count}")

    medium_confidence = df[df["match_type"] == "MEDIUM_CONFIDENCE"]
    if len(medium_confidence) > 0:
        flag(
            "WARNING",
            f"{len(medium_confidence)} MEDIUM_CONFIDENCE matches found -- "
            "these were matched on fuzzy signals only (no exact email/phone) "
            "and are worth a manual spot-check.",
        )
        line(f"\n{len(medium_confidence)} MEDIUM_CONFIDENCE matches (manual review recommended):")
        cols = [c for c in ["person_id", "source_system", "name", "email",
                              "phone", "match_score", "match_reason"] if c in df.columns]
        line(medium_confidence[cols].to_string(index=False))

    sources_per_person = df.groupby("person_id")["source_system"].nunique()
    single_source = (sources_per_person == 1).sum()
    multi_source = (sources_per_person > 1).sum()

    line(f"\nPersons found in exactly 1 source : {single_source}")
    line(f"Persons found in 2+ sources       : {multi_source}")

    if unique_persons > 0:
        multi_source_pct = multi_source / unique_persons * 100
        if multi_source_pct < 10:
            flag(
                "WARNING",
                f"Only {multi_source_pct:.1f}% of persons matched across "
                "multiple sources -- if the same people are expected to "
                "appear in more than one source, this may mean matching "
                "is too strict (or normalization upstream is inconsistent).",
            )

    scored = df[~df["match_type"].isin(["BASE_RECORD", "NEW_PERSON"])]
    if len(scored) > 0 and "match_score" in scored.columns:
        line("\nMatch score distribution (matched records only):")
        line(f"  min  : {scored['match_score'].min():.1f}")
        line(f"  mean : {scored['match_score'].mean():.1f}")
        line(f"  max  : {scored['match_score'].max():.1f}")

    if "email" in df.columns and "phone" in df.columns:
        unmatchable = df[df["email"].isna() & df["phone"].isna()]
        if len(unmatchable) > 0:
            flag(
                "WARNING",
                f"{len(unmatchable)} source records have neither email nor "
                "phone -- these can never be matched to another source's "
                "record for the same person.",
            )


# ============================================================
# 4. DATABASE INTEGRITY (live Postgres)
# ============================================================

def report_database_integrity():
    section("4. DATABASE INTEGRITY (live Postgres)")

    try:
        import psycopg2
        from dotenv import load_dotenv
    except ImportError:
        line("psycopg2/python-dotenv not installed -- skipping DB checks.")
        line("(pip install -r requirements.txt to enable this section)")
        return

    load_dotenv()

    import os

    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            connect_timeout=5,
        )
    except Exception as exc:
        line(f"Could not connect to database -- skipping DB checks.")
        line(f"  ({exc})")
        flag(
            "INFO",
            "Database integrity checks were skipped (no DB connection). "
            "Run this report again with a reachable Postgres instance "
            "for the full picture.",
        )
        return

    try:
        with conn.cursor() as cur:
            # --- row counts ---
            cur.execute("SELECT COUNT(*) FROM persons;")
            persons_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM source_records;")
            source_records_count = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM audio_submissions;")
            audio_count = cur.fetchone()[0]

            line(f"\npersons rows           : {persons_count}")
            line(f"source_records rows    : {source_records_count}")
            line(f"audio_submissions rows : {audio_count}")

   
            cur.execute(
                """
                SELECT email, COUNT(*) FROM persons
                WHERE email IS NOT NULL
                GROUP BY email HAVING COUNT(*) > 1;
                """
            )
            dup_emails = cur.fetchall()

            cur.execute(
                """
                SELECT phone, COUNT(*) FROM persons
                WHERE phone IS NOT NULL
                GROUP BY phone HAVING COUNT(*) > 1;
                """
            )
            dup_phones = cur.fetchall()

            line(f"\nDuplicate emails in persons : {len(dup_emails)}")
            line(f"Duplicate phones in persons : {len(dup_phones)}")

            if dup_emails:
                flag(
                    "CRITICAL",
                    f"{len(dup_emails)} email(s) appear on more than one "
                    "persons row -- the entity-matching step should have "
                    "merged these into a single person.",
                )
                for email, count in dup_emails[:10]:
                    line(f"    {email}: {count} rows")

            if dup_phones:
                flag(
                    "CRITICAL",
                    f"{len(dup_phones)} phone(s) appear on more than one "
                    "persons row -- the entity-matching step should have "
                    "merged these into a single person.",
                )
                for phone, count in dup_phones[:10]:
                    line(f"    {phone}: {count} rows")

            # --- persons with neither email nor phone: unreachable ---
            cur.execute(
                "SELECT COUNT(*) FROM persons WHERE email IS NULL AND phone IS NULL;"
            )
            unreachable = cur.fetchone()[0]
            line(f"\nPersons with no email AND no phone : {unreachable}")
            if unreachable > 0:
                flag(
                    "WARNING",
                    f"{unreachable} person(s) have neither email nor phone "
                    "-- there is no way to contact them or reliably match "
                    "future records to them.",
                )

            # --- persons with zero source_records (orphans) ---
            cur.execute(
                """
                SELECT COUNT(*) FROM persons p
                WHERE NOT EXISTS (
                    SELECT 1 FROM source_records sr WHERE sr.person_id = p.id
                );
                """
            )
            orphan_persons = cur.fetchone()[0]
            line(f"Persons with zero source_records   : {orphan_persons}")
            if orphan_persons > 0:
                flag(
                    "WARNING",
                    f"{orphan_persons} person(s) have no linked source_records "
                    "-- likely created outside the CSV pipeline (e.g. via the "
                    "audio submission API) with no prior history, which is "
                    "expected, but worth confirming.",
                )

            # --- audio_submissions per person (basic distribution) ---
            if audio_count > 0:
                cur.execute(
                    """
                    SELECT COUNT(DISTINCT person_id) FROM audio_submissions;
                    """
                )
                distinct_submitters = cur.fetchone()[0]
                line(f"\nDistinct people with audio submissions : {distinct_submitters}")
                line(f"Total audio submissions                : {audio_count}")

    finally:
        conn.close()


# ============================================================
# SUMMARY
# ============================================================

def report_summary():
    section("SUMMARY")

    if not ISSUES:
        line("\nNo issues found. Pipeline looks healthy.")
        return

    critical = [m for s, m in ISSUES if s == "CRITICAL"]
    warnings = [m for s, m in ISSUES if s == "WARNING"]
    info = [m for s, m in ISSUES if s == "INFO"]

    line(f"\n{len(critical)} CRITICAL, {len(warnings)} WARNING, {len(info)} INFO")

    for severity, messages in [
        ("CRITICAL", critical),
        ("WARNING", warnings),
        ("INFO", info),
    ]:
        if not messages:
            continue
        line(f"\n[{severity}]")
        for msg in messages:
            line(f"  - {msg}")


def main():
    line("CONSULTBAE DATA QUALITY REPORT")
    line(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    raw_stats = report_raw_files()
    report_cleaning_impact(raw_stats)
    report_matching_quality()
    report_database_integrity()
    report_summary()

    output_file = OUTPUT_DIR / f"data_quality_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    output_file.write_text("\n".join(_LINES))
    print(f"\nReport saved to: {output_file}")

    has_critical = any(s == "CRITICAL" for s, _ in ISSUES)
    sys.exit(1 if has_critical else 0)


if __name__ == "__main__":
    main()