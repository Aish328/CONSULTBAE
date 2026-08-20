"""
Turns matching_results.csv (one row per SOURCE record) into:

  1. persons_df       -- one row per real person, with a single
                          canonical name/email/phone/city chosen
                          for that person
  2. source_records_df -- unchanged, one row per source record,
                          still carrying person_id as the link

This is deliberately separated from the database-writing step
(ingest_to_db.py) so the "which value wins" logic can be tested
on its own, without needing a live Postgres connection.
"""

from pathlib import Path

import pandas as pd


MATCHED_FILE = Path(r"C:\Users\Lenovo\Desktop\consultbae_updated\consultbae\data\matched\matching_results.csv")

# Source priority when choosing the canonical name/email/phone
# for a person. Naukri has the richest fields (name+email+phone),
# so it wins when present. CBNexus has phone+name but no email.
# Gig workers has name+email but no phone.
SOURCE_PRIORITY = ["naukri", "cbnexus", "gig_workers"]


def choose_canonical_record(person_rows):
    """
    person_rows: DataFrame of all source rows for ONE person_id.

    Returns a dict with the canonical name/email/phone/city for
    that person, plus a note on which source(s) contributed.
    """

    # Sort candidate rows by source priority, most-preferred first.
    ordered = person_rows.copy()
    ordered["priority"] = ordered["source_system"].apply(
        lambda s: SOURCE_PRIORITY.index(s) if s in SOURCE_PRIORITY else 99
    )
    ordered = ordered.sort_values("priority")

    canonical = {}

    # For each field, take the first non-null value in priority order.
    # This means: if Naukri has a name, use Naukri's name. If Naukri
    # is missing (this person never appeared in Naukri), fall back to
    # CBNexus, then gig_workers.
    for field in ["name", "email", "phone", "city"]:
        value = None
        for _, row in ordered.iterrows():
            candidate = row.get(field)
            if pd.notna(candidate) and str(candidate).strip():
                value = candidate
                break
        canonical[field] = value

    canonical["sources"] = "|".join(sorted(person_rows["source_system"].unique()))
    canonical["source_row_count"] = len(person_rows)

    return canonical


def build_persons(matched_df):
    """
    Returns (persons_df, source_records_df).

    persons_df has one row per person_id with canonical fields.
    source_records_df is matched_df unchanged (kept separate so
    the caller can insert it as-is into source_records).
    """

    person_records = []

    for person_id, group in matched_df.groupby("person_id"):
        canonical = choose_canonical_record(group)
        canonical["person_id"] = person_id
        person_records.append(canonical)

    persons_df = pd.DataFrame(person_records)[
        ["person_id", "name", "email", "phone", "city", "sources", "source_row_count"]
    ]

    return persons_df, matched_df


def main():
    # Read phone as a string explicitly. Without this, pandas
    # infers the phone column as float64 (because some rows have
    # no phone -> NaN forces the whole int-looking column to
    # float), which silently corrupts every phone number with a
    # trailing ".0" once printed or written out.
    matched_df = pd.read_csv(MATCHED_FILE, dtype={"phone": "string"})

    persons_df, source_records_df = build_persons(matched_df)

    print(f"Source records : {len(source_records_df)}")
    print(f"Unique persons : {len(persons_df)}")

    print("\nPeople assembled from more than one source (the actual merges):")
    multi_source = persons_df[persons_df["sources"].str.contains(r"\|")]
    print(multi_source.to_string(index=False))

    print("\nSample of single-source people:")
    print(persons_df[~persons_df["sources"].str.contains(r"\|")].head(5).to_string(index=False))


if __name__ == "__main__":
    main()
