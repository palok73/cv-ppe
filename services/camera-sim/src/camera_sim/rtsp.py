"""ffmpeg-backed RTSP endpoint that mimics a Hikvision camera's per-channel streams.

Real Hikvision cameras are RTSP *servers*: an NVR/VMS pulls
``rtsp://<camera>/Streaming/Channels/101`` (main stream) and ``.../102`` (sub
stream). ``mode: listen`` below reproduces that pull model using ffmpeg's RTSP
muxer with ``-rtsp_flags listen``. ``mode: publish`` instead pushes into an
RTSP URL you already run (e.g. MediaMTX) for setups that need a push model.

Looping: "sequential" order plays the clip list on an infinite loop inside a
single long-lived ffmpeg process (seamless, no reconnects). "random" order
shuffles the clip list, plays it through once, then reshuffles and restarts
ffmpeg for the next pass -- clients relying on `mode: listen` will see a brief
reconnect at each pass boundary, which is an accepted trade-off for true
per-pass randomization.
"""

from __future__ import annotations

import logging
import random
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from .config import StreamConfig
from .playlist import list_clips, order_clips, write_concat_playlist

logger = logging.getLogger(__name__)


def build_ffmpeg_args(
    playlist_path: Path,
    stream: StreamConfig,
    *,
    loop_forever: bool,
    ffmpeg_bin: str = "ffmpeg",
) -> list[str]:
    args = [ffmpeg_bin, "-nostdin", "-hide_banner", "-loglevel", "warning", "-re"]
    if loop_forever:
        args += ["-stream_loop", "-1"]
    args += ["-f", "concat", "-safe", "0", "-i", str(playlist_path)]

    if stream.resolution:
        scale = stream.resolution.replace("x", ":")
        args += ["-vf", f"scale={scale}", "-c:v", "libx264", "-preset", "veryfast"]
        if stream.bitrate_kbps:
            args += ["-b:v", f"{stream.bitrate_kbps}k"]
    else:
        args += ["-c", "copy"]

    args += ["-f", "rtsp"]
    if stream.mode == "listen":
        args += ["-rtsp_flags", "listen"]
        target = f"rtsp://{stream.bind_host}:{stream.bind_port}{stream.path}"
    else:
        target = stream.target_url
    args.append(target)
    return args


@dataclass
class StreamRunner:
    camera_id: str
    stream_name: str
    clips_dir: Path
    order: str
    stream: StreamConfig
    work_dir: Path
    ffmpeg_bin: str = "ffmpeg"
    rng: random.Random | None = None

    def _playlist_path(self) -> Path:
        return self.work_dir / f"{self.camera_id}-{self.stream_name}.ffconcat"

    def run_forever(self, stop_event: Event) -> None:
        clips = list_clips(self.clips_dir)
        backoff = 1.0
        while not stop_event.is_set():
            ordered = order_clips(clips, self.order, self.rng)
            playlist = write_concat_playlist(ordered, self._playlist_path())
            loop_forever = self.order == "sequential"
            args = build_ffmpeg_args(
                playlist, self.stream, loop_forever=loop_forever, ffmpeg_bin=self.ffmpeg_bin
            )
            logger.info("starting %s/%s: %s", self.camera_id, self.stream_name, " ".join(args))
            started_at = time.monotonic()
            proc = subprocess.Popen(args)
            try:
                while proc.poll() is None and not stop_event.is_set():
                    time.sleep(0.5)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
            if stop_event.is_set():
                return
            ran_for = time.monotonic() - started_at
            backoff = 1.0 if ran_for > 10 else min(backoff * 2, 30.0)
            logger.warning(
                "%s/%s ffmpeg exited after %.1fs, restarting in %.1fs",
                self.camera_id,
                self.stream_name,
                ran_for,
                backoff,
            )
            stop_event.wait(backoff)
