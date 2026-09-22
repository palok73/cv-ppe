# Model and dependency licences

Rule (SPEC.md, Pipeline step 2): Apache-2.0 / MIT-style only. No AGPL/GPL, so no Ultralytics YOLO and
no RT-DETR implementation from inside the Ultralytics package. Check the licence of the **weights**
and of the **training data** as well as the code, and record it here before adopting anything.

| Item | Kind | Version | Licence | Source checked | Notes |
|---|---|---|---|---|---|
| numpy | dependency | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | installed package metadata | |
| opencv-python-headless | dependency | 5.0.0.93 | Apache-2.0 | installed package metadata | Wheels bundle FFmpeg (LGPL, from upstream docs, not verified here); confirm LGPL terms are acceptable before shipping |
| keremberke/construction-safety-object-detection | training data (image) | HF dataset, uploaded 2022-12-29 | CC BY 4.0 | dataset card on huggingface.co, mirrors Roboflow "Construction Site Safety" v1 | 398 images, 17 classes (hardhat/no-hardhat/vest/no-vest/mask/no-mask/gloves/person/etc). Downloaded to `data/construction-safety-object-detection/`. Attribution required per CC BY. |
| keremberke/hard-hat-detection | training data (image) | HF dataset, uploaded 2023-01-16 | CC BY 4.0 | dataset card on huggingface.co, mirrors Roboflow "Hard Hats" v2 | 19,745 images, 2 classes (hardhat/no-hardhat). Downloaded to `data/hard-hat-detection/`. Attribution required per CC BY. |
| rfdetr | training tool (`[train]` extra, not core) | 1.10.1 | Apache-2.0 | installed package metadata (`dist-info/licenses/LICENSE`) | RFDETRNano variant used, matches SPEC.md's allowed detector families. "Plus" variants (rfdetr_plus, RF-DETR-XL/2XL) are PML 1.0, not used here. |
| torch / torchvision | training tool (`[train]` extra) | 2.14.0 / 0.29.0 | BSD-3-Clause | installed package metadata | CPU-only wheels (no GPU on this machine). |
| transformers / huggingface-hub | training tool (`[train]` extra, rfdetr dependency) | 5.17.0 / 1.32.0 | Apache-2.0 | installed package metadata | |
| ffmpeg (system binary) | dev/test tool dependency, `services/camera-sim/` only, not part of the core pipeline | build-dependent | LGPL or GPL depending on build config (not bundled; invoked as an external subprocess, not linked) | ffmpeg.org licensing docs | Used only to loop local video as RTSP and extract snapshot frames for the camera simulator used to test ingest. Shelling out to a system binary is a different licensing posture than linking/bundling (as opencv-python-headless's wheel does above); flagging here for the same reason — confirm acceptable before this tool is used anywhere near a shipped product. |
| pyyaml | dependency, `services/camera-sim/` only | 6.x | MIT | PyPI project metadata | |
| requests | dependency, `services/camera-sim/` only | 2.x | Apache-2.0 | PyPI project metadata | |

## Datasets evaluated and rejected

| Item | Reason rejected |
|---|---|
| CMA: Construction Meta Action (GitHub S1mpleyang/ConstructionActionRecognition) | GitHub license badge says MIT, but the repo's own README explicitly restricts the *dataset* to research/non-commercial use with mandatory attribution — conflicts with the badge. Not used. Also hosted on Baidu Netdisk only (no plain HTTPS). |
| CMOT Dataset (GitHub XZ-YAN/CMOT-Dataset) | CC BY-NC 4.0 (non-commercial). Would be useful (77k clips, helmet + tracking annotations) but can't ship in a commercial product without separate licensing. |
| Roboflow-hosted "Construction Site Safety" (717-image v27) / CHV / SH17 | Export requires a Roboflow account sign-in; not pulled since we can't create accounts on the user's behalf. The 398-image v1 export of the same Construction Site Safety dataset is available unauthenticated via the Hugging Face mirror above instead. |
