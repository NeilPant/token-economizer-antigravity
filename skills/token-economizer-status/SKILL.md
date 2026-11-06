---
name: token-economizer-status
description: Show TokenEconomizer settings and saved state for the current Antigravity workspace. Use when asked whether TokenEconomizer is active or what it has learned.
compatibility: Requires Python 3.10 or newer on PATH.
---

Run `python3 scripts/run.py status --explain` from this skill directory.
Summarize the output accurately. Antigravity support is under development: the
current native hook handles session start only, so do not say the loop guard,
session folding, or token accounting is active.
