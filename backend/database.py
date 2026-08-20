"""
Database access for the web app (Task 3).

Uses the same connection style as scripts/ingest_to_db.py (raw
psycopg2, credentials from .env) so both the batch pipeline and the
web app talk to Postgres the same way.

Person matching here is intentionally simple compared to
scripts/match_people.py: that script does offline fuzzy matching
across three CSV exports. Here, someone is submitting audio live
through a form, so we just need to know "have we seen this email or
phone before" -- exact match on email first (most reliable), then
phone. If neither matches, a new person row is created.
"""

import os

import psycopg2
from dotenv import load_dotenv

from models import AudioSubmission, Person

load_dotenv()


def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )


def find_person(conn, email=None, phone=None):
    """
    Look for an existing person by email first, then phone.
    Returns a Person or None.
    """
    with conn.cursor() as cur:
        if email:
            cur.execute(
                """
                SELECT id, name, email, phone, created_at, updated_at
                FROM persons
                WHERE email = %s
                LIMIT 1;
                """,
                (email,),
            )
            row = cur.fetchone()
            if row:
                return Person.from_row(row)

        if phone:
            cur.execute(
                """
                SELECT id, name, email, phone, created_at, updated_at
                FROM persons
                WHERE phone = %s
                LIMIT 1;
                """,
                (phone,),
            )
            row = cur.fetchone()
            if row:
                return Person.from_row(row)

    return None


def create_person(conn, name, email, phone):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO persons (name, email, phone)
            VALUES (%s, %s, %s)
            RETURNING id, name, email, phone, created_at, updated_at;
            """,
            (name, email, phone),
        )
        row = cur.fetchone()
    conn.commit()
    return Person.from_row(row)


def get_or_create_person(conn, name, email, phone):
    """
    Find a matching person by email/phone; if none exists, create
    one. This is the single entry point app.py should call -- it
    keeps the match-then-create logic in one place instead of
    scattered across routes.
    """
    existing = find_person(conn, email=email, phone=phone)
    if existing:
        return existing, False  # (person, created_new)

    created = create_person(conn, name=name, email=email, phone=phone)
    return created, True


def insert_audio_submission(conn, person_id, audio_path, metrics):
    """
    metrics: dict with keys duration_seconds, sample_rate_khz,
    bitrate_kbps, loudness_db, noise_score (all from
    audio_processor.process_audio).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO audio_submissions
                (person_id, audio_path, duration_seconds,
                 sample_rate_khz, bitrate_kbps, loudness_db, noise_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, person_id, audio_path, duration_seconds,
                      sample_rate_khz, bitrate_kbps, loudness_db,
                      noise_score, created_at;
            """,
            (
                person_id,
                audio_path,
                metrics.get("duration_seconds"),
                metrics.get("sample_rate_khz"),
                metrics.get("bitrate_kbps"),
                metrics.get("loudness_db"),
                metrics.get("noise_score"),
            ),
        )
        row = cur.fetchone()
    conn.commit()
    return AudioSubmission.from_row(row)


def get_submissions_for_person(conn, person_id):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, person_id, audio_path, duration_seconds,
                   sample_rate_khz, bitrate_kbps, loudness_db,
                   noise_score, created_at
            FROM audio_submissions
            WHERE person_id = %s
            ORDER BY created_at DESC;
            """,
            (person_id,),
        )
        rows = cur.fetchall()
    return [AudioSubmission.from_row(row) for row in rows]