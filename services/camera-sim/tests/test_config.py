from pathlib import Path

import pytest

from camera_sim.config import load_config

BASE_YAML = """
cameras:
  - id: cam1
    clips_dir: {clips_dir}
    channel: 1
    order: {order}
    streams:
      main:
        mode: listen
        bind_host: 0.0.0.0
        bind_port: 8554
        path: /Streaming/Channels/101
    motion:
      enabled: {motion_enabled}
      channels: [hikvision]
      hikvision:
        target_url: "http://127.0.0.1:9000/hik"
"""


def _write(tmp_path: Path, text: str) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(text, encoding="utf-8")
    return config_path


def test_load_config_happy_path(tmp_path):
    config_path = _write(
        tmp_path,
        BASE_YAML.format(clips_dir=tmp_path, order="sequential", motion_enabled="true"),
    )

    cfg = load_config(config_path)

    assert len(cfg.cameras) == 1
    camera = cfg.cameras[0]
    assert camera.id == "cam1"
    assert camera.order == "sequential"
    assert camera.streams["main"].bind_port == 8554
    assert camera.motion.enabled is True
    assert camera.motion.hikvision.target_url == "http://127.0.0.1:9000/hik"


def test_load_config_no_cameras_raises(tmp_path):
    config_path = _write(tmp_path, "cameras: []\n")
    with pytest.raises(ValueError, match="at least one camera"):
        load_config(config_path)


def test_load_config_unknown_order_raises(tmp_path):
    config_path = _write(
        tmp_path,
        BASE_YAML.format(clips_dir=tmp_path, order="shuffled", motion_enabled="false"),
    )
    with pytest.raises(ValueError, match="unknown order"):
        load_config(config_path)


def test_publish_stream_requires_target_url(tmp_path):
    text = BASE_YAML.format(clips_dir=tmp_path, order="sequential", motion_enabled="false")
    text = text.replace("mode: listen", "mode: publish")
    config_path = _write(tmp_path, text)
    with pytest.raises(ValueError, match="target_url"):
        load_config(config_path)


def test_motion_enabled_without_target_url_raises(tmp_path):
    text = BASE_YAML.format(clips_dir=tmp_path, order="sequential", motion_enabled="true")
    text = text.replace('target_url: "http://127.0.0.1:9000/hik"', "")
    config_path = _write(tmp_path, text)
    with pytest.raises(ValueError, match="hikvision.target_url"):
        load_config(config_path)


def test_interval_seconds_accepts_scalar_or_range(tmp_path):
    text = BASE_YAML.format(clips_dir=tmp_path, order="sequential", motion_enabled="true")
    text = text.replace(
        "channels: [hikvision]", "channels: [hikvision]\n      interval_seconds: 10"
    )
    config_path = _write(tmp_path, text)
    cfg = load_config(config_path)
    assert cfg.cameras[0].motion.interval_seconds == (10.0, 10.0)
