"""Extracts a JPEG still from a local clip, to embed in simulated motion events."""

from __future__ import annotations

import logging
import random
import subprocess
from pathlib import Path

from .playlist import list_clips

logger = logging.getLogger(__name__)


def grab_snapshot(
    clips_dir: Path, *, ffmpeg_bin: str = "ffmpeg", rng: random.Random | None = None
) -> bytes | None:
    try:
        clips = list_clips(clips_dir)
    except (FileNotFoundError, ValueError):
        return None
    clip = (rng or random).choice(clips)
    try:
        result = subprocess.run(
            [
                ffmpeg_bin,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(clip),
                "-frames:v",
                "1",
                "-f",
                "image2pipe",
                "-vcodec",
                "mjpeg",
                "-",
            ],
            capture_output=True,
            timeout=10,
            check=True,
        )
        return result.stdout or None
    except (OSError, subprocess.SubprocessError):
        logger.warning("snapshot extraction failed for %s", clip, exc_info=True)
        return None
