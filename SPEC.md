# SPEC: construction-site helmet monitoring (5-16 cameras)

Markers: **[decided]** = confirmed by the product owner; **[assumed]** = proposed default, to be confirmed.

## Product and scope
- Product for **construction companies**: law forbids moving on a construction site without a helmet, so violations must be reported ASAP. **[decided]**
- One site per deployment, **5-16 cameras** typical. **[decided]**
- Person identification is out of v1; keep an extension point only. **[assumed]**

## Deployment
- **On-prem server with NVIDIA GPU** (in the site cabin or similar). **[decided]** Verify in the PoC that 16 sub-streams at ~5 fps fit.
- Inference sits behind an interface (ONNX Runtime first) so edge devices remain possible later. **[assumed]**
- Site network may be LTE or unreliable: detection, alarms and storage must work **offline**; remote notifications retry with a queue. **[assumed]**
- Per-site YAML config: cameras, zones, adjacency and minimum transit times, optional floor-plan calibration.

### Baseline hardware (per site, up to 16 cameras) **[assumed: rough estimates, validate with the M1 benchmark]**
Load estimate: 16 sub-streams (640x360 to 1280x720) at ~5 fps = ~80 detector inferences/s, plus helmet classification on person crops and re-ID embeddings only on flagged events. Light for a modern GPU; hardware decode of the streams and the night/IR model are the parts to measure.

| Component | Baseline | Notes |
|---|---|---|
| GPU | NVIDIA RTX 4060 8 GB class, or RTX A2000 12 GB / L4 for a workstation-grade option | 8 GB+ VRAM leaves room for day and night models. NVDEC handles the sub-stream decode. |
| CPU | 8 cores (Ryzen 5/7 or Core i5/i7 class) | Stream handling, tracking, dedup, clip cutting. |
| RAM | 32 GB | Includes a ~30 s per-camera RAM ring buffer of the main stream (~30 MB per camera at 8 Mbps) for clip pre-roll. |
| Storage | 1 TB NVMe (OS, DB, clips) plus optional 2-4 TB HDD | Only incident clips and snapshots are kept, not continuous video (the NVR does that). Roughly 10-20 MB per incident. |
| Network | 2x GbE: camera VLAN and uplink; LTE/5G router as backup | Main-stream ingest of 16 cameras is ~64-130 Mbps, so use a proper PoE switch. |
| Power / environment | UPS (10+ min), dust-filtered or industrial chassis, cabin cooling | Construction cabin conditions: dust, heat, power dips. |
| OS / runtime | Ubuntu LTS, NVIDIA driver, Docker; ONNX Runtime with TensorRT provider | Keeps edge devices possible later. |

**Form factor [decided]:** a standard workstation/mini-server in a heated, ventilated cabin with UPS is the default (about EUR 1.5-2.5k per site, rough estimate; GPU ~EUR 400-440 new, Sep 2026). A **rugged/industrial fanless PC is a supported option** with the same software. Rugged units usually have a weaker GPU, so the M1 benchmark must state cameras-per-node for each class. The deployment guide covers both.

## Scaling beyond 16 cameras
1. **Headroom first:** one GPU should serve roughly 32+ cameras with the same design; measure it in the M1 benchmark and record "streams per GPU" in `docs/`.
2. **Scale up a node:** larger GPU or a second GPU; one worker process per camera group, with detector batching across cameras.
3. **Scale out to multiple nodes on one site:** partition cameras by zone; each node runs ingest, detect, track and helmet; only small event metadata (plus short-lived embeddings) goes to a per-site **dedup coordinator** over a message bus (MQTT or NATS).
4. **Multi-site:** each site keeps its own on-prem node (must still work offline); a central control plane handles config, model updates, fleet health and the aggregated dashboard. Video stays on site; only incident metadata and clips selected for review are uploaded.
5. **Design rules from day one:** per-camera workers with no global state, stages connected by queues, config-driven camera list, dedup partitioned by site and zone (only adjacent cameras are ever compared), inference behind an interface.

## Cameras
- **Mix of fixed CCTV and mobile camera towers.** **[decided]**
- **Both new and existing cameras:** customers will often reuse cameras they already have. **[decided]** Consequences:
  - Ship a **camera placement guide** (mounting height, maximum distance so a head is ~40-60 px, avoid backlight and steep down-angles) for new installs.
  - Add a **setup check** in the software: per-camera suitability score (head size at the working distance, exposure, blur, IR quality) and a warning when a view is unsuitable. Existing cameras get the score, not a rejection.
  - Accuracy varies per camera; report metrics per camera and show the score in the dashboard.
- Calibration is optional. With calibration: floor-position dedup. Without: time + camera adjacency + appearance only, accepting more duplicates. **[assumed]**

## Environment (all required in v1) **[decided]**
- Outdoor with daylight, weather and shadow changes.
- Night / IR footage: helmet colour is lost, so this needs its own training data and possibly its own model or threshold set.
- Dusty, dirty or steamy lenses: a camera-health / image-quality check (blur, blocked view, low contrast) raises a "camera degraded" notice instead of silently missing violations.
- Accuracy hazards: hi-vis vests and similar clothing (weak re-ID), hoods and caps, helmets of many colours, occlusion by scaffolding and machinery, people far from the camera.

## Pipeline
1. **Ingest:** RTSP sub-stream for detection, main stream for evidence. Optional ONVIF/webhook motion trigger; own person trigger is the fallback.
2. **Person trigger:** cheap motion gate, then person detector at ~5 fps. **Apache/MIT-style licensed models only** (RT-DETR, RF-DETR, YOLOX class); no Ultralytics YOLO or other AGPL/GPL components. Verify each model's and package's licence before adopting it (the RT-DETR implementation inside the Ultralytics package is AGPL). **[decided]** Track every model and dependency licence in `docs/licenses.md`.
3. **Tracking:** per-camera ByteTrack/BoT-SORT; one event per track.
4. **Helmet check:** PoC decides between (a) single detector with `head_helmet` / `head_no_helmet` classes and (b) person -> head crop -> classifier. N-of-M smoothing lives in `ppe/`.
5. **Dedup:** incident-level. Floor position (if calibrated) + time gating + appearance embedding as tie-breaker. Per-zone cooldown, default 60 s. Prefer a duplicate over a wrong merge.
6. **Events:** snapshot + clip with pre-roll, stored locally (SQLite + filesystem).

## Latency (two tiers) **[decided]**
- **Fast alarm:** <= 5 s from first violation, single camera, after N-of-M smoothing.
- **Merged incident record:** within ~60 s after cross-camera dedup.

## Notifications **[decided]**
- **SMS (via a gateway such as Twilio or a Slovak provider) and email / web push from the dashboard** to the site manager or safety officer. Telegram and WhatsApp are not in v1. Channel abstraction so providers can be swapped; delivery failure is retried with a queue and logged. Provider choice is made at M2.
- **Dashboard / review screen** with snapshot, clip, camera, zone, time; supports marking an incident as false alarm (feeds the eval set).
- On-site siren, light and phone-call alerts are **not** in v1 (keep an output interface so a relay can be added).

## Privacy and legal (operating in Slovakia, EU rules apply) **[decided: jurisdiction]**
Not legal advice; every point needs confirmation by Slovak counsel or a DPO before real footage is recorded.
- **GDPR:** video of workers is personal data even without faces. The construction company (employer) is expected to be the controller and we the processor, with a data processing agreement. A **DPIA** is very likely required (systematic monitoring of employees, new technology). Sites with subcontractors have several employers, so controller roles must be clarified per site.
- **Slovak law:** Data Protection Act (18/2018) and the Labour Code rules on employee monitoring: a serious reason linked to the employer's activity (workplace safety is a candidate), employees informed in advance of scope, method and duration, and consultation with employee representatives where they exist. Supervisory authority: ÚOOÚ.
- **EU AI Act:** helmet detection is not a prohibited practice, but AI used to monitor worker behaviour can fall into the employment high-risk category. Get an explicit legal classification early; it decides documentation and human-oversight obligations. The no-biometrics design helps whichever way it goes.
- **Roles [decided]:** the construction company is the controller and owns the legal basis and the DPIA. We are the processor and supply a DPA, a DPIA template and technical documentation (data flows, retention, access control, no-biometrics design).
- **Retention [decided]:** incident clips and snapshots are kept **7 days by default, configurable per site**, and deleted automatically.
- **Blocking item:** a Slovak lawyer / DPO reviews this section before any recording on a real site.
- **Design consequences:** no face recognition; appearance embeddings in memory only; retention enforced in code; access log for the review dashboard; incidents stored per site; data stays on site or in EU-hosted infrastructure; signage at the site; purpose limited to helmet compliance (no productivity or other analytics).
- **Localization:** dashboard and notifications in Slovak and English (Czech optional).

## Out of scope (v1)
ARC integration, multi-tenancy, person identification, siren/relay outputs, other PPE classes, fall detection, access control.

## Milestones
- **M0 (no real-site footage available, so we create the data) [decided]:**
  - Start with public PPE/hard-hat datasets for first detector experiments.
  - Record **staged footage** on our own premises or a test rig: volunteers with and without helmets of several colours, hoods and caps, hi-vis clothing, partial occlusion, distances and angles matching the placement guide, day / dusk / night with IR, and dirty-lens simulation (smudge, dust, fog).
  - Volunteers sign a consent form; staged footage follows the same retention and privacy rules.
  - Label a first eval set and make `eval/run.py` real. **Domain-gap risk:** staged data underestimates real-site clutter, so results are provisional until real-site footage exists.
  - Real-site footage comes later from a pilot customer, only after the legal review.
- **M1:** single-camera pipeline (ingest -> detect -> track -> helmet) with baseline eval numbers, day and night separately, plus a **sizing benchmark** (streams per GPU, latency, GPU/CPU/RAM use) to confirm or revise the hardware table.
- **M2:** events, clips, SMS and email/web-push notifications (provider chosen here), offline queue.
- **M3:** multi-camera dedup with topology config, with and without calibration.
- **M4:** review dashboard, camera-health alerts, retention job, stream reconnect hardening.

## Acceptance (starting targets, confirm after the M1 baseline) **[assumed]**
- Helmet recall >= 95% and precision >= 90% at incident level on the day set; night/IR targets set after baseline.
- <= 1 false alarm per camera per day on a 24 h soak recording.
- Dedup: <= 1.2 incidents per real violation on the multi-camera eval set; never merge two different people in the eval set.
- Fast-alarm latency <= 5 s measured end to end from frame capture to notification send.
- All measured by `python eval/run.py`.

## Eval set format (`eval/clips/labels.json`, gitignored)
Files: `eval/scoring.py` (loading, matching, metrics), `eval/run.py` (CLI, acceptance gates), `tests/test_eval_scoring.py`.
- A **scenario** is one staged session: `id`, `condition` (`day` | `dusk` | `night_ir`), `duration_s`, `cameras` (camera id -> clip path relative to the labels file), optional timezone-aware `epoch` (default 2000-01-01T00:00:00Z), and `violations`.
- A **violation** is one person without a helmet in a time window: `id`, `person` (anonymous key such as `p1`, only used to tell people apart, never a name), `start_s`, `end_s` (seconds from scenario start), optional `cameras` (default: all of the scenario's cameras).
- Pipeline contract: `--pipeline module:callable`, called as `f(scenario) -> list[Incident]`. Incident times are `epoch` + position in the clip (capture time, not processing time).
- **Matching:** an incident and a violation are candidates when they share a camera and their windows overlap (violation widened by `--tolerance`, default 3 s). A one-to-one matching decides which incident found which violation. Leftover incidents are **duplicates** (overlap an already-found violation) or **false alarms** (overlap nothing). A missed violation that overlaps an incident matched to a different person is a **suspected merge**.
- **Metrics** overall, per condition and per camera: recall, precision (1 - false alarms / incidents), incidents per violation, suspected merges, false alarms per camera-day.
- **Gates** (exit 1 if any fails; exit 2 if the eval cannot run): day recall >= 0.95, day precision >= 0.90, incidents per violation <= 1.2, suspected merges = 0, false alarms per camera-day <= 1 (only checked once the labels cover >= 24 camera-hours; staged clips skip it). Dusk and night/IR are reported but not gated until the M1 baseline sets targets.
- Not measured yet: fast-alarm latency (needs the notifier from M2), calibrated vs uncalibrated dedup split.

## Still open (none block work on M0)
1. Is a Slovak lawyer / DPO engaged? Required before any recording on a real site.
2. Which SMS gateway (decided at M2).
3. Who records the staged footage and where (own premises or a test rig)? Needed before M0 starts.
4. Budget ceiling per site, to be checked against the M1 benchmark.
