# Privacy rules

- No face detection/recognition/embeddings in the core pipeline. Identification is an optional module behind an explicit config flag, default off.
- Appearance (re-ID) embeddings are treated as personal data: keep in memory or short-TTL storage only, never in long-term event records.
- Event records store: camera, zone, timestamp, confidence, snapshot/clip reference, incident id. Not embeddings.
- Retention is configurable and enforced in code (delete expired clips/snapshots), not left to ops.
- Never log frames, crops, or embeddings at INFO level or above.
- Anything touching identification must be flagged in the PR description for legal review.
