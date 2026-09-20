---
paths:
  - "src/**"
---

# Pipeline rules

- Stages exchange only the dataclasses in `src/ppe_monitor/types.py`; no stage imports another stage's internals.
- Every stage is deterministic given its input and a seed, so eval runs are reproducible.
- Detection and helmet thresholds come from config, never hard-coded.
- Temporal smoothing (N of M frames) lives in `ppe/`, not in `events/`.
- Timestamps are timezone-aware UTC; use the frame's capture time, not processing time.
- Dedup errors: prefer a duplicate incident over a merged pair of different people.
