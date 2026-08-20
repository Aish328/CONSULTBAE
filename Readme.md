# ConsultBae

## What this is

Two pieces:

1. **Data pipeline (Task 1)** — merges 3 messy candidate/contact
   CSVs (Naukri applicants, gig workers, CBNexus contacts) into a
   single deduplicated `persons` table in Postgres, tracking which
   raw source each merged person came from.
2. **Audio submission backend (Task 3)** — a small Flask app that
   lets a person submit their details + a voice recording, analyzes
   the recording (duration, sample rate, bitrate, loudness, a noise
   heuristic), and stores it against their `persons` row.

## Setup

```bash
pip install -r requirements.txt
```

`pydub` (used for audio analysis) shells out to **ffmpeg** — make
sure it's installed and on your PATH (`ffmpeg -version` to check).
On Ubuntu/Debian: `sudo apt install ffmpeg`. On Mac: `brew install ffmpeg`.

Create a `.env` file in the project root:

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=consultbae
DB_USER=postgres
DB_PASSWORD=your_password
```

Make sure the `consultbae` database exists:
```bash
psql -U postgres -h localhost -c "CREATE DATABASE consultbae;"
```

## Running the data pipeline

Run in order — each step depends on the previous one's output:

```bash
python3 scripts/clean_data.py      # data/*.csv          -> data/cleaned/*.csv
python3 scripts/match_people.py    # data/cleaned/*.csv   -> data/matched/matching_results.csv
python3 scripts/ingest_to_db.py    # data/matched/...     -> Postgres (persons, source_records)
```

`ingest_to_db.py` auto-creates the schema if it doesn't exist yet,
and truncates+reloads `persons`/`source_records` on every run, so
it's always safe to re-run from scratch. It does **not** touch
`audio_submissions` — that table is only written to by the backend
below.

Current dataset produces **60 unique persons** from **102** raw
source rows across the 3 files.

## Running the audio submission backend

```bash
cd backend
python3 app.py
```

Starts a dev server on `http://localhost:5000`. Endpoints:

- `GET /api/health` — liveness check
- `POST /api/submit` — multipart form: `name` (required), `email`
  and/or `phone` (at least one required), `audio` (required file —
  wav/mp3/m4a/ogg/flac/webm, 25MB max). Finds an existing person by
  email then phone, or creates a new one; saves the audio to
  `backend/uploads/`; analyzes it; stores the result.
- `GET /api/persons/<id>/submissions` — list a person's audio
  submissions.

Example:
```bash
curl -X POST http://localhost:5000/api/submit \
  -F "name=Jane Doe" \
  -F "email=jane@example.com" \
  -F "audio=@recording.wav"
```

### About `noise_score`

There's no universal standard for scoring noise in a short clip, so
this is a documented heuristic (see `backend/audio_processor.py`):
it compares the loudest vs. quietest 100ms windows in the clip.
Clean recordings have real silence between speech (a big gap =
low/clean score); noisy recordings have a "noise floor" even in the
quiet parts (a small gap = high/noisy score). Treat it as a rough
0–100 triage signal, not a precise acoustic measurement.

## Project layout

```
data/                 raw source CSVs
data/cleaned/         output of clean_data.py
data/matched/         output of match_people.py
database/schema.sql   Postgres schema (persons, source_records, audio_submissions)
scripts/               data pipeline scripts (run in order, see above)
backend/               Flask app for audio submissions (Task 3)
  app.py               routes
  database.py           Postgres access
  audio_processor.py    audio analysis
  models.py             Person / AudioSubmission data shapes
  uploads/              saved audio files (created at runtime)
reports/data_quality.py  not yet implemented
n8n/skill_classifier.py  not yet implemented
frontend/                not yet implemented
```

## Known gotchas already fixed here

- `ingest_to_db.py` used to crash with `can't adapt type 'NAType'`
  on any row with a missing phone number (30 of the 102 rows have
  no phone, e.g. all `gig_workers` rows) because pandas' nullable
  `"string"` dtype uses `pd.NA` instead of `None`, which psycopg2
  can't insert directly. Fixed by converting `pd.NA`/`NaN` to
  `None` before hitting the DB.