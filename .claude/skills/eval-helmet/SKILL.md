---
name: eval-helmet
description: Run the helmet/dedup evaluation on labeled clips and report precision/recall against the previous run. Use after any change to detection, tracking, helmet classification or dedup.
disable-model-invocation: true
---

# Evaluate helmet detection and dedup

1. Run `python eval/run.py --pipeline <module:callable> --out eval/new_results.json` and capture the printed metrics.
2. Compare with `eval/last_results.json` if it exists.
3. Report a small table: helmet precision, helmet recall, incidents-per-violation, suspected merges, before vs after.
4. Flag any metric that got worse, with the clips that changed (from the run's per-clip output).
5. Only if the user agrees, overwrite `eval/last_results.json` with the new numbers.

Do not open or describe clip contents; work from the script's output only.
