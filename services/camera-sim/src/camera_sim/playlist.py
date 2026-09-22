"""Builds ffmpeg concat playlists from a directory of local clip files."""

from __future__ import annotations

import random
from pathlib import Path

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".ts"}


def list_clips(clips_dir: Path) -> list[Path]:
    if not clips_dir.is_dir():
        raise FileNotFoundError(f"clips directory not found: {clips_dir}")
    clips = sorted(p for p in clips_dir.iterdir() if p.suffix.lower() in VIDEO_EXTENSIONS)
    if not clips:
        raise ValueError(f"no video clips found in {clips_dir}")
    return clips


def order_clips(clips: list[Path], order: str, rng: random.Random | None = None) -> list[Path]:
    if order == "sequential":
        return list(clips)
    if order == "random":
        rng = rng or random.Random()
        shuffled = list(clips)
        rng.shuffle(shuffled)
        return shuffled
    raise ValueError(f"unknown order mode: {order!r}")


def write_concat_playlist(clips: list[Path], playlist_path: Path) -> Path:
    """Writes an ffconcat file ffmpeg's concat demuxer can loop over."""
    lines = ["ffconcat version 1.0"]
    for clip in clips:
        escaped = str(clip.resolve()).replace("'", r"'\''")
        lines.append(f"file '{escaped}'")
    playlist_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return playlist_path
