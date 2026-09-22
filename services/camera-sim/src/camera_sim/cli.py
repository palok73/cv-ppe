"""Entry point: `camera-sim run --config config.yaml`."""

from __future__ import annotations

import argparse
import functools
import logging
import signal
import tempfile
import threading
from pathlib import Path

from .config import CameraConfig, load_config
from .motion import MotionRunner
from .rtsp import StreamRunner
from .snapshot import grab_snapshot

logger = logging.getLogger(__name__)


def run(config_path: str) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    cfg = load_config(config_path)
    stop_event = threading.Event()

    def handle_signal(signum, _frame):
        logger.info("received signal %s, shutting down", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    threads: list[threading.Thread] = []
    with tempfile.TemporaryDirectory(prefix="camera-sim-") as work_dir:
        for camera in cfg.cameras:
            threads += _start_camera(camera, Path(work_dir), stop_event)

        stop_event.wait()
        for t in threads:
            t.join(timeout=10)


def _start_camera(
    camera: CameraConfig, work_dir: Path, stop_event: threading.Event
) -> list[threading.Thread]:
    threads: list[threading.Thread] = []
    for stream_name, stream in camera.streams.items():
        runner = StreamRunner(
            camera_id=camera.id,
            stream_name=stream_name,
            clips_dir=camera.clips_dir,
            order=camera.order,
            stream=stream,
            work_dir=work_dir,
        )
        t = threading.Thread(target=runner.run_forever, args=(stop_event,), daemon=True)
        t.start()
        threads.append(t)

    if camera.motion.enabled:
        snapshot_provider = functools.partial(grab_snapshot, camera.clips_dir)
        motion_runner = MotionRunner(
            camera_id=camera.id,
            channel=camera.channel,
            config=camera.motion,
            snapshot_provider=snapshot_provider,
        )
        t = threading.Thread(target=motion_runner.run_forever, args=(stop_event,), daemon=True)
        t.start()
        threads.append(t)

    return threads


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="camera-sim", description="Simulate Hikvision-style IP cameras for testing."
    )
    parser.add_argument("command", choices=["run"])
    parser.add_argument("--config", required=True, help="Path to a simulator config YAML file.")
    args = parser.parse_args()
    if args.command == "run":
        run(args.config)


if __name__ == "__main__":
    main()
