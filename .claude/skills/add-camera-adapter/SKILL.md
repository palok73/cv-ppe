---
name: add-camera-adapter
description: Add support for a new camera source (RTSP/ONVIF, vendor webhook, GigE Vision) to the ingest stage. Use when the user wants to connect a new camera type.
disable-model-invocation: true
arguments: [source]
---

# Add camera adapter: $source

1. Read `src/ppe_monitor/ingest/__init__.py` and one existing adapter for the pattern.
2. Implement an adapter in `src/ppe_monitor/ingest/` that yields `Frame` objects (see `types.py`) with capture-time UTC timestamps and a stable `camera_id`.
3. Support both the low-res detection stream and the main stream (evidence only) where the source offers both.
4. If the source can push motion/analytics events (ONVIF events, webhook, MQTT), expose them as an optional trigger; keep our own person trigger as the fallback.
5. Add a test using a recorded fixture or a fake source; no live-camera tests in CI.
6. Run `ruff check .` and `pytest -q`.
