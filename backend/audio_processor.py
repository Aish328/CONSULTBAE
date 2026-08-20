"""
Extracts the metrics stored in audio_submissions:
    duration_seconds, sample_rate_khz, bitrate_kbps,
    loudness_db, noise_score

Uses pydub (which shells out to ffmpeg), so this works on whatever
format someone uploads -- mp3, wav, m4a, etc. -- not just wav.

NOTE ON noise_score:
There's no single industry-standard "noise score" for a short
uploaded clip, so this is a documented heuristic, not a scientific
measurement:

    noise_score = loudest_100ms - quietest_100ms   (in dB, clamped >= 0)

The idea: a clean recording has a big gap between speech (loud) and
background silence (quiet). A noisy recording has a small gap,
because the "quiet" parts are polluted by hiss/hum/traffic/etc. and
aren't actually quiet. We scale this gap into a 0-100 score where
HIGHER = NOISIER (0 = perfectly clean, 100 = no discernible
difference between speech and background, i.e. very noisy), because
that reads naturally in a dashboard ("noise_score: 82" jumps out as
bad without needing to remember which direction is good).

This is intentionally simple and should be treated as a rough
triage signal (e.g. "flag anything above 60 for manual review"),
not a precise acoustic measurement. If more accuracy is needed
later, swap this out for a proper library (e.g. a spectral noise
estimate via librosa) without touching app.py -- process_audio()
is the only function callers depend on.
"""

import os

from pydub import AudioSegment

# 100ms analysis window for loudness/noise measurement.
_CHUNK_MS = 100

# dB gap at/above which we consider a clip "very noisy" for the
# purposes of scaling into a 0-100 score.
_NOISY_GAP_DB = 40.0

# Floor used in place of true digital silence (-inf dBFS). Without
# this, a genuinely silent gap gets excluded from the min/max
# calculation entirely -- which paradoxically makes a CLEAN clip
# (with real silence) look identical to a NOISY one (all chunks
# non-silent), because the true silence never gets to pull the
# "quietest" value down. Treating -inf as "very quiet" instead of
# "no data" fixes this.
_SILENCE_FLOOR_DB = -90.0


def process_audio(file_path):
    """
    Returns a dict with duration_seconds, sample_rate_khz,
    bitrate_kbps, loudness_db, noise_score. Raises ValueError if the
    file can't be read/decoded (caller should turn that into a 400).
    """
    try:
        audio = AudioSegment.from_file(file_path)
    except Exception as exc:
        raise ValueError(f"Could not decode audio file: {exc}") from exc

    duration_seconds = round(len(audio) / 1000.0, 3)
    sample_rate_khz = round(audio.frame_rate / 1000.0, 3)

    file_size_bits = os.path.getsize(file_path) * 8
    bitrate_kbps = (
        round((file_size_bits / duration_seconds) / 1000.0, 1)
        if duration_seconds > 0
        else None
    )

    loudness_db = round(audio.dBFS, 2) if audio.dBFS != float("-inf") else None
    noise_score = _estimate_noise_score(audio)

    return {
        "duration_seconds": duration_seconds,
        "sample_rate_khz": sample_rate_khz,
        "bitrate_kbps": bitrate_kbps,
        "loudness_db": loudness_db,
        "noise_score": noise_score,
    }


def _estimate_noise_score(audio):
    """
    See module docstring for the method. Returns a float 0-100, or
    None if the clip is too short to analyze.
    """
    chunks = [
        audio[i : i + _CHUNK_MS]
        for i in range(0, len(audio), _CHUNK_MS)
        if len(audio[i : i + _CHUNK_MS]) == _CHUNK_MS
    ]

    if len(chunks) < 2:
        return None

    chunk_levels = [
        c.dBFS if c.dBFS != float("-inf") else _SILENCE_FLOOR_DB
        for c in chunks
    ]

    if len(chunk_levels) < 2:
        return None

    loudest = max(chunk_levels)
    quietest = min(chunk_levels)
    gap = max(loudest - quietest, 0.0)

    score = 100.0 * (1.0 - min(gap, _NOISY_GAP_DB) / _NOISY_GAP_DB)
    return round(score, 1)