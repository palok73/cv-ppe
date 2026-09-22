"""Fine-tune an RF-DETR helmet detector on a Roboflow-format COCO dataset.

Not part of the shipped pipeline (src/ppe_monitor/): this is offline tooling that produces
weights for the `ppe/` stage's helmet check to load later. RF-DETR is used because SPEC.md
("Pipeline step 2") restricts detector architectures to RT-DETR/RF-DETR/YOLOX (Apache/MIT
licensed, no Ultralytics/AGPL). See docs/licenses.md for the licence check on rfdetr itself.

No GPU was detected on this machine, so this defaults to RFDETRNano (the lightest variant,
384px) and a small epoch count. Increase --epochs once you have GPU time; on CPU, more than
a handful of epochs over the full 19.7k-image hard-hat-detection set is impractically slow.

Usage:
    .venv/Scripts/python.exe training/train_helmet_detector.py
    .venv/Scripts/python.exe training/train_helmet_detector.py --epochs 10 --dataset-dir data/construction-safety-object-detection
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=ROOT / "data" / "hard-hat-detection",
        help="Roboflow-format COCO dataset with train/valid/test subfolders",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Where to write checkpoints (default: data/models/<dataset-dir-name>-nano)",
    )
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    dataset_dir = args.dataset_dir.resolve()
    if not (dataset_dir / "train" / "_annotations.coco.json").exists():
        raise SystemExit(f"No {dataset_dir}/train/_annotations.coco.json — wrong --dataset-dir?")

    output_dir = args.output_dir or (ROOT / "data" / "models" / f"{dataset_dir.name}-nano")
    output_dir.mkdir(parents=True, exist_ok=True)

    from rfdetr import RFDETRNano

    print(f"dataset:    {dataset_dir}")
    print(f"output:     {output_dir}")
    print(f"epochs:     {args.epochs}  batch_size: {args.batch_size}  seed: {args.seed}")

    model = RFDETRNano()
    model.train(
        dataset_dir=str(dataset_dir),
        output_dir=str(output_dir),
        epochs=args.epochs,
        batch_size=args.batch_size,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
