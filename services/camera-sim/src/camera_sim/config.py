"""Config schema and YAML loading for the camera simulator service."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

VALID_ORDERS = ("sequential", "random")
VALID_STREAM_MODES = ("listen", "publish")
VALID_MOTION_CHANNELS = ("hikvision", "onvif")


@dataclass
class StreamConfig:
    mode: str = "listen"
    bind_host: str = "0.0.0.0"
    bind_port: int = 8554
    path: str = "/Streaming/Channels/101"
    target_url: str | None = None
    resolution: str | None = None
    bitrate_kbps: int | None = None

    def __post_init__(self) -> None:
        if self.mode not in VALID_STREAM_MODES:
            raise ValueError(f"unknown stream mode: {self.mode!r}")
        if self.mode == "publish" and not self.target_url:
            raise ValueError("stream mode 'publish' requires target_url")


@dataclass
class HikvisionMotionConfig:
    target_url: str = ""
    include_snapshot: bool = False
    xml_version: str = "1.0"
    device_ip: str = "192.168.1.100"
    device_port: int = 80
    device_mac: str = "00:00:00:00:00:00"
    protocol: str = "HTTP"


@dataclass
class OnvifMotionConfig:
    target_url: str = ""
    producer_address: str = "http://192.168.1.100/onvif/device_service"
    video_source_token: str = "VideoSourceToken"


@dataclass
class MotionConfig:
    enabled: bool = False
    channels: list[str] = field(default_factory=lambda: ["hikvision"])
    interval_seconds: tuple[float, float] = (30.0, 30.0)
    active_duration_seconds: float = 3.0
    hikvision: HikvisionMotionConfig = field(default_factory=HikvisionMotionConfig)
    onvif: OnvifMotionConfig = field(default_factory=OnvifMotionConfig)

    def __post_init__(self) -> None:
        if isinstance(self.interval_seconds, (int, float)):
            self.interval_seconds = (float(self.interval_seconds), float(self.interval_seconds))
        else:
            lo, hi = self.interval_seconds
            self.interval_seconds = (float(lo), float(hi))
        if not self.enabled:
            return
        for channel in self.channels:
            if channel not in VALID_MOTION_CHANNELS:
                raise ValueError(f"unknown motion channel: {channel!r}")
        if "hikvision" in self.channels and not self.hikvision.target_url:
            raise ValueError("motion channel 'hikvision' requires hikvision.target_url")
        if "onvif" in self.channels and not self.onvif.target_url:
            raise ValueError("motion channel 'onvif' requires onvif.target_url")


@dataclass
class CameraConfig:
    id: str
    clips_dir: Path
    channel: int = 1
    order: str = "sequential"
    streams: dict[str, StreamConfig] = field(default_factory=dict)
    motion: MotionConfig = field(default_factory=MotionConfig)

    def __post_init__(self) -> None:
        self.clips_dir = Path(self.clips_dir)
        if self.order not in VALID_ORDERS:
            raise ValueError(f"camera {self.id}: unknown order {self.order!r}")
        if not self.streams:
            raise ValueError(f"camera {self.id}: at least one stream must be configured")


@dataclass
class SimulatorConfig:
    cameras: list[CameraConfig]


def _build_stream(data: dict) -> StreamConfig:
    return StreamConfig(**data)


def _build_motion(data: dict | None) -> MotionConfig:
    data = dict(data or {})
    hikvision_data = data.pop("hikvision", None)
    onvif_data = data.pop("onvif", None)
    return MotionConfig(
        hikvision=HikvisionMotionConfig(**(hikvision_data or {})),
        onvif=OnvifMotionConfig(**(onvif_data or {})),
        **data,
    )


def _build_camera(data: dict) -> CameraConfig:
    streams = {
        name: _build_stream(stream_data) for name, stream_data in data.get("streams", {}).items()
    }
    return CameraConfig(
        id=data["id"],
        clips_dir=data["clips_dir"],
        channel=data.get("channel", 1),
        order=data.get("order", "sequential"),
        streams=streams,
        motion=_build_motion(data.get("motion")),
    )


def load_config(path: str | Path) -> SimulatorConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    cameras = [_build_camera(cam) for cam in (raw or {}).get("cameras", [])]
    if not cameras:
        raise ValueError("config must define at least one camera")
    return SimulatorConfig(cameras=cameras)
