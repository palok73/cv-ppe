"""Runs a fine-tuned RF-DETR checkpoint on an image crop, detecting hardhat / no-hardhat.

The checkpoint is produced by training/train_helmet_detector.py and is not committed to git
(data/ is gitignored) — train one first if DEFAULT_CHECKPOINT doesn't exist. rfdetr itself is
an optional dependency (`pip install -e ".[detect]"`), imported lazily so importing this module
doesn't require it unless a HelmetDetector is actually constructed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

DEFAULT_CHECKPOINT = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "models"
    / "hard-hat-detection-nano"
    / "checkpoint_best_ema.pth"
)
# Index must match training_config.json's class_names for the checkpoint in use.
CLASS_NAMES = ("hardhat", "no-hardhat")


@dataclass(frozen=True)
class HelmetDetection:
    bbox: tuple[float, float, float, float]
    has_helmet: bool
    confidence: float


class HelmetDetector:
    """Wraps an RF-DETR-Nano checkpoint fine-tuned on the hardhat/no-hardhat classes."""

    def __init__(
        self, checkpoint_path: Path | str = DEFAULT_CHECKPOINT, device: str = "cpu"
    ) -> None:
        checkpoint_path = Path(checkpoint_path)
        if not checkpoint_path.exists():
            raise FileNotFoundError(
                f"No checkpoint at {checkpoint_path}. Run training/train_helmet_detector.py first."
            )
        from rfdetr import RFDETRNano

        self._model = RFDETRNano(
            pretrain_weights=str(checkpoint_path), num_classes=len(CLASS_NAMES), device=device
        )

    def detect(self, image_rgb: np.ndarray, threshold: float) -> list[HelmetDetection]:
        """`image_rgb` must be RGB (not BGR) — convert Frame.image before calling."""
        result = self._model.predict(image_rgb, threshold=threshold)
        return [
            HelmetDetection(
                bbox=tuple(float(v) for v in xyxy),
                has_helmet=CLASS_NAMES[int(class_id)] == "hardhat",
                confidence=float(confidence),
            )
            for xyxy, class_id, confidence in zip(result.xyxy, result.class_id, result.confidence)
        ]
