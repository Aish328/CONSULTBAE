import re
from pathlib import Path

import pandas as pd
from rapidfuzz.fuzz import ratio


# ============================================================
# CONFIGURATION
# ============================================================

CLEANED_DIR = Path(r"C:\Users\Lenovo\Desktop\consultbae_updated\consultbae\data\cleaned")
OUTPUT_DIR = Path(r"C:\Users\Lenovo\Desktop\consultbae_updated\consultbae\data\matched")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# NORMALIZATION
# ============================================================

def clean_text(value):
    if pd.isna(value) or value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    value = re.sub(r"\s+", " ", value)

    return value


def normalize_name(value):
    value = clean_text(value)

    if value is None:
        return None

    return value.lower()


def normalize_email(value):
    value = clean_text(value)

    if value is None:
        return None

    return value.lower()


def normalize_phone(value):
    value = clean_text(value)

    if value is None:
        return None

    digits = re.sub(r"\D", "", value)

    if not digits:
        return None

    # Keep last 10 digits.
    if len(digits) > 10:
        digits = digits[-10:]

    return digits


def normalize_city(value):
    value = clean_text(value)

    if value is None:
        return None

    return value.lower()


# ============================================================
# NAME SIMILARITY
# ============================================================

def name_similarity(name1, name2):

    if not name1 or not name2:
        return 0

    return ratio(
        normalize_name(name1),
        normalize_name(name2)
    )


# ============================================================
# LOAD DATA
# ============================================================

def load_sources():

    naukri = pd.read_csv(
        CLEANED_DIR / "source1_naukri_applicants.csv"
    )

    gig = pd.read_csv(
        CLEANED_DIR / "source2_gig_workers.csv"
    )

    cbnexus = pd.read_csv(
        CLEANED_DIR / "source3_cbnexus_contacts.csv"
    )

    return naukri, gig, cbnexus


# ============================================================
# PREPARE NAUKRI
# ============================================================

def prepare_naukri(df):

    result = pd.DataFrame()

    result["source_system"] = "naukri"

    result["source_row"] = range(
        2,
        len(df) + 2
    )

    result["name"] = df["full_name"].apply(
        normalize_name
    )

    result["email"] = df["email"].apply(
        normalize_email
    )

    result["phone"] = df["phone"].apply(
        normalize_phone
    )

    result["city"] = df["city"].apply(
        normalize_city
    )

    result["skills"] = df["skills"]

    return result


# ============================================================
# PREPARE GIG WORKERS
# ============================================================

def prepare_gig(df):

    result = pd.DataFrame()

    result["source_system"] = "gig_workers"

    result["source_row"] = range(
        2,
        len(df) + 2
    )

    result["name"] = df["worker_name"].apply(
        normalize_name
    )

    result["email"] = df["email_id"].apply(
        normalize_email
    )

    result["phone"] = None

    result["city"] = df["location"].apply(
        normalize_city
    )

    result["skills"] = df["skill_tags"]

    return result


# ============================================================
# PREPARE CBNEXUS
# ============================================================

def prepare_cbnexus(df):

    result = pd.DataFrame()

    result["source_system"] = "cbnexus"

    result["source_row"] = range(
        2,
        len(df) + 2
    )

    result["name"] = df["name"].apply(
        normalize_name
    )

    result["email"] = None

    result["phone"] = df["phone_number"].apply(
        normalize_phone
    )

    result["city"] = df["city"].apply(
        normalize_city
    )

    result["skills"] = None

    return result


# ============================================================
# MATCH SCORE
# ============================================================

def calculate_match(record_a, record_b):

    score = 0
    reasons = []

    # --------------------------------------------------------
    # Exact email
    # --------------------------------------------------------

    if (
        record_a["email"]
        and record_b["email"]
        and record_a["email"] == record_b["email"]
    ):

        score += 100

        reasons.append(
            "exact_email"
        )

    # --------------------------------------------------------
    # Exact phone
    # --------------------------------------------------------

    if (
        record_a["phone"]
        and record_b["phone"]
        and record_a["phone"] == record_b["phone"]
    ):

        score += 100

        reasons.append(
            "exact_phone"
        )

    # --------------------------------------------------------
    # Name similarity
    # --------------------------------------------------------

    similarity = name_similarity(
        record_a["name"],
        record_b["name"]
    )

    if similarity >= 95:

        score += 30

        reasons.append(
            f"name_similarity_{similarity:.1f}"
        )

    elif similarity >= 85:

        score += 20

        reasons.append(
            f"name_similarity_{similarity:.1f}"
        )

    elif similarity >= 70:

        score += 10

        reasons.append(
            f"name_similarity_{similarity:.1f}"
        )

    # --------------------------------------------------------
    # City agreement
    # --------------------------------------------------------

    if (
        record_a["city"]
        and record_b["city"]
        and record_a["city"] == record_b["city"]
    ):

        score += 10

        reasons.append(
            "same_city"
        )

    return score, reasons


# ============================================================
# MATCH TWO RECORDS
# ============================================================

def classify_match(score, reasons):

    if "exact_email" in reasons:

        return "HIGH_CONFIDENCE"

    if "exact_phone" in reasons:

        return "HIGH_CONFIDENCE"

    if score >= 50:

        return "MEDIUM_CONFIDENCE"

    return "NO_MATCH"


# ============================================================
# MATCH DATASETS
# ============================================================

def perform_matching(naukri, gig, cbnexus):

    results = []

    person_counter = 1

    # --------------------------------------------------------
    # Create a person for every Naukri record, but first check
    # each row against EARLIER Naukri rows already processed.
    #
    # This catches the same person appearing twice within the
    # same file (e.g. "R. Verma" and "Rohit Verma" sharing an
    # email+phone, or a name re-entered with an alt. email).
    #
    # Only an exact email or exact phone match (HIGH_CONFIDENCE)
    # is accepted here -- name similarity alone is deliberately
    # NOT enough to merge within Naukri, because two different
    # real people can share a name (see: the two "Arjun Mehta"
    # records with different phone numbers across the files).
    # --------------------------------------------------------

    person_map = {}

    naukri_records = list(naukri.iterrows())

    for position, (index, record) in enumerate(naukri_records):

        best_person = None
        best_score = 0
        best_reasons = []

        for other_index, other_record in naukri_records[:position]:

            score, reasons = calculate_match(
                record,
                other_record
            )

            if score > best_score:

                best_score = score
                best_person = person_map[
                    ("naukri", other_index)
                ]
                best_reasons = reasons

        match_type = classify_match(
            best_score,
            best_reasons
        )

        if match_type == "HIGH_CONFIDENCE" and best_person is not None:

            person_id = best_person

            results.append({
                "person_id": person_id,
                "source_system": "naukri",
                "source_row": record["source_row"],
                "name": record["name"],
                "email": record["email"],
                "phone": record["phone"],
                "city": record["city"],
                "match_type": "DUPLICATE_WITHIN_SOURCE",
                "match_score": best_score,
                "match_reason": "|".join(best_reasons)
            })

        else:

            person_id = person_counter

            person_counter += 1

            results.append({
                "person_id": person_id,
                "source_system": "naukri",
                "source_row": record["source_row"],
                "name": record["name"],
                "email": record["email"],
                "phone": record["phone"],
                "city": record["city"],
                "match_type": "BASE_RECORD",
                "match_score": 0,
                "match_reason": "naukri_base"
            })

        person_map[
            ("naukri", index)
        ] = person_id

    # --------------------------------------------------------
    # Match Gig Workers to Naukri
    # --------------------------------------------------------

    for gig_index, gig_record in gig.iterrows():

        best_person = None
        best_score = 0
        best_reasons = []

        for naukri_index, naukri_record in naukri.iterrows():

            score, reasons = calculate_match(
                gig_record,
                naukri_record
            )

            if score > best_score:

                best_score = score
                best_person = person_map[
                    ("naukri", naukri_index)
                ]
                best_reasons = reasons

        match_type = classify_match(
            best_score,
            best_reasons
        )

        if match_type in [
            "HIGH_CONFIDENCE",
            "MEDIUM_CONFIDENCE"
        ]:

            results.append({
                "person_id": best_person,
                "source_system": "gig_workers",
                "source_row": gig_record["source_row"],
                "name": gig_record["name"],
                "email": gig_record["email"],
                "phone": gig_record["phone"],
                "city": gig_record["city"],
                "match_type": match_type,
                "match_score": best_score,
                "match_reason": "|".join(
                    best_reasons
                )
            })

        else:

            # No confident match.
            # Create a new person.
            person_id = person_counter

            person_counter += 1

            results.append({
                "person_id": person_id,
                "source_system": "gig_workers",
                "source_row": gig_record["source_row"],
                "name": gig_record["name"],
                "email": gig_record["email"],
                "phone": gig_record["phone"],
                "city": gig_record["city"],
                "match_type": "NEW_PERSON",
                "match_score": best_score,
                "match_reason": "no_confident_match"
            })

    # --------------------------------------------------------
    # Match CBNexus to Naukri
    # --------------------------------------------------------

    for cb_index, cb_record in cbnexus.iterrows():

        best_person = None
        best_score = 0
        best_reasons = []

        for naukri_index, naukri_record in naukri.iterrows():

            score, reasons = calculate_match(
                cb_record,
                naukri_record
            )

            if score > best_score:

                best_score = score
                best_person = person_map[
                    ("naukri", naukri_index)
                ]
                best_reasons = reasons

        match_type = classify_match(
            best_score,
            best_reasons
        )

        if match_type in [
            "HIGH_CONFIDENCE",
            "MEDIUM_CONFIDENCE"
        ]:

            results.append({
                "person_id": best_person,
                "source_system": "cbnexus",
                "source_row": cb_record["source_row"],
                "name": cb_record["name"],
                "email": cb_record["email"],
                "phone": cb_record["phone"],
                "city": cb_record["city"],
                "match_type": match_type,
                "match_score": best_score,
                "match_reason": "|".join(
                    best_reasons
                )
            })

        else:

            person_id = person_counter

            person_counter += 1

            results.append({
                "person_id": person_id,
                "source_system": "cbnexus",
                "source_row": cb_record["source_row"],
                "name": cb_record["name"],
                "email": cb_record["email"],
                "phone": cb_record["phone"],
                "city": cb_record["city"],
                "match_type": "NEW_PERSON",
                "match_score": best_score,
                "match_reason": "no_confident_match"
            })

    return pd.DataFrame(results)


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("CONSULTBAE ENTITY MATCHING")
    print("=" * 70)

    naukri_raw, gig_raw, cb_raw = load_sources()

    print(
        f"\nNaukri records     : {len(naukri_raw)}"
    )

    print(
        f"Gig worker records : {len(gig_raw)}"
    )

    print(
        f"CBNexus records    : {len(cb_raw)}"
    )

    # Prepare datasets

    naukri = prepare_naukri(
        naukri_raw
    )

    gig = prepare_gig(
        gig_raw
    )

    cbnexus = prepare_cbnexus(
        cb_raw
    )

    # Perform matching

    results = perform_matching(
        naukri,
        gig,
        cbnexus
    )

    # Save result

    output_file = (
        OUTPUT_DIR /
        "matching_results.csv"
    )

    results.to_csv(
        output_file,
        index=False
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("MATCHING SUMMARY")
    print("=" * 70)

    print(
        f"Total source records : {len(results)}"
    )

    print(
        f"Unique persons       : "
        f"{results['person_id'].nunique()}"
    )

    print("\nMatch types:")

    print(
        results["match_type"]
        .value_counts()
        .to_string()
    )

    print("\nSource distribution:")

    print(
        results["source_system"]
        .value_counts()
        .to_string()
    )

    print(
        f"\nSaved:"
        f"\n{output_file}"
    )


if __name__ == "__main__":
    main()