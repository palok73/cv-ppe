"""Evaluate helmet detection and dedup on labeled clips in eval/clips/.

Expected labels: eval/clips/labels.json (format to be defined in SPEC.md).
Prints metrics; exits non-zero when acceptance thresholds are not met.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

CLIPS = Path(__file__).parent / "clips"


def precision_recall(tp: int, fp: int, fn: int) -> tuple[float, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return precision, recall


def main() -> int:
    labels = CLIPS / "labels.json"
    if not labels.exists():
        print("No eval/clips/labels.json yet. Add labeled clips first (see SPEC.md).")
        return 2
    # TODO: run the pipeline on each clip and compare with labels.
    json.loads(labels.read_text())
    print("Pipeline not implemented yet.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
