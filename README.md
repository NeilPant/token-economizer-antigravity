# TokenEconomizer for Antigravity

Planning repository for a native Google Antigravity plugin port of Microsoft's
[TokenEconomizer](https://github.com/microsoft/TokenEconomizer).

The upstream project is an Apache-2.0 Python package that learns repository
micro-skills, prunes unused tools, and detects failure loops across coding-agent
sessions. This repository currently contains the port plan only; implementation
has not started.

## Start here

- [Porting plan](PLAN.md) — native plugin design, upstream-to-Antigravity mapping,
  milestones, open compatibility questions, and acceptance criteria.
- [Antigravity plugin docs](https://antigravity.google/docs/plugins/)
- [Antigravity hooks docs](https://antigravity.google/docs/hooks/)

The plugin and hook contracts are documented in `PLAN.md`, but the Agy runtime
has not been exercised here because the `agy` executable is unavailable in this
workspace. The first implementation milestone is a capability spike against
live Antigravity App, CLI, and IDE builds before adapting the shared
TokenEconomizer engine.

## Upstream attribution

The planned port derives from Microsoft's TokenEconomizer and will retain its
Apache-2.0 license and required attribution in the implementation.
