# camera-sim

A standalone service for testing cv-ppe's ingest stage without real cameras:
it loops locally-stored video files and serves them as RTSP streams shaped
like a Hikvision IP camera, and independently fires simulated motion-trigger
notifications in the two formats the ingest stage's SPEC anticipates
(Hikvision ISAPI "HTTP Listening" push, and ONVIF `wsnt:Notify` push).

It is a test double, not part of the core pipeline: it lives outside
`src/ppe_monitor/` and ships as its own installable package.

## Why it looks like this

- **RTSP `listen` mode is the default**, not `publish`. Real Hikvision
  cameras are RTSP *servers* — an NVR/VMS connects to
  `rtsp://<camera>:554/Streaming/Channels/101` (main stream, channel×100+1)
  and `.../102` (sub stream, channel×100+2). `listen` mode reproduces exactly
  that: the simulator opens those paths and waits for the pipeline to
  connect. `publish` mode (push to an RTSP URL you already run, e.g.
  MediaMTX) is also supported for setups that need it, per-stream.
- **Looping is seamless for `order: sequential`** (a single long-lived ffmpeg
  process loops an ffconcat playlist forever) but **reconnects once per pass
  for `order: random`** (each pass is a freshly shuffled, finite playlist;
  ffmpeg exits at the end of the pass and the supervisor restarts it with a
  new shuffle). This is a deliberate trade-off to get true per-pass
  randomization instead of a fixed shuffled-once order — see
  `src/camera_sim/rtsp.py`.
- **Motion notifications mimic two real push mechanisms**, not a pull/poll
  API, matching "push to my endpoint" test setups:
  - *Hikvision ISAPI*: a camera configured with an HTTP Listening host
    (`PUT /ISAPI/Event/notification/httpHosts/<id>`) POSTs an
    `EventNotificationAlert` XML body to that host on every event, optionally
    as `multipart/mixed` with a JPEG snapshot attached. `xml_version: "1.0"`
    reproduces the richer schema (`ipAddress`/`macAddress`/
    `DetectionRegionList`); `"2.0"` reproduces the simplified one.
  - *ONVIF*: a device with an active push subscription sends a SOAP
    `wsnt:Notify` carrying a `tns1:VideoSource/MotionAlarm` topic and a
    boolean `tt:Data/SimpleItem[@Name='State']` to the subscriber's endpoint.
    The WS-Subscription handshake itself isn't implemented — the target URL
    is configured directly, as if a subscription already exists.
  - Both are **best-effort reproductions** of publicly documented formats,
    not certified against real hardware or Hikvision's SDK. Don't rely on
    byte-exact parity; do rely on them exercising the same code paths a real
    push would.
  - Each motion "burst" fires `active`, holds for `active_duration_seconds`,
    then fires `inactive`, on every enabled channel.

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
