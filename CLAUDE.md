# cv-ppe

Multi-camera helmet (PPE) monitoring: ingest streams -> person trigger -> track -> helmet check -> cross-camera dedup -> event/alarm.
Read `SPEC.md` for requirements. Keep this file under 200 lines.

## Scope
Construction sites in Slovakia (EU rules), single site, 5-16 cameras, on-prem GPU; ARC/multi-tenant out of scope.
Must work offline. Night/IR and dirty lenses are in scope. Apache/MIT-licensed models only (no AGPL/GPL, so no Ultralytics YOLO).

## Commands
- Install: `pip install -e ".[dev]"`
- Test: `pytest -q` (prefer a single file: `pytest tests/test_x.py -q`)
- Lint: `ruff check . && ruff format --check .`
- Eval (the source of truth for "does it work"): `python eval/run.py`

## Architecture decisions (non-obvious)
- Pipeline stages live in `src/ppe_monitor/<stage>/`; stages talk only through types in `src/ppe_monitor/types.py`.
- Dedup is **event/incident-level**, not identity-level. Signals: appearance embedding + floor-plane position + time gating.
- **No face recognition or face embeddings in the core pipeline.** Identification is an optional, separately switched module. See `.claude/rules/privacy.md`.
- Per-camera tracking emits one event per track, never per frame.
- Bias toward duplicates over missed violations when dedup is uncertain.
- Detection runs on the low-res sub-stream; the main stream is used only for evidence clips.

## Dev tools
- `services/camera-sim/`: standalone service (own `pyproject.toml`, install/test independently) that simulates Hikvision-style cameras — loops local video over RTSP and fires ISAPI/ONVIF-style motion pushes — for testing ingest without real cameras. Not a pipeline stage; see its README.

## Workflow
- After a series of changes: run lint, the relevant tests, then `python eval/run.py`.
- Do not report a detection change as an improvement without eval numbers (precision/recall before vs after).
- `data/` and `eval/clips/` hold large or sensitive footage: gitignored, never edit or commit.
- Use a subagent for anything that reads many files or long logs.

## Compact instructions
When compacting, preserve: modified files, test/eval commands, latest eval numbers, open decisions.
