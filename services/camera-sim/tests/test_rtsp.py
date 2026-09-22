from pathlib import Path

import pytest

from camera_sim.config import StreamConfig
from camera_sim.rtsp import build_ffmpeg_args


def test_listen_mode_builds_rtsp_url_from_bind_host_and_path():
    stream = StreamConfig(
        mode="listen", bind_host="0.0.0.0", bind_port=8554, path="/Streaming/Channels/101"
    )

    args = build_ffmpeg_args(Path("playlist.ffconcat"), stream, loop_forever=True)

    assert args[0] == "ffmpeg"
    assert "-rtsp_flags" in args
    assert args[args.index("-rtsp_flags") + 1] == "listen"
    assert args[-1] == "rtsp://0.0.0.0:8554/Streaming/Channels/101"
    assert "-stream_loop" in args
    assert "-c" in args and args[args.index("-c") + 1] == "copy"


def test_publish_mode_targets_configured_url():
    stream = StreamConfig(mode="publish", target_url="rtsp://media-server:8554/cam1")

    args = build_ffmpeg_args(Path("playlist.ffconcat"), stream, loop_forever=False)

    assert args[-1] == "rtsp://media-server:8554/cam1"
    assert "-rtsp_flags" not in args
    assert "-stream_loop" not in args


def test_resolution_triggers_reencode_with_scale_filter():
    stream = StreamConfig(resolution="640x360", bitrate_kbps=512)

    args = build_ffmpeg_args(Path("playlist.ffconcat"), stream, loop_forever=True)

    assert "-vf" in args
    assert args[args.index("-vf") + 1] == "scale=640:360"
    assert "-c:v" in args and args[args.index("-c:v") + 1] == "libx264"
    assert "-b:v" in args and args[args.index("-b:v") + 1] == "512k"
    assert "-c" not in args


def test_no_resolution_uses_stream_copy():
    stream = StreamConfig()

    args = build_ffmpeg_args(Path("playlist.ffconcat"), stream, loop_forever=True)

    assert "-vf" not in args
    assert "-c" in args and args[args.index("-c") + 1] == "copy"


def test_publish_without_target_url_rejected_at_config_time():
    with pytest.raises(ValueError, match="target_url"):
        StreamConfig(mode="publish")
