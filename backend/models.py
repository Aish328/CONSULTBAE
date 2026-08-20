
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Person:
    id: Optional[int]
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row):
        """row: (id, name, email, phone, created_at, updated_at)"""
        if row is None:
            return None
        return cls(
            id=row[0],
            name=row[1],
            email=row[2],
            phone=row[3],
            created_at=row[4],
            updated_at=row[5],
        )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
        }


@dataclass
class AudioSubmission:
    id: Optional[int]
    person_id: int
    audio_path: str
    duration_seconds: Optional[float] = None
    sample_rate_khz: Optional[float] = None
    bitrate_kbps: Optional[float] = None
    loudness_db: Optional[float] = None
    noise_score: Optional[float] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row):
        
        if row is None:
            return None
        return cls(
            id=row[0],
            person_id=row[1],
            audio_path=row[2],
            duration_seconds=row[3],
            sample_rate_khz=row[4],
            bitrate_kbps=row[5],
            loudness_db=row[6],
            noise_score=row[7],
            created_at=row[8],
        )

    def to_dict(self):
        return {
            "id": self.id,
            "person_id": self.person_id,
            "audio_path": self.audio_path,
            "duration_seconds": self.duration_seconds,
            "sample_rate_khz": self.sample_rate_khz,
            "bitrate_kbps": self.bitrate_kbps,
            "loudness_db": self.loudness_db,
            "noise_score": self.noise_score,
        }