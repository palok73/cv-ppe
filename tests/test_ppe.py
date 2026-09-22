from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from ppe_monitor.ppe import PPEConfig, check_helmet
from ppe_monitor.ppe import detector as detector_module
from ppe_monitor.ppe.detector import HelmetDetection
from ppe_monitor.types import Detection, Frame, Track

CAMERA = "cam-1"
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


class _FakeDetector:
    """Returns one canned detection list per call, in order, ignoring the image."""

    def __init__(self, results: list[list[HelmetDetection]]):
        self._results = iter(results)

    def detect(self, image_rgb, threshold: float) -> list[HelmetDetection]:
        return next(self._results)


def _track_with_n_detections(n: int) -> Track:
    detections = [
        Detection(
            camera_id=CAMERA, captured_at=T0.replace(microsecond=i), bbox=(0, 0, 10, 10), score=0.9
        )
        for i in range(n)
    ]
    return Track(camera_id=CAMERA, track_id=1, detections=detections)


def _frames_for(track: Track) -> dict[tuple[str, datetime], Frame]:
    image = np.zeros((10, 10, 3), dtype=np.uint8)
    return {
        (d.camera_id, d.captured_at): Frame(
            camera_id=d.camera_id, captured_at=d.captured_at, image=image
        )
        for d in track.detections
    }


def test_majority_hardhat_votes_yield_has_helmet_true():
    track = _track_with_n_detections(3)
    detector = _FakeDetector(
        [
            [HelmetDetection(bbox=(0, 0, 10, 10), has_helmet=True, confidence=0.9)],
            [HelmetDetection(bbox=(0, 0, 10, 10), has_helmet=True, confidence=0.8)],
            [HelmetDetection(bbox=(0, 0, 10, 10), has_helmet=False, confidence=0.6)],
        ]
    )

    verdict = check_helmet(track, _frames_for(track), detector, PPEConfig(min_conclusive_frames=1))

    assert verdict.track is track
    assert verdict.has_helmet is True
    assert verdict.confidence == pytest.approx((0.9 + 0.8) / 2)


def test_majority_no_hardhat_votes_yield_has_helmet_false():
    track = _track_with_n_detections(3)
    detector = _FakeDetector(
        [
            [HelmetDetection(bbox=(0, 0, 10, 10), has_helmet=False, confidence=0.7)],
            [HelmetDetection(bbox=(0, 0, 10, 10), has_helmet=False, confidence=0.6)],
            [HelmetDetection(bbox=(0, 0, 10, 10), has_helmet=True, confidence=0.9)],
        ]
    )

    verdict = check_helmet(track, _frames_for(track), detector, PPEConfig(min_conclusive_frames=1))

    assert verdict.has_helmet is False
    assert verdict.confidence == pytest.approx((0.7 + 0.6) / 2)


def test_no_conclusive_frames_defaults_to_not_confirmed():
    track = _track_with_n_detections(2)
    detector = _FakeDetector([[], []])  # no detections found in either frame

    verdict = check_helmet(track, _frames_for(track), detector, PPEConfig(min_conclusive_frames=1))

    assert verdict.has_helmet is False
    assert verdict.confidence == 0.0


def test_min_conclusive_frames_requires_enough_evidence():
    track = _track_with_n_detections(2)
    detector = _FakeDetector(
        [
            [HelmetDetection(bbox=(0, 0, 10, 10), has_helmet=True, confidence=0.9)],
            [],
        ]
    )

    verdict = check_helmet(track, _frames_for(track), detector, PPEConfig(min_conclusive_frames=2))

    assert verdict.has_helmet is False
    assert verdict.confidence == 0.0


def test_missing_frame_for_a_detection_is_skipped_not_counted():
    track = _track_with_n_detections(2)
    frames = _frames_for(track)
    del frames[(CAMERA, track.detections[1].captured_at)]
    detector = _FakeDetector(
        [[HelmetDetection(bbox=(0, 0, 10, 10), has_helmet=True, confidence=0.9)]]
    )

    verdict = check_helmet(track, frames, detector, PPEConfig(min_conclusive_frames=1))

    assert verdict.has_helmet is True
    assert verdict.confidence == pytest.approx(0.9)


@pytest.mark.skipif(
    not detector_module.DEFAULT_CHECKPOINT.exists(),
    reason="needs a trained checkpoint under data/models/ (gitignored; run training/train_helmet_detector.py)",
)
def test_real_checkpoint_detects_hardhat_on_a_dataset_image():
    pytest.importorskip("rfdetr")
    import cv2

    image_path = (
        Path(__file__).parent.parent
        / "data"
        / "hard-hat-detection"
        / "valid"
        / "Image2_jpg.rf.610856296b3d7934847694fc03c82aff.jpg"
    )
    if not image_path.exists():
        pytest.skip("needs the downloaded hard-hat-detection dataset under data/ (gitignored)")

    image_bgr = cv2.imread(str(image_path))
    frame = Frame(camera_id=CAMERA, captured_at=T0, image=image_bgr)
    detection = Detection(
        camera_id=CAMERA,
        captured_at=T0,
        bbox=(0.0, 0.0, float(image_bgr.shape[1]), float(image_bgr.shape[0])),
        score=1.0,
    )
    track = Track(camera_id=CAMERA, track_id=1, detections=[detection])
    detector = detector_module.HelmetDetector()

    verdict = check_helmet(track, {(CAMERA, T0): frame}, detector)

    assert verdict.has_helmet is True
    assert verdict.confidence > 0.3
