# ConsultBae

## What this is

Take-home submission for the ConsultBae AI Automation assignment. Four
pieces:

1. **Data pipeline (Task 1)** — merges 3 messy candidate/contact
   CSVs (Naukri applicants, gig workers, CBNexus contacts) into a
   single deduplicated `persons` table in Postgres, tracking which
   raw source each merged person came from. See `DATA_ISSUES.md` for
   the full list of data problems found and how each was handled.
2. **n8n automation (Task 2)** — `n8n/duplicate_alert_workflow.json`:
   webhook receives a new CSV → normalizes fields the same way
   `clean_data.py` does → checks each row against Postgres → sends a
   duplicate alert for matches, inserts new people otherwise. See
   "Running the n8n automation" below.
3. **Audio submission app (Task 3)** — a Flask app + plain HTML/JS
   frontend where a person enters their name/phone, records audio in
   the browser (or uploads a file), and submits. Duration, sample
   rate, bitrate, loudness, and a noise heuristic are extracted
   automatically and stored, and a second page lists every submission
   with a player.
4. **Data quality report (Task 4)** — `reports/data_quality.py` walks
   the pipeline end-to-end (raw → cleaned → matched → DB) and prints/
   saves a health report; `DATA_ISSUES.md` is the narrative writeup.

Task 5 (scaling to 5,000 workers over a weekend) is in `STRETCH.md`.

## Setup

```bash
pip install -r requirements.txt
```

`pydub` (used for audio analysis) shells out to **ffmpeg** — make
sure it's installed and on your PATH (`ffmpeg -version` to check).
On Ubuntu/Debian: `sudo apt install ffmpeg`. On Mac: `brew install ffmpeg`.

Create a `.env` file in the project root (see `.env.example`):

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

## Running the n8n automation (Task 2)

`n8n/duplicate_alert_workflow.json` is the exported flow. To run it:

1. Install n8n (`npx n8n` or the desktop app) and open the editor.
2. Import `n8n/duplicate_alert_workflow.json` (Workflows → Import from
   File).
3. Open the **Check Against Database** and **Insert New Person** /
   **Insert Source Record** nodes and point their Postgres credential
   at the same DB as `.env` (host/port/db/user/password).
4. Set the **Send Duplicate Alert** node's URL to wherever you want
   the alert delivered (a Slack incoming webhook, or
   https://webhook.site for a quick demo target).
5. Activate the workflow, then `POST` a CSV file to the webhook URL
   n8n shows you (same shape as the Task 1 source files — a `Name`/
   `Full Name`, `Phone`/`Phone Number`, `Email` column, etc.). Rows
   that match an existing person by email or phone trigger the alert;
   rows that don't get inserted as new people.

The **Normalize Fields** code node deliberately mirrors
`find_column()` in `scripts/clean_data.py`, so a CSV with any of the
3 known header styles (`Full Name` / `full_name` / `worker_name`,
etc.) is recognized the same way the batch pipeline recognizes it —
this flow isn't a separate, disconnected demo, it uses the same
matching assumptions as Task 1.

`n8n/skill_classifier.py` is a bonus, not a second Task 2 submission:
it's a plain-Python skill-tagging function written so it can be
pasted directly into an n8n Code node (Pyodide can't `import` a repo
file at runtime), or run standalone for testing
(`python3 n8n/skill_classifier.py`). The one required, graded Task 2
flow is the duplicate-alert workflow above.

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
data/                    raw source CSVs
data/cleaned/             output of clean_data.py
data/matched/             output of match_people.py
database/schema.sql      Postgres schema (persons, source_records, audio_submissions)
scripts/
  clean_data.py           Task 1 step 1 - cleaning
  match_people.py         Task 1 step 2 - entity matching / dedup
  build_persons.py        Task 1 step 3a - collapse matched rows -> one canonical row/person
  ingest_to_db.py          Task 1 step 3b - writes persons/source_records to Postgres
  inspect_data.py         dev utility - prints column/dtype/null/duplicate stats per raw file
  test.py                 dev utility - quick "can I connect to Postgres" check
backend/                  Flask app for audio submissions (Task 3)
  app.py                   routes
  database.py              Postgres access
  audio_processor.py       audio analysis (pydub/ffmpeg)
  models.py                Person / AudioSubmission data shapes
  uploads/                 saved audio files (created at runtime)
frontend/
  index.html               submission form (record in-browser or upload + submit)
  submissions.html          list view: play button + extracted properties per submission
n8n/
  duplicate_alert_workflow.json   Task 2 - the graded automation (see above)
  skill_classifier.py             bonus helper, not the Task 2 submission (see above)
reports/data_quality.py   Task 4 support - automated pipeline health report
DATA_ISSUES.md             Task 4 - data problems found and how each was handled
STRETCH.md                 Task 5 - scaling to 5,000 workers over a weekend
```

## Known gotchas already fixed here

- `ingest_to_db.py` used to crash with `can't adapt type 'NAType'`
  on any row with a missing phone number (30 of the 102 rows have
  no phone, e.g. all `gig_workers` rows) because pandas' nullable
  `"string"` dtype uses `pd.NA` instead of `None`, which psycopg2
  can't insert directly. Fixed by converting `pd.NA`/`NaN` to
  `None` before hitting the DB.
- `clean_data.py`, `match_people.py`, and `build_persons.py`'s
  standalone mode had the previous developer's absolute Windows path
  (`C:\Users\Lenovo\Desktop\consultbae_updated\...`) hardcoded as the
  input/output directory, so they only ever worked on that one
  machine — anyone else running `python3 scripts/clean_data.py` got
  `No CSV files found in the data directory` and a stray literally
  -named folder created in their working directory. Fixed by
  switching all three to the relative `data` / `data/cleaned` /
  `data/matched` paths that `ingest_to_db.py` and `reports/
  data_quality.py` already used, so the whole pipeline now runs the
  same way from any checkout as long as you're in the project root.

## Stuck log

### 1. `psycopg2` crashing on missing phone numbers with `can't adapt type 'NAType'`

The first real end-to-end run of `ingest_to_db.py` against a live
Postgres instance crashed immediately, every time, on the
`INSERT INTO persons ...` for any row missing a phone number — 30 of
the 102 raw rows (all of `source2_gig_workers.csv`) have none.

The error, `can't adapt type 'NAType'`, doesn't mention pandas or
`NaN` anywhere, so the first instinct was to assume a schema mismatch
(wrong column type in `schema.sql`). Checked that first — it wasn't
it, `phone TEXT` accepts `NULL` fine from `psql` directly.

Searched the exact error string, which surfaced that this is
pandas' *nullable* `"string"` dtype specifically — `pd.NA` is a
distinct sentinel object from Python's `None` and from `float('nan')`,
and psycopg2's adapter registry only knows how to convert the latter
two. That dtype was chosen deliberately (`dtype={"phone": "string"}`
in `build_persons.py`) to stop phone numbers from being silently
upcast to `float64` and printed as `"9000000254.0"` — so the fix
couldn't be "stop using the nullable dtype," that would reintroduce a
worse bug.

Asked an AI assistant for the cleanest fix. It suggested
`df.where(pd.notna(df), None)` as a one-liner over the whole
dataframe right before the insert loop. Rejected the tempting
alternative of just adding a fallback in the SQL (`INSERT ...
COALESCE(%s, NULL)`) — that treats the symptom at every call site
instead of once, and doesn't fix the underlying "pandas NA leaking
into a DB boundary" problem, so the next person who adds a new
column with missing values hits the same crash again. Fixed it once,
centrally, in `_clean_for_db()`, applied to the whole dataframe rather
than just the phone column defensively.

### 2. Entity matching with no common ID field

Task 1 explicitly has no shared key across the 3 files, so the
question was how confident to be before merging two rows into one
person — too strict and real duplicates stay split (bad: undercounts
unique people, and the audio app in Task 3 would create a *second*
person record for someone who already exists); too loose and
unrelated people get merged (worse: someone's audio submission lands
on a stranger's record).

Started by asking an AI assistant to "write a fuzzy matcher for these
3 CSVs." It came back with a single global similarity score blending
name+email+phone+city into one fuzzy number with one threshold.
Rejected that shape: it made *why* two rows merged unrecoverable — a
0.71-confidence match tells you nothing about whether it was the
email or the city that tipped it over, which matters a lot when
auditing 60 merge decisions by hand to sanity-check them. Rebuilt it
as tiered instead — exact email match first (highest confidence, no
fuzziness involved), then exact phone, then fuzzy name (via
`rapidfuzz`) with an explicit same-city bonus, and an explicit numeric
floor (`score >= 50`) below which nothing merges — and made every
match record its own `match_reason` string, specifically so a
suspicious merge could be traced back to exactly which signal caused
it. Caught the two `DUPLICATE_WITHIN_SOURCE` cases (issue #8 in
`DATA_ISSUES.md`) this way — they wouldn't have stood out in a single
opaque score.

### 3. Pipeline only worked on one machine

After the pipeline was "done" and committed, re-running it fresh (to
double check the 60-persons number for this README) failed instantly
with `No CSV files found in the data directory` — despite the CSVs
being right there in `data/`. `clean_data.py`, `match_people.py`, and
`build_persons.py` all had an absolute Windows path
(`C:\Users\Lenovo\Desktop\consultbae_updated\consultbae\data`)
hardcoded as `INPUT_DIR`/`OUTPUT_DIR`, left over from wherever they
were first written — on Linux that string isn't a path at all, it's
just a filename with backslashes in it, so `Path.glob("*.csv")`
against it found nothing, and `.mkdir(parents=True)` on the output
side created one bizarre folder literally named with backslashes in
the current directory instead of the intended `data/cleaned`.

This was found by actually re-running the scripts from a clean
checkout rather than trusting that "it worked before" — the kind of
bug that's invisible if you only ever run code on the machine you
wrote it on. Fixed by switching all three to the same relative-path
pattern `ingest_to_db.py` already used correctly
(`Path("data")`, `Path("data/cleaned")`, `Path("data/matched")`),
which works from any checkout as long as you run scripts from the
project root — and re-ran the full pipeline afterward to confirm the
"60 unique persons from 102 raw rows" number in this README is still
accurate post-fix, not just copied from an old run.