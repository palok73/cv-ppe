import random
from pathlib import Path

import pytest

from camera_sim.playlist import list_clips, order_clips, write_concat_playlist


def _touch(path: Path) -> Path:
    path.write_bytes(b"")
    return path


def test_list_clips_filters_by_extension_and_sorts(tmp_path):
    _touch(tmp_path / "b.mp4")
    _touch(tmp_path / "a.mov")
    _touch(tmp_path / "notes.txt")
    _touch(tmp_path / "c.MKV")

    clips = list_clips(tmp_path)

    assert [p.name for p in clips] == ["a.mov", "b.mp4", "c.MKV"]


def test_list_clips_missing_dir_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        list_clips(tmp_path / "does-not-exist")


def test_list_clips_empty_dir_raises(tmp_path):
    with pytest.raises(ValueError):
        list_clips(tmp_path)


def test_order_clips_sequential_preserves_order():
    clips = [Path("a.mp4"), Path("b.mp4"), Path("c.mp4")]
    assert order_clips(clips, "sequential") == clips


def test_order_clips_random_is_a_permutation_and_seedable():
    clips = [Path(f"{i}.mp4") for i in range(10)]
    shuffled = order_clips(clips, "random", rng=random.Random(42))
    assert sorted(shuffled) == sorted(clips)
    assert shuffled == order_clips(clips, "random", rng=random.Random(42))


def test_order_clips_unknown_mode_raises():
    with pytest.raises(ValueError):
        order_clips([Path("a.mp4")], "shuffle-please")


def test_write_concat_playlist_format(tmp_path):
    clip = _touch(tmp_path / "clip.mp4")
    playlist_path = tmp_path / "playlist.ffconcat"

    write_concat_playlist([clip], playlist_path)

    content = playlist_path.read_text(encoding="utf-8")
    assert content.startswith("ffconcat version 1.0\n")
    assert f"file '{clip.resolve()}'\n" in content


def test_write_concat_playlist_escapes_single_quotes(tmp_path):
    # ffmpeg's own quoting rules (shared with the concat demuxer) require a
    # literal `'` inside a single-quoted value to be written as `'\''`.
    clip = _touch(tmp_path / "clip's.mp4")
    playlist_path = tmp_path / "playlist.ffconcat"

    write_concat_playlist([clip], playlist_path)

    content = playlist_path.read_text(encoding="utf-8")
    assert r"clip'\''s.mp4" in content
