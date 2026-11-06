# Porting plan: TokenEconomizer for Antigravity

**Status:** initial native bundle implemented; runtime validation and mechanism hooks remain
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

Antigravity plugins are versioned directories with a required `plugin.json` and
optional skills, MCP servers, custom agents, rules, and lifecycle hooks. The
same plugin format is supported by the App, CLI, and IDE. Plugins can be
installed from a local path or GitHub URL, and App installations sync into the
CLI's installed list. The initial bundle now has a native manifest, skills,
`hooks.json`, and bundled Python scripts; it does not wrap the existing plugin
in a separate service.

### Runtime behavior confirmed in the official docs

These are documented contracts, not live observations from this workspace.
The `agy` executable is not installed here, so a runtime smoke test still needs
to happen on a machine with Antigravity.

- Hook commands run synchronously from the plugin root, receive camelCase JSON
  on stdin, and return one JSON object on stdout. The documented default timeout
  is 30 seconds. A non-zero exit is logged and ignored by the plugin host, so
  hooks should fail open and keep diagnostics off stdout.
- Installed plugin files live in a read-only directory and are replaced when
  the plugin updates. Hook commands should use paths relative to the plugin
  root. `${PLUGIN_DATA}` is documented for plugin MCP server processes; the
  docs do not promise it in shell hook environments. Keep durable state outside
  the install tree, using TokenEconomizer's private `~/.tokeneconomizer` state
  root with an Antigravity host namespace unless live tests identify a better
  supported writable location.
- Hook payloads include `conversationId`, `workspacePaths`, `transcriptPath`,
  `artifactDirectoryPath`, `modelName`, and `lastUserInput`. Transcript paths
  are under a different app-data root for App, CLI, and IDE. The adapter must
  support multiple workspace paths and must not assume the first path is always
  the repository root.
- `SessionStart` fires once per new conversation and can inject startup steps.
  `PreInvocation` fires before model calls and includes `invocationNum` and
  `initialNumSteps`; it is not a `UserPromptSubmit` event. `PostInvocation` runs
  after each model invocation. `Stop` is an execution-loop stop event, not an
  upstream `SessionEnd`; it reports `executionNum`, `terminationReason`, and
  `fullyIdle` (whether background work has completed).
- `PostToolUse` receives the tool call, step index, and an optional error, but
  its documented output is `{}`. It cannot deliver a redirect in that response.
  Read and parse the transcript for tool results, and inject a loop-guard nudge
  on a later `PreInvocation` or use `Stop` only after live behavior is verified.
- `PreToolUse` can allow, deny, ask, or rewrite a tool call. Blocking a call is
  not the same as removing its tool schema from the prompt. `Stop` can return
  `decision: "continue"` and a reason to re-enter the loop, so using it adds
  another model invocation and must remain a carefully bounded intervention.
- The CLI's separate status-line script payload includes context-window token
  counts and an estimated-cost object. Those fields are not part of the hook
  payload contract, and the docs don't specify an equivalent plugin hook for
  App or IDE. Treat status-line accounting as a CLI-only optional integration;
  inspect transcripts and other surfaces before claiming cross-surface costs.
- Antigravity already supports lazy MCP tool discovery; tools can be marked
  always-loaded by MCP metadata. This does not expose a documented mechanism
  for dynamically removing built-in tool definitions from the primary agent.
  A custom agent's tool allowlist is opt-in and does not transparently prune the
  user's selected agent.

Antigravity's hook contract differs materially from the current upstream host
adapters. Add a dedicated adapter and preserve the above lifecycle semantics;
do not map events onto Claude/Codex event names just to reuse their assumptions.

## Current implementation slice

- The upstream Python core is vendored under `tokeneconomizer/` with its
  Apache-2.0 license and source attribution.
- `plugin.json`, `hooks.json`, a bundled icon, and two native skills are in place.
  The only registered lifecycle hook is `SessionStart`, which injects existing
  cached facts using Antigravity's documented `injectSteps` response shape.
- The Antigravity adapter normalizes the documented camelCase fields, uses
  `conversationId` as the session key, and declines to pin state when mounted
  workspaces cannot be resolved to one repository.
- Status and config skills run the shared CLI with `--host antigravity`.
  Model-backed side calls return no answer until an Agy-native authenticated
  model path is verified; they never fall through to Claude Code.
- Loop guarding, transcript folding, tool-catalog learning/pruning, and Agy cost
  reporting are not registered or claimed as working yet.
- `agy plugin validate --strict` and local installation have not been run because
  this workspace has no Antigravity CLI or App installation.

## Upstream-to-Antigravity mapping

| TokenEconomizer mechanism | Antigravity integration | Design decision / validation needed |
| --- | --- | --- |
| Micro-skills | The native adapter can inject already-cached facts at `SessionStart`. No Agy fold hook is registered yet. | Verify transcript readability, append timing, compaction, and resume behavior in App, CLI, and IDE before wiring conversation folding. |
| Failure-loop guard | Read tool results/errors from the persistent transcript; queue or assess repeated failures away from the synchronous hook path. Inject a bounded advisory redirect on `PreInvocation`. | The hook payload lacks tool output and `PostToolUse` returns `{}`. Verify transcript format and per-turn boundaries. The hook contract does not provide a model-call API; prove how to make proposer/judge calls through the user's Agy auth without recursive hooks, or keep those model-backed features off. |
| Tool pruning | Collect usage evidence and offer a reviewable proposal. Optionally document Agy's built-in lazy MCP discovery. | There is no documented primary-agent API to remove tool definitions dynamically. A custom agent tool allowlist is opt-in and static; do not market call-denial or a custom agent as transparent token-saving pruning. |
| User-facing commands | Bundle skills for status, configuration, micro-skills, and tool-pruning management, with helper scripts inside the plugin. | Skills load their name/description at startup and full instructions on demand; test slash invocation and skill names in App, CLI, and IDE. |
| Session cost reporting | Reuse upstream pricing only where real usage data exists. A separate CLI status-line payload exposes context counts and an estimated-cost object. | The plugin hook contract contains no usage fields. The status-line interface is CLI-specific and isn't listed as a plugin component. Verify transcripts and App/IDE support before implementing a cross-surface ledger; distinguish estimated spend from billed spend. |

## Implementation milestones

### 0. Capability spike

**Status: pending live Antigravity access.**

Before changing the shared engine, capture real event fixtures and answer these
questions on supported Antigravity App, CLI, and IDE versions:

- Can hook subprocesses read `transcriptPath` on each surface and under the
  workspace sandbox? Does the transcript expose completed tool output, usage,
  compaction boundaries, and stable event ordering while it is still being
  written?
- How do `invocationNum`, `initialNumSteps`, and `lastUserInput` behave across
  multiple model calls for one prompt, queued prompts, resumes, and compaction?
- How does `Stop` fire across normal completion, max-step termination, errors,
  cancellation, and background tasks? Is `fullyIdle` reliable before folding?
- Are hook command timeouts and fail-open behavior consistent across App, CLI,
  and IDE? Which Python launchers and shells are available on macOS, Linux, and
  Windows?
- Can an installed plugin call an Agy model using the active user's auth and
  billing without launching a recursively hooked Agy session? What permissions
  and latency apply? If this is unsupported, which mechanisms work without a
  judge/proposer model call?
- Is there any supported API for dynamic built-in tool-schema pruning? How does
  built-in lazy MCP discovery interact with plugin-provided MCP tools and
  customization token budgets?
- Can the separate CLI status-line context/cost payload be installed or
  integrated from a plugin without overwriting a user's existing status-line
  customization? What usage information exists in App and IDE?

Record confirmed behavior and unsupported cases in the host adapter docs. Treat
any answer that differs across App, CLI, and IDE as a per-surface capability.
This workspace has no `agy` executable, so live validation must run on an
Antigravity-enabled machine before the port is considered runtime-compatible.

### 1. Native plugin shell

**Status: initial slice added; strict validation and installation pending.**

- Add a strict-schema `plugin.json` with a kebab-case plugin name, accurate
  version, upstream attribution, Apache-2.0 license, repository URL, and up to
  three suggested prompts.
- Add a marketplace-facing `README.md`, plugin-level `hooks.json`, and bundled
  launcher scripts using paths relative to the plugin root.
- Add `agy plugin validate --strict` and local install instructions.
- Keep runtime state outside the read-only installed plugin directory; do not
  assume hooks inherit the MCP-only `${PLUGIN_DATA}` variable.
- Use short hook handlers and explicit timeouts. Queue expensive work so hook
  time does not consume the default 30-second limit.

### 2. Antigravity host adapter

**Status: initial `SessionStart` normalization added; other events not wired.**

- Add `antigravity` as a host in the shared adapter/controller path, with
  Antigravity-specific event parsing and output serialization.
- Normalize `conversationId`, `workspacePaths`, `transcriptPath`, `modelName`,
  `lastUserInput`, `toolCall`, `error`, `executionNum`, and `fullyIdle` only where
  present; retain raw payload fixtures for regression coverage.
- Make every hook fail open: malformed input, missing Python, timeout, or an
  internal error must leave the agent running and return a no-op response.
- Prevent the plugin's own judge/proposer calls from recursively triggering its
  hooks, following the existing upstream side-call guard.
- Keep proposer/judge calls inert until an Agy-authenticated model-call path is
  verified; the current runner returns no answer rather than falling through to
  another installed agent's CLI.
- Keep repository data isolated by canonical repository identity and plugin
  state isolated by host/conversation identity.

### 3. Micro-skills and loop guard

- Reuse upstream fact extraction, contradiction handling, turn-state detection,
  pricing, and ledger code where the event semantics match.
- Preserve upstream confirmation thresholds and per-mechanism configuration;
  keep micro-skills off by default if they require proposer model calls.
- Run folds/proposer/judge work outside latency-sensitive synchronous hooks
  where possible. Use a native authenticated model-call path only after the
  capability spike verifies it; otherwise leave model-backed pieces disabled.
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
- Hook commands work with the read-only install layout, use persistent writable
  state safely, and stay within the configured timeout on App, CLI, and IDE.
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
- Antigravity CLI status line: <https://antigravity.google/docs/cli/statusline/>
- Antigravity CLI changelog: <https://antigravity.google/docs/changelog?tab=cli>
