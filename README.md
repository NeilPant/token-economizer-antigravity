# TokenEconomizer for Antigravity

An independent, native [Google Antigravity](https://antigravity.google/) plugin port of Microsoft's [TokenEconomizer](https://github.com/microsoft/TokenEconomizer).

> **Port status:** The plugin installs and runs in the Antigravity CLI. The current Agy adapter registers a session-start hook and provides two working skills for status and configuration. This is an initial integration, not a complete port of every upstream mechanism. Agy conversation folding, real-time loop intervention, tool pruning, and Agy token/cost accounting are not implemented.

## What this project is trying to do

TokenEconomizer is designed to reduce repeated work and wasted context in coding-agent sessions. Upstream provides mechanisms that learn small repository-specific facts, identify repeated failure loops, and use tool-use evidence to help prune unused tools.

This repository packages that project in Antigravity's native plugin format and adapts the shared Python code to Agy's runtime. The aim is to reuse the upstream mechanisms where their assumptions fit, use Agy's own skills and lifecycle hooks, and keep state scoped to the repository and conversation. Agy's events and payloads differ from other coding agents, so the adapter must use Agy's actual contracts instead of pretending it is Claude Code or Codex.

The port is being built incrementally. We only claim a feature works on Agy after its runtime behavior has been verified. See [PLAN.md](PLAN.md) for the design, capability findings, and remaining work.

## What works today

| Component | Agy support |
| --- | --- |
| Native plugin package | Validates with `agy plugin validate --strict` and installs from a local directory. |
| Session-start hook | Registered and smoke-tested in Antigravity CLI. It associates the conversation with an unambiguous workspace repository and records session state. |
| Status skill | `/token-economizer-status` runs and reports configuration and saved state. |
| Configuration skill | `/token-economizer-config` displays the current configuration. |
| Cached micro-skill injection | The adapter can format cached facts for Agy's session-start response, but Agy-side learning/folding is not implemented, so this does not currently produce learned facts. |
| Failure-loop guard | Not active on Agy. |
| Tool pruning | Not supported on Agy. Agy does not expose a verified API for removing built-in tool definitions from the active agent. |
| Session folding and token/cost accounting | Not implemented for Agy. |

The port has been checked with Antigravity CLI 1.5.2 on macOS. That confirms the CLI install, hook, and status-skill path; it does not certify the standalone App, IDE, other operating systems, or all upstream mechanisms.

## Requirements

- Google Antigravity App/CLI/IDE with plugin support. The CLI is needed for the commands below.
- Python 3.10 or newer available as `python3` on `PATH`.
- A GitHub connection only if installing from the GitHub repository; a local clone works offline.

The Antigravity CLI may be installed at `~/.gemini/bin/agy` without being on your shell `PATH`. If `agy` is not found, use that full path in the commands below or add `~/.gemini/bin` to your shell `PATH`.

## Install

### Install from GitHub

The repository is public. Install it using Agy's plugin CLI:

```sh
agy plugin install https://github.com/NeilPant/token-economizer-antigravity
```

If your `agy` executable is not on `PATH`, substitute `~/.gemini/bin/agy` for `agy`.

### Install from a local clone

```sh
git clone https://github.com/NeilPant/token-economizer-antigravity.git
cd token-economizer-antigravity
agy plugin validate --strict .
agy plugin install .
```

The validator should report two skills and one hook, then the install command should report that `token-economizer` was installed. The installed copy is staged under `~/.gemini/config/plugins/token-economizer` and is enabled by default.

### Install in the Antigravity App or IDE

Plugins installed through Agy are shared with the Antigravity App. In the App, open **Customizations → Installed** to confirm the plugin is enabled. In the standalone Antigravity IDE, a workspace-only local plugin can be placed under `.agents/plugins/` at the workspace root. For global manual installation, use `~/.gemini/config/plugins/`. The plugin was tested in the CLI; the App and standalone IDE have not yet had separate runtime smoke tests.

In the CLI's interactive session, `/plugin` opens the plugin manager. Use its Installed tab to inspect or enable/disable the plugin.

## Use

Once installed and enabled, the plugin's skills are available in an Antigravity session:

```text
/token-economizer-status
/token-economizer-config
```

You can also ask naturally, for example, “Is TokenEconomizer active in this workspace?” or “Show the TokenEconomizer configuration.” Agy loads each skill's name and description at session startup and reads its instructions when the skill is invoked.

The status output reports which mechanisms are available for the current host. A configuration value being present does not mean the corresponding mechanism is implemented for Agy; for example, `toolprune=auto` is an upstream default, but tool pruning is unavailable on this host.

## Configuration and data

TokenEconomizer stores runtime state outside the plugin install directory, which Agy may replace during plugin updates:

- Default state root: `~/.tokeneconomizer`
- Override the state root with `TOKENECONOMIZER_HOME` if you need another writable location.
- Repository identity is derived from the Git remote when available, so sessions from the same repository can share repository-scoped state.
- Antigravity sessions are recorded in the `antigravity` host namespace.

The configuration skill displays the values currently read by the shared TokenEconomizer core. Do not turn on unfinished Agy mechanisms expecting them to start working: folding, loop guarding, tool pruning, and usage accounting require additional Agy-specific implementation and validation.

## Verify, update, disable, or remove

Validate the source checkout and inspect installed plugins:

```sh
agy plugin validate --strict .
agy plugin list
agy plugin list --json
```

Install a newer local checkout over the existing installation with `agy plugin install .`. Then confirm its version and enabled state with `agy plugin list`.

Temporarily disable the plugin:

```sh
agy plugin disable token-economizer
```

Enable it again:

```sh
agy plugin enable token-economizer
```

Uninstall the plugin:

```sh
agy plugin uninstall token-economizer
```

Uninstalling removes the installed plugin package. The separate `~/.tokeneconomizer` state directory is not the plugin install directory; remove it yourself only if you also want to delete TokenEconomizer's saved repository/session data.

## Development

From a checkout:

```sh
agy plugin validate --strict .
agy plugin install .
```

The native bundle is made from `plugin.json`, `hooks.json`, `skills/`, `scripts/`, and the shared `tokeneconomizer/` Python package. The Agy adapter is in `tokeneconomizer/plugin/hosts.py`; the hook entry point is `scripts/te-hook.py`. Agy hook commands run from the plugin root, receive JSON on standard input, and must return their JSON response on standard output. The launcher keeps diagnostics away from the hook's JSON output and fails open when the runtime cannot process an event.

When changing the adapter, preserve Agy's camelCase payload fields and hook response formats. Validate with the Agy CLI after editing the manifest, skills, or hook configuration. Before enabling new lifecycle events, verify their semantics and behavior on each claimed Antigravity surface; see the acceptance criteria in [PLAN.md](PLAN.md).

## Project documents

- [Porting plan and Agy runtime notes](PLAN.md)
- [Upstream attribution](UPSTREAM.md)
- [Microsoft TokenEconomizer source](https://github.com/microsoft/TokenEconomizer)
- [Antigravity plugins](https://antigravity.google/docs/plugins/)
- [Antigravity hooks](https://antigravity.google/docs/hooks/)
- [Building Antigravity plugins](https://antigravity.google/docs/build-plugins/)

## License and attribution

This project adapts Microsoft's TokenEconomizer and retains its Apache-2.0 license and upstream notices. This Antigravity port is an independent community project; it is not an official Microsoft or Google product and is not endorsed by either company. See [LICENSE](LICENSE) and [UPSTREAM.md](UPSTREAM.md).
