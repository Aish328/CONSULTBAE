
import os
from pathlib import Path

import pandas as pd
import psycopg2
from dotenv import load_dotenv

from build_persons import build_persons

load_dotenv()

MATCHED_FILE = Path("data/matched/matching_results.csv")
SCHEMA_FILE = Path("database/schema.sql")


def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


def ensure_schema(conn):
   
    with conn.cursor() as cur:
        cur.execute(SCHEMA_FILE.read_text())
    conn.commit()


def clear_existing_data(conn):
    
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE source_records RESTART IDENTITY;")
        cur.execute("TRUNCATE TABLE persons RESTART IDENTITY CASCADE;")
    conn.commit()


def insert_persons(conn, persons_df):
   
    csv_id_to_db_id = {}

    with conn.cursor() as cur:
        for _, row in persons_df.iterrows():
            cur.execute(
                """
                INSERT INTO persons (name, email, phone)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (row["name"], row["email"], row["phone"]),
            )
            db_id = cur.fetchone()[0]
            csv_id_to_db_id[row["person_id"]] = db_id

    conn.commit()
    return csv_id_to_db_id


def insert_source_records(conn, source_records_df, csv_id_to_db_id):
    with conn.cursor() as cur:
        for _, row in source_records_df.iterrows():
            db_person_id = csv_id_to_db_id[row["person_id"]]

            cur.execute(
                """
                INSERT INTO source_records
                    (person_id, source_system, source_record_id,
                     raw_name, raw_email, raw_phone)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (
                    db_person_id,
                    row["source_system"],
                    str(row["source_row"]),
                    row["name"],
                    row["email"],
                    row["phone"],
                ),
            )

    conn.commit()


def _clean_for_db(df):
   
    return df.astype(object).where(pd.notnull(df), None)


def main():
    matched_df = pd.read_csv(MATCHED_FILE, dtype={"phone": "string"})
    matched_df = _clean_for_db(matched_df)
    persons_df, source_records_df = build_persons(matched_df)
    persons_df = _clean_for_db(persons_df)
    source_records_df = _clean_for_db(source_records_df)

    print(f"Persons to insert        : {len(persons_df)}")
    print(f"Source records to insert : {len(source_records_df)}")

    conn = get_connection()

    try:
        ensure_schema(conn)
        clear_existing_data(conn)

        csv_id_to_db_id = insert_persons(conn, persons_df)
        insert_source_records(conn, source_records_df, csv_id_to_db_id)

        print("\nIngestion complete.")

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM persons;")
            print(f"persons rows in DB        : {cur.fetchone()[0]}")
            cur.execute("SELECT COUNT(*) FROM source_records;")
            print(f"source_records rows in DB : {cur.fetchone()[0]}")

    except Exception as error:
        conn.rollback()
        print("Ingestion FAILED, rolled back.")
        print(error)
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    main()