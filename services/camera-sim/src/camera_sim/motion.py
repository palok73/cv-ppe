"""Drives one camera's simulated motion trigger across its enabled channels.

Each motion "burst" fires an active event, holds for `active_duration_seconds`,
then fires an inactive event, on both the Hikvision ISAPI channel and the
ONVIF channel if enabled -- mirroring how a real camera would raise the same
physical motion event on every notification mechanism it has configured.
"""

from __future__ import annotations

import logging
import random
import threading
from collections.abc import Callable
from dataclasses import dataclass

import requests

from . import hikvision_motion, onvif_motion
from .config import MotionConfig

logger = logging.getLogger(__name__)


@dataclass
class MotionRunner:
    camera_id: str
    channel: int
    config: MotionConfig
    snapshot_provider: Callable[[], bytes | None] | None = None
    rng: random.Random | None = None
    post: Callable = requests.post

    def _next_interval(self) -> float:
        lo, hi = self.config.interval_seconds
        rng = self.rng or random
        return rng.uniform(lo, hi)

    def _fire_hikvision(
        self, event_state: str, active_post_count: int, snapshot: bytes | None
    ) -> None:
        cfg = self.config.hikvision
        xml_body = hikvision_motion.build_event_xml(
            xml_version=cfg.xml_version,
            channel=self.channel,
            event_state=event_state,
            ip_address=cfg.device_ip,
            port=cfg.device_port,
            mac_address=cfg.device_mac,
            protocol=cfg.protocol,
            active_post_count=active_post_count,
        )
        hikvision_motion.send_event(
            cfg.target_url,
            xml_body,
            snapshot_jpeg=snapshot if event_state == "active" else None,
            post=self.post,
        )

    def _fire_onvif(self, motion_active: bool) -> None:
        cfg = self.config.onvif
        envelope = onvif_motion.build_notify_envelope(
            motion_active=motion_active,
            producer_address=cfg.producer_address,
            video_source_token=cfg.video_source_token,
        )
        onvif_motion.send_notify(cfg.target_url, envelope, post=self.post)

    def _fire(self, event_state: str, active_post_count: int, snapshot: bytes | None) -> None:
        if "hikvision" in self.config.channels:
            try:
                self._fire_hikvision(event_state, active_post_count, snapshot)
            except Exception:
                logger.exception("hikvision motion POST failed for %s", self.camera_id)
        if "onvif" in self.config.channels:
            try:
                self._fire_onvif(event_state == "active")
            except Exception:
                logger.exception("onvif motion notify failed for %s", self.camera_id)

    def run_forever(self, stop_event: threading.Event) -> None:
        active_post_count = 0
        while not stop_event.wait(self._next_interval()):
            active_post_count += 1
            snapshot = None
            if "hikvision" in self.config.channels and self.config.hikvision.include_snapshot:
                snapshot = self.snapshot_provider() if self.snapshot_provider else None
            logger.info("%s: motion active", self.camera_id)
            self._fire("active", active_post_count, snapshot)
            if stop_event.wait(self.config.active_duration_seconds):
                return
            logger.info("%s: motion inactive", self.camera_id)
            self._fire("inactive", active_post_count, None)
