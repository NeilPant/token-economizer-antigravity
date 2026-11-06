# Porting plan: TokenEconomizer for Antigravity

**Status:** planning scaffold; no port code has been added yet  
**Upstream:** [microsoft/TokenEconomizer](https://github.com/microsoft/TokenEconomizer)  
**Target:** native Google Antigravity (Agy) plugin for App, CLI, and IDE

## Goal

Package TokenEconomizer as an installable Antigravity plugin while reusing its
existing Python mechanisms and keeping the agent's normal model, login, and
permissions. The plugin should learn repository-specific facts across sessions,
intervene when an agent is stuck, and reduce repeated tool overhead where
Antigravity exposes a safe way to do so.

Upstream currently implements three mechanisms: micro-skills, evidence-based
tool pruning, and a failure-loop guard. Its core package is Python 3.10+, uses
the standard library at runtime, and already separates shared logic from
agent-specific hook adapters.

## How the native plugin model fits

Antigravity plugins are versioned directories with `plugin.json` plus optional
skills, MCP servers, custom agents, rules, and lifecycle hooks. They can be
installed from a local directory or GitHub repository. Hook scripts receive a
JSON event on stdin and return JSON on stdout; a native plugin can bundle
`hooks.json` and relative-path scripts.

The target lifecycle includes `SessionStart`, `PreInvocation`, `PostInvocation`,
`PreToolUse`, `PostToolUse`, and `Stop`. Antigravity's hook contract is not
identical to the current upstream adapters, so add an Antigravity host adapter
instead of translating Antigravity events into a different host's assumptions.

## Upstream-to-Antigravity mapping

| TokenEconomizer mechanism | Antigravity integration | Design decision / validation needed |
| --- | --- | --- |
| Micro-skills | `SessionStart` reads the repository's confirmed facts and injects concise context. `PostToolUse` records observations; `Stop` can schedule a fold when the conversation is fully idle. | Antigravity has no upstream-style `SessionEnd`; establish how `Stop`, `executionNum`, and `fullyIdle` map to a foldable session. Store state by Antigravity conversation and repository identity. |
| Failure-loop guard | Track tool calls/errors from `PostToolUse`; use `PreInvocation` to inject a redirect when a prior assessment finds a repeated failure loop. Use the existing judge and redirect wording where host behavior permits. | `PreInvocation` runs before each model invocation, not necessarily once per user prompt. Verify how to identify a prompt-turn and what transcript data is available. Assess asynchronously if the hook can reliably retrieve a completed verdict. Do not force continuation from `Stop` until interactive behavior is verified. |
| Tool pruning | Learn usage evidence from tool events/catalog data. Expose proposals and a reversible restore path. | `PreToolUse` can deny, ask, or rewrite a call, but that does not itself remove a tool definition from the model context. Verify whether Antigravity exposes a supported way to hide/remove tool definitions. Do not claim token savings from blocking calls; if there is no native schema-pruning surface, ship proposal-only or mark this mechanism unsupported. |
| User-facing commands | Bundle Antigravity skills for status, configuration, micro-skills, and tool-pruning management, with helper scripts in the plugin. | Confirm skill discovery and slash-command behavior in App, CLI, and IDE. Keep each skill's `name` aligned with its folder name. |
| Session cost reporting | Reuse upstream pricing and ledger logic when Antigravity exposes enough token usage metadata. | Inspect Antigravity transcript/event logs and confirm whether input, cached, output, and auxiliary model-call usage are available. Report unavailable fields honestly; do not infer billed cost from invocation counts. |

## Implementation milestones

### 0. Capability spike

Before changing the shared engine, capture real event fixtures and answer these
questions on supported Antigravity CLI and IDE versions:

- What exact payloads arrive for every target event, including missing files,
  failed tools, asynchronous/background commands, and resumed conversations?
- Does `PreInvocation` distinguish a new user prompt from another model
  invocation in the same turn?
- What transcript format and token-usage fields are available to plugin hooks?
- Can a plugin safely enumerate or suppress available tools before prompt
  construction, or only deny calls in `PreToolUse`?
- Which Python executable is available to hooks on macOS, Linux, and Windows,
  and what hook timeout behavior applies?
- Does `Stop` with `decision: "continue"` behave consistently in interactive
  and headless runs, and how does `fullyIdle` affect background commands?

Record confirmed behavior and unsupported cases in the host adapter docs. Treat
any answer that differs across App, CLI, and IDE as a per-surface capability.

### 1. Native plugin shell

- Add a strict-schema `plugin.json` with a kebab-case plugin name, accurate
  version, upstream attribution, Apache-2.0 license, repository URL, and up to
  three suggested prompts.
- Add a marketplace-facing `README.md`, plugin-level `hooks.json`, and bundled
  launcher scripts using paths relative to the plugin root.
- Add `agy plugin validate --strict` and local install instructions.
- Keep runtime state outside the installed plugin directory; installed plugin
  files may be read-only or replaced during upgrades.

### 2. Antigravity host adapter

- Add `antigravity` as a host in the shared adapter/controller path, with
  Antigravity-specific event parsing and output serialization.
- Normalize `conversationId`, `workspacePaths`, `transcriptPath`, `modelName`,
  `lastUserInput`, `toolCall`, `error`, `executionNum`, and `fullyIdle` only where
  present; retain raw payload fixtures for regression coverage.
- Make every hook fail open: malformed input, missing Python, timeout, or an
  internal error must leave the agent running and return a no-op response.
- Prevent the plugin's own judge/proposer calls from recursively triggering its
  hooks, following the existing upstream side-call guard.
- Keep repository data isolated by canonical repository identity and plugin
  state isolated by host/conversation identity.

### 3. Micro-skills and loop guard

- Reuse upstream fact extraction, contradiction handling, turn-state detection,
  pricing, and ledger code where the event semantics match.
- Preserve upstream confirmation thresholds and per-mechanism configuration;
  keep micro-skills off by default if they require proposer model calls.
- Run folds/proposer/judge work outside latency-sensitive hooks where possible.
- Inject only concise, bounded context. A loop redirect is advisory and
  reversible; the plugin must not stop or kill a user task.
- Treat Antigravity token accounting as unsupported until transcript usage is
  verified end to end.

### 4. Tool pruning and commands

- Build a real Antigravity tool catalog from supported runtime metadata or an
  explicit refresh command; do not count tools that were never available.
- Keep human-oriented, planning, browsing, and delegation tools protected as in
  upstream.
- If Antigravity cannot remove schemas before model invocation, retain learning
  and a user-reviewable proposal but do not apply a deny list by default.
- Provide status, config, micro-skills, tool-pruning, and restore workflows as
  Antigravity skills and/or local CLI commands. Preserve all user-authored
  settings and make generated changes reversible.

### 5. Release readiness

- Validate the package with `agy plugin validate --strict` and install it from a
  local path in each supported Antigravity surface.
- Exercise session start, normal tool use, failed tool use, repeated failures,
  idle completion, resume, disable/uninstall, and missing-runtime behavior.
- Confirm state isolation across repositories and that disabling/uninstalling
  the plugin leaves user-authored configuration intact.
- Document verified versions, platform limitations, Python requirements,
  optional features, and cost-reporting limits.
- Preserve Microsoft's Apache-2.0 license and upstream notices; identify the
  derivative clearly and avoid implying Microsoft endorsement.

## Acceptance criteria

- The bundle passes `agy plugin validate --strict` without warnings and installs
  from a local path on every claimed surface.
- Session facts and loop-guard state are repository-scoped, persistent across
  conversations, and recover safely after interrupted hooks.
- Hook failures never fail the Antigravity task; disable and restore behavior is
  clear and reversible.
- No plugin-owned API key is needed. Any model calls use Antigravity's supported
  model/auth path and are included in cost reporting if usage is exposed.
- Tool pruning is advertised as token-saving only if definitions are removed
  before model context construction; otherwise it remains a reviewed proposal.
- Unsupported usage metrics or host events are reported as unavailable instead
  of estimated as fact.

## Collaboration notes

- Keep this port as a separate repository and preserve a clear link to upstream.
- Prefer small, reviewable commits: capability findings, plugin shell, host
  adapter, mechanisms, then release docs.
- Do not copy upstream implementation files until the target repository and
  licensing/attribution files are in place.

## References

- Upstream repository: <https://github.com/microsoft/TokenEconomizer>
- Antigravity plugins: <https://antigravity.google/docs/plugins/>
- Antigravity hooks: <https://antigravity.google/docs/hooks/>
- Antigravity plugin build guide: <https://antigravity.google/docs/build-plugins/>
