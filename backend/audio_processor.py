import os
from pydub import AudioSegment

_CHUNK_MS = 100 # 100ms analysis window for loudness/noise measurement.

_NOISY_GAP_DB = 40.0

_SILENCE_FLOOR_DB = -90.0


def process_audio(file_path):
   
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