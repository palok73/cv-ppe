# camera-sim

A standalone service for testing cv-ppe's ingest stage without real cameras:
it loops locally-stored video files and serves them as RTSP streams shaped
like a Hikvision IP camera, and independently fires simulated motion-trigger
notifications in the two formats the ingest stage's SPEC anticipates
(Hikvision ISAPI "HTTP Listening" push, and ONVIF `wsnt:Notify` push).

It is a test double, not part of the core pipeline: it lives outside
`src/ppe_monitor/` and ships as its own installable package.

**For the full reasoning behind these choices** — why RTSP `listen` mode is
the default, how the Hikvision ISAPI and ONVIF motion pushes actually work,
a code walkthrough, and known limitations — see [`DESIGN.md`](DESIGN.md).
The short version:

- RTSP `listen` mode (default) makes the simulator act as an RTSP *server*,
  like a real Hikvision camera, at `.../Streaming/Channels/101` (main) and
  `.../102` (sub). `publish` mode is also available per-stream for pushing
  into an existing RTSP server instead.
- `order: sequential` loops seamlessly; `order: random` reshuffles and
  briefly reconnects once per pass — a deliberate trade-off, not a bug.
- Motion notifications mimic two real push mechanisms: a Hikvision ISAPI
  "HTTP Listening" POST (`EventNotificationAlert` XML, optionally with a
  JPEG snapshot), and an ONVIF SOAP `wsnt:Notify`. Both are best-effort
  reproductions of publicly documented formats, not verified against real
  hardware.

## Requirements

- Python 3.10+
- A system `ffmpeg` binary on `PATH` (used as a subprocess for looping and
  RTSP muxing/serving; not bundled or linked — see `docs/licenses.md` at the
  repo root for the licensing note).

## Install and run

```bash
pip install -e ".[dev]"
camera-sim run --config config-examples/single-camera.yaml
```

Point your RTSP client (or the ppe_monitor ingest stage) at
`rtsp://localhost:8554/Streaming/Channels/101` (main) and
`rtsp://localhost:8555/Streaming/Channels/102` (sub) for the example config.
Motion notifications POST to whatever `target_url` you configure per channel
— point them at a throwaway HTTP listener while testing.

## Config reference

See `config-examples/single-camera.yaml` for an annotated example. Top level
is a list under `cameras:`; each camera has:

- `id`, `channel` (Hikvision channel number), `clips_dir`, `order`
  (`sequential` | `random`)
- `streams`: a map of stream name -> `{mode: listen|publish, bind_host,
  bind_port, path, target_url, resolution, bitrate_kbps}`. Any number of
  streams per camera (typically `main` + `sub`).
- `motion`: `{enabled, channels: [hikvision, onvif], interval_seconds,
  active_duration_seconds, hikvision: {...}, onvif: {...}}`.

## Tests

```bash
pytest -q
```

Tests cover config parsing, playlist ordering, ffmpeg argv construction, and
the Hikvision/ONVIF payload builders — all pure functions, so they don't
require `ffmpeg` or a network to run.
