"""Shared types exchanged between pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import numpy as np


@dataclass(frozen=True)
class Frame:
    camera_id: str
    captured_at: datetime  # timezone-aware UTC
    image: np.ndarray  # HxWx3 BGR


@dataclass(frozen=True)
class Detection:
    camera_id: str
    captured_at: datetime
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2 in pixels
    score: float


@dataclass
class Track:
    camera_id: str
    track_id: int
    detections: list[Detection] = field(default_factory=list)


@dataclass(frozen=True)
class HelmetVerdict:
    track: Track
    has_helmet: bool
    confidence: float


@dataclass(frozen=True)
class Incident:
    incident_id: str
    camera_ids: tuple[str, ...]
    first_seen: datetime
    last_seen: datetime
    zone: str | None = None
    snapshot_ref: str | None = None
    clip_ref: str | None = None
