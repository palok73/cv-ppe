I want to build a multi-camera helmet (PPE) monitoring system. Read SPEC.md first.
Interview me in detail using the AskUserQuestion tool.

Ask about technical implementation, deployment hardware, camera geometry, alarm behaviour, privacy/legal constraints, edge cases and tradeoffs. Don't ask obvious questions; dig into the hard parts I might not have considered (dedup across cameras, uniform look-alikes, night footage, false-alarm cost).

Keep interviewing until we've covered everything, then update SPEC.md: name the files and interfaces involved, state what is out of scope, and end with an end-to-end verification step using `python eval/run.py`.
