from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AnalysisResult:
    file_path: str
    root_note: str | None
    key: str | None
    confidence: float
    category: str
    type: str
    duration: float
    sample_rate: int | None = None
    format: str | None = None
    scale_confidence: float = 0.0
    notes: list[str] = field(default_factory=list)
    chords: list[str] = field(default_factory=list)
    bpm: float | None = None
    rms_db: float | None = None
    peak_db: float | None = None
    dynamic_range_db: float | None = None
    spectral_centroid: float | None = None
    spectral_bandwidth: float | None = None
    rolloff: float | None = None
    fundamental_freq: float | None = None
    brightness: str | None = None
    warmth: str | None = None
    roughness: str | None = None
    mfcc: list[float] = field(default_factory=list)
    subtype: str | None = None
    source: str | None = None
    librosa_root: str | None = None
    librosa_root_confidence: float = 0.0
    librosa_key: str | None = None
    librosa_key_confidence: float = 0.0
    destination: str | None = None
    error: str | None = None
    size: int | None = None
    mtime: float | None = None

    def to_dict(self) -> dict[str, Any]:
        path = Path(self.file_path)
        return {
            "schema_version": 1,
            "file": {
                "path": self.file_path,
                "name": path.name,
                "format": self.format or path.suffix.lower().lstrip("."),
                "duration_sec": self.duration,
                "sample_rate": self.sample_rate,
                "size": self.size,
                "mtime": self.mtime,
            },
            "musical": {
                "root": self.root_note,
                "key": self.key,
                "scale_confidence": self.scale_confidence,
                "notes": self.notes,
                "chords": self.chords,
                "bpm": self.bpm,
            },
            "audio_features": {
                "loudness": {
                    "rms": self.rms_db,
                    "peak_db": self.peak_db,
                    "dynamic_range": self.dynamic_range_db,
                },
                "frequency": {
                    "spectral_centroid": self.spectral_centroid,
                    "spectral_bandwidth": self.spectral_bandwidth,
                    "rolloff": self.rolloff,
                    "fundamental_freq": self.fundamental_freq,
                },
                "timbre": {
                    "brightness": self.brightness,
                    "warmth": self.warmth,
                    "roughness": self.roughness,
                    "mfcc": self.mfcc,
                },
            },
            "classification": {
                "category": self.category,
                "type": self.type,
                "subtype": self.subtype,
                "source": self.source,
                "confidence": self.confidence,
            },
            "analysis": {
                "programs": {
                    "librosa": {
                        "root": self.librosa_root or self.root_note,
                        "root_confidence": self.librosa_root_confidence,
                        "key": self.librosa_key or self.key,
                        "key_confidence": self.librosa_key_confidence,
                    }
                },
                "final_decision": {
                    "root": self.root_note,
                    "key": self.key,
                    "confidence": self.confidence,
                },
            },
            "routing": {
                "destination": self.destination,
                "error": self.error,
            },
        }

    @property
    def key_or_root(self) -> str | None:
        return self.key or self.root_note


def file_signature(path: Path) -> dict[str, int | float]:
    stat = path.stat()
    return {"size": stat.st_size, "mtime": stat.st_mtime}
