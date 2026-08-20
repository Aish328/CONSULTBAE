"""
ConsultBae Task 3 -- audio submission web app.

Single endpoint that lets a person submit their name/email/phone
plus an audio recording. We:
  1. find-or-create their `persons` row (matches Task 1's dedup
     logic in spirit: email first, then phone)
  2. save the uploaded audio file to disk
  3. analyze it (duration, sample rate, bitrate, loudness, noise)
  4. store the analysis in `audio_submissions`

Run locally with:
    python3 backend/app.py
(requires the same .env as scripts/ingest_to_db.py: DB_HOST,
DB_PORT, DB_NAME, DB_USER, DB_PASSWORD)
"""

import os
import uuid
from pathlib import Path

from email_validator import EmailNotValidError, validate_email
from flask import Flask, jsonify, request, send_from_directory

import database
from audio_processor import process_audio

UPLOAD_DIR = Path(os.getenv("AUDIO_UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm"}
MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


@app.route("/", methods=["GET"])
def index():
    """
    Serves frontend/index.html directly from Flask, so the page and
    the API share one origin (no CORS setup needed) and there's an
    actual page here instead of the default 404.
    """
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/submissions", methods=["GET"])
def submissions_page():
    """
    The "second view" required by Task 3: lists every audio
    submission across all people with a play button and the
    extracted properties.
    """
    return send_from_directory(FRONTEND_DIR, "submissions.html")


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/submissions", methods=["GET"])
def all_submissions():
    """All audio submissions, newest first, joined with the
    submitter's name/email/phone. Backs the /submissions page."""
    conn = database.get_connection()
    try:
        submissions = database.get_all_submissions(conn)
    finally:
        conn.close()
    return jsonify(submissions)


@app.route("/api/audio/<path:filename>", methods=["GET"])
def serve_audio(filename):
    """
    Streams a stored audio file so the <audio> player on the
    submissions list can actually play it.

    Path-traversal note: we only accept a bare filename (no
    directories) and only serve files that already exist inside
    UPLOAD_DIR -- send_from_directory itself also refuses to resolve
    outside its given directory, but the basename check below is a
    second, explicit guard rather than relying solely on that.
    """
    safe_name = Path(filename).name
    if safe_name != filename or not (UPLOAD_DIR / safe_name).is_file():
        return jsonify({"error": "audio file not found"}), 404
    return send_from_directory(UPLOAD_DIR, safe_name)


@app.route("/api/submit", methods=["POST"])
def submit():
    """
    multipart/form-data:
        name  (required)
        email (optional if phone given)
        phone (optional if email given)
        audio (required, file)
    """
    name = (request.form.get("name") or "").strip()
    email = (request.form.get("email") or "").strip() or None
    phone = (request.form.get("phone") or "").strip() or None
    audio_file = request.files.get("audio")

    # ---- validation ----
    if not name:
        return jsonify({"error": "name is required"}), 400

    if not email and not phone:
        return jsonify({"error": "email or phone is required"}), 400

    if email:
        try:
            email = validate_email(email, check_deliverability=False).normalized
        except EmailNotValidError as exc:
            return jsonify({"error": f"invalid email: {exc}"}), 400

    if not audio_file or audio_file.filename == "":
        return jsonify({"error": "audio file is required"}), 400

    ext = Path(audio_file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return (
            jsonify(
                {
                    "error": (
                        f"unsupported audio format '{ext}'. "
                        f"Allowed: {sorted(ALLOWED_EXTENSIONS)}"
                    )
                }
            ),
            400,
        )

    # ---- save file to disk with a collision-proof name ----
    stored_filename = f"{uuid.uuid4().hex}{ext}"
    stored_path = UPLOAD_DIR / stored_filename
    audio_file.save(stored_path)

    # ---- analyze audio ----
    try:
        metrics = process_audio(str(stored_path))
    except ValueError as exc:
        stored_path.unlink(missing_ok=True)
        return jsonify({"error": str(exc)}), 400

    # ---- write to DB ----
    conn = database.get_connection()
    try:
        person, created_new = database.get_or_create_person(
            conn, name=name, email=email, phone=phone
        )
        submission = database.insert_audio_submission(
            conn,
            person_id=person.id,
            audio_path=str(stored_path),
            metrics=metrics,
        )
    except Exception as exc:
        conn.rollback()
        stored_path.unlink(missing_ok=True)
        return jsonify({"error": f"database error: {exc}"}), 500
    finally:
        conn.close()

    return (
        jsonify(
            {
                "person": person.to_dict(),
                "person_created": created_new,
                "submission": submission.to_dict(),
            }
        ),
        201,
    )


@app.route("/api/persons/<int:person_id>/submissions", methods=["GET"])
def list_submissions(person_id):
    conn = database.get_connection()
    try:
        submissions = database.get_submissions_for_person(conn, person_id)
    finally:
        conn.close()

    return jsonify([s.to_dict() for s in submissions])


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", 5000)))
