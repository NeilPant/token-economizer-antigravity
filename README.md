# TokenEconomizer for Antigravity

Native Google Antigravity plugin port of Microsoft's
[TokenEconomizer](https://github.com/microsoft/TokenEconomizer).

The upstream project is an Apache-2.0 Python package that learns repository
micro-skills, prunes unused tools, and detects failure loops across coding-agent
sessions. The first implementation slice includes the native plugin bundle, a
SessionStart adapter, and status/config skills. It does not yet fold Agy
conversations, run the loop guard, or prune tools.

## Start here

- [Porting plan](PLAN.md) — native plugin design, upstream-to-Antigravity mapping,
  milestones, open compatibility questions, and acceptance criteria.
- [Upstream attribution](UPSTREAM.md) — Apache-2.0 source and attribution details.
- [Antigravity plugin docs](https://antigravity.google/docs/plugins/)
- [Antigravity hooks docs](https://antigravity.google/docs/hooks/)

## Local use

The plugin requires Python 3.10+ on `PATH`. From a machine with Antigravity
installed, validate and install it with:

```sh
agy plugin validate --strict .
agy plugin install .
```

The `agy` executable is unavailable in this workspace, so these commands and
the live App/CLI/IDE hook behavior have not been verified here. Only the
documented `SessionStart` event is registered in this initial slice. Runtime
findings and the remaining capability spike are tracked in `PLAN.md`.

## Upstream attribution

The port derives from Microsoft's TokenEconomizer. Its Apache-2.0 license and
attribution are retained in this repository.
