---
name: token-economizer-config
description: Display TokenEconomizer configuration for the current Antigravity workspace. Use when asked to inspect or explain its settings.
compatibility: Requires Python 3.10 or newer on PATH.
---

Run `python3 scripts/run.py config show` from this skill directory and
explain the settings shown. Clarify that Agy supports the rule-based loop guard,
idle-time transcript folding, and transcript token counts. Its optional model
judge and distiller side calls have no Agy-native model-call path. Tool pruning
is unavailable because Agy does not expose a verified dynamic tool-catalog API.
Do not imply that unsupported settings become active by changing their value.
