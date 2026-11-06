---
name: token-economizer-status
description: Show TokenEconomizer settings and saved state for the current Antigravity workspace. Use when asked whether TokenEconomizer is active or what it has learned.
compatibility: Requires Python 3.10 or newer on PATH.
---

Run `python3 scripts/run.py status --explain` from this skill directory.
Summarize the output accurately. The Agy CLI integration uses session-start,
pre-invocation, post-tool-use, and stop hooks. It folds a conversation after its
transcript has been quiet for ten minutes, counts tokens recorded in the Agy
transcript, and uses the rule-based loop guard without a model judge. Tool
pruning is unavailable on Agy. Effective-token cost is an estimate and falls
back to generic weights when the transcript's model has no price entry; it is
not billed spend. App and IDE behavior has not been separately verified.
