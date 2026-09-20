# Model and dependency licences

Rule (SPEC.md, Pipeline step 2): Apache-2.0 / MIT-style only. No AGPL/GPL, so no Ultralytics YOLO and
no RT-DETR implementation from inside the Ultralytics package. Check the licence of the **weights**
and of the **training data** as well as the code, and record it here before adopting anything.

| Item | Kind | Version | Licence | Source checked | Notes |
|---|---|---|---|---|---|
| numpy | dependency | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | installed package metadata | |
| opencv-python-headless | dependency | 5.0.0.93 | Apache-2.0 | installed package metadata | Wheels bundle FFmpeg (LGPL, from upstream docs, not verified here); confirm LGPL terms are acceptable before shipping |
