CREATE TABLE IF NOT EXISTS persons (
    id SERIAL PRIMARY KEY,
    name TEXT,
    email TEXT,
    phone TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS source_records (
    id SERIAL PRIMARY KEY,
    person_id INTEGER REFERENCES persons(id),
    source_system TEXT NOT NULL,
    source_record_id TEXT,
    raw_name TEXT,
    raw_email TEXT,
    raw_phone TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE IF NOT EXISTS audio_submissions (
    id SERIAL PRIMARY KEY,
    person_id INTEGER REFERENCES persons(id),
    audio_path TEXT NOT NULL,
    duration_seconds NUMERIC,
    sample_rate_khz NUMERIC,
    bitrate_kbps NUMERIC,
    loudness_db NUMERIC,
    noise_score NUMERIC,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


CREATE INDEX IF NOT EXISTS idx_persons_email
ON persons(email);


CREATE INDEX IF NOT EXISTS idx_persons_phone
ON persons(phone);