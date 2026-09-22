import threading

from camera_sim.config import HikvisionMotionConfig, MotionConfig, OnvifMotionConfig
from camera_sim.motion import MotionRunner


class ZeroRng:
    """Fires immediately, so tests don't sleep for real intervals."""

    def uniform(self, lo, hi):
        return 0.0


def _config(channels, include_snapshot=False) -> MotionConfig:
    return MotionConfig(
        enabled=True,
        channels=channels,
        interval_seconds=(0.0, 0.0),
        active_duration_seconds=0.0,
        hikvision=HikvisionMotionConfig(
            target_url="http://example.invalid/hik", include_snapshot=include_snapshot
        ),
        onvif=OnvifMotionConfig(target_url="http://example.invalid/onvif"),
    )


def test_run_forever_fires_active_then_inactive_on_hikvision_channel():
    calls = []
    stop_event = threading.Event()

    def fake_post(url, data, headers, timeout):
        calls.append((url, headers["Content-Type"]))
        if len(calls) >= 2:
            stop_event.set()

    runner = MotionRunner(
        camera_id="cam1",
        channel=1,
        config=_config(["hikvision"]),
        rng=ZeroRng(),
        post=fake_post,
    )

    runner.run_forever(stop_event)

    assert len(calls) == 2
    assert all(url == "http://example.invalid/hik" for url, _ in calls)


def test_run_forever_fires_both_channels_per_state():
    calls = []
    stop_event = threading.Event()

    def fake_post(url, data, headers, timeout):
        calls.append(url)
        if len(calls) >= 4:  # 2 channels x (active, inactive)
            stop_event.set()

    runner = MotionRunner(
        camera_id="cam1",
        channel=1,
        config=_config(["hikvision", "onvif"]),
        rng=ZeroRng(),
        post=fake_post,
    )

    runner.run_forever(stop_event)

    assert calls.count("http://example.invalid/hik") == 2
    assert calls.count("http://example.invalid/onvif") == 2


def test_snapshot_provider_only_called_when_include_snapshot_enabled():
    snapshot_calls = []
    stop_event = threading.Event()

    def fake_post(url, data, headers, timeout):
        stop_event.set()

    runner = MotionRunner(
        camera_id="cam1",
        channel=1,
        config=_config(["hikvision"], include_snapshot=True),
        rng=ZeroRng(),
        post=fake_post,
        snapshot_provider=lambda: snapshot_calls.append(1) or b"jpeg-bytes",
    )

    runner.run_forever(stop_event)

    assert snapshot_calls == [1]


def test_snapshot_provider_not_called_when_disabled():
    snapshot_calls = []
    stop_event = threading.Event()

    def fake_post(url, data, headers, timeout):
        stop_event.set()

    runner = MotionRunner(
        camera_id="cam1",
        channel=1,
        config=_config(["hikvision"], include_snapshot=False),
        rng=ZeroRng(),
        post=fake_post,
        snapshot_provider=lambda: snapshot_calls.append(1) or b"jpeg-bytes",
    )

    runner.run_forever(stop_event)

    assert snapshot_calls == []
