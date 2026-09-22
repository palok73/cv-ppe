"""Helmet / no-helmet classification with temporal smoothing (N of M frames)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import cv2
import numpy as np

from ppe_monitor.ppe.detector import HelmetDetector
from ppe_monitor.types import Frame, HelmetVerdict, Track


@dataclass(frozen=True)
class PPEConfig:
    """Thresholds for the helmet check — come from config, never hard-coded inline."""

    detection_threshold: float = 0.5
    min_conclusive_frames: int = 1


def _crop_rgb(frame: Frame, bbox: tuple[float, float, float, float]) -> np.ndarray:
    height, width = frame.image.shape[:2]
    x1, x2 = sorted(round(v) for v in (bbox[0], bbox[2]))
    y1, y2 = sorted(round(v) for v in (bbox[1], bbox[3]))
    x1, x2 = max(0, min(x1, width)), max(0, min(x2, width))
    y1, y2 = max(0, min(y1, height)), max(0, min(y2, height))
    return cv2.cvtColor(frame.image[y1:y2, x1:x2], cv2.COLOR_BGR2RGB)


def check_helmet(
    track: Track,
    frames: dict[tuple[str, datetime], Frame],
    detector: HelmetDetector,
    config: PPEConfig | None = None,
) -> HelmetVerdict:
    """Classify a track as helmeted using majority vote over its detections' frames.

    `frames` maps (camera_id, captured_at) -> Frame: Detection carries a bbox but not pixels,
    so the caller supplies the frames the track was built from. Detections with no matching
    frame, an empty crop, or no model output are skipped rather than voted as "no helmet" —
    absence of evidence isn't evidence of absence. If too few detections are conclusive
    (< min_conclusive_frames), the verdict defaults to has_helmet=False, confidence=0.0: a
    safety monitor should fail toward flagging for review, not toward silently passing.
    """
    config = config or PPEConfig()
    votes: list[bool] = []
    confidences: list[float] = []
    for detection in track.detections:
        frame = frames.get((detection.camera_id, detection.captured_at))
        if frame is None:
            continue
        crop = _crop_rgb(frame, detection.bbox)
        if crop.size == 0:
            continue
        found = detector.detect(crop, threshold=config.detection_threshold)
        if not found:
            continue
        best = max(found, key=lambda d: d.confidence)
        votes.append(best.has_helmet)
        confidences.append(best.confidence)

    if len(votes) < config.min_conclusive_frames:
        return HelmetVerdict(track=track, has_helmet=False, confidence=0.0)

    has_helmet = sum(votes) * 2 > len(votes)
    agreeing = [c for vote, c in zip(votes, confidences) if vote == has_helmet]
    return HelmetVerdict(
        track=track, has_helmet=has_helmet, confidence=sum(agreeing) / len(agreeing)
    )
