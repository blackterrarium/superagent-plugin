# Cross-harness role mixing (`SUPER_MODEL_<ROLE>=<harness>:<model>`) — design

**Date:** 2026-08-28
**Status:** approved (user), pending implementation plan
**Scope decision:** per-role harness mixing within one tick, in both directions between the
`claude` and `codex` supervisor harnesses, with `cursor` and `pi` as additional bridge
targets. Pi as a *supervisor* harness (`SUPER_HARNESS=pi`) is a separate later goal.

## Goal

Let one `.superenv` pin different agent roles to different providers inside a single loop —
e.g. the supervisor and reviewers on Claude, the implementer on an OpenAI model, the panel on
whatever Pi can reach — without changing how the dispatching skills (including superpowers'
`subagent-driven-development`, which this plugin does not own) call their subagents.

The codex harness design (2026-08-12) deliberately deferred this and left the seam: every role
already dispatches through a per-role hook — a generated `.claude/agents/super-<role>.md`
definition on Claude, `spawn_agent` parameters on Codex. This design uses that hook to swap the
*answering* subagent for a thin relay that runs the foreign CLI.

## Non-goals (YAGNI)

- `SUPER_HARNESS=pi` (Pi driving the tick). Follow-up goal; see § Pi follow-up.
- Bridging the supervisor itself. `SUPER_MODEL_SUPERVISOR` must be native to `SUPER_HARNESS`.
- Routing *native* roles through the bridge. Native dispatch is unchanged.
- Giving a bridged role in-process subagent tools. A bridged role is a single headless CLI run.
- Per-tick harness alternation within one loop.

## Harness CLI facts this design relies on

- **Claude Code:** `claude -p` reads the prompt from stdin; `--model` accepts tier names and full
  IDs; `--effort low|medium|high|xhigh|max`; `--allowedTools`. `CLAUDE_CODE_EFFORT_LEVEL` in the
  environment overrides `--effort` — the bridge unsets it for the child. Whether `claude -p` may
  be launched from inside a Claude Code session (`CLAUDECODE` set) is **unverified** and is the
  plan's first task; the fallback is `env -u CLAUDECODE`.
- **Codex:** `codex exec` reads the prompt from stdin when given `-`; `-m`, `-c
  model_reasoning_effort=<none|minimal|low|medium|high|xhigh>`, `-C <dir>`, `-o <file>` (last
  message), `--skip-git-repo-check`, sandbox flags as in the tick (`SUPER_CODEX_SANDBOX`).
  `spawn_agent` is available in plain `codex exec` sessions (smoke T4b, 2026-08-12).
- **Cursor:** `agent -p <prompt> --trust --force [--model <name>] --output-format text`
  (as in the tick). No effort knob.
- **Pi** (pi.dev docs via context7): `pi -p` reads the prompt from stdin; model string
  `<provider>/<model>[:<thinking>]` (e.g. `openai/gpt-5`, `anthropic/claude-opus-5:high`), or
  `--provider`/`--model`; thinking levels `off|minimal|low|medium|high` (per model);
  `--tools <list>` restricts tools; `--mode json` for an event stream. Pi core ships no subagent
  tool.

## 1. Configuration

### Value grammar

For the nine role keys (`SUPER_MODEL_PLANNER`, `_EXECUTOR`, `_PANEL`, `_IMPLEMENTER`,
`_FIX_APPLIER`, `_TASK_REVIEWER`, `_RE_REVIEWER`, `_BRANCH_REVIEWER`, `_FIX_PLANNER`):

```
value   := "inherit" | [harness ":"] model
harness := "claude" | "codex" | "cursor" | "pi"
model   := that harness's native model string
```

Inference when no prefix is given (prefix always wins):

| Value matches | Inferred harness |
|---|---|
| `sonnet` \| `opus` \| `haiku` \| `fable` \| `^claude-` | `claude` |
| `^gpt-` \| `^o[0-9]` \| `^codex` | `codex` |
| contains `/` (e.g. `openai/gpt-5`) | `pi` |
| anything else | WARN, treat as `inherit` (as today) |

A role is **native** when its harness equals `SUPER_HARNESS`, otherwise **bridged**.
`inherit` is always native (it means "omit the override" on the running harness).

`SUPER_MODEL_SUPERVISOR` must be native: a prefix equal to `SUPER_HARNESS` is stripped; any other
prefix (or a foreign inference) is a hard error in `init` and in `_common.sh` at tick time.

### Effort

`SUPER_EFFORT_<ROLE>` is validated in the **role's harness** domain, not the supervisor's:

| Role harness | Valid values | Delivery |
|---|---|---|
| claude | `low\|medium\|high\|xhigh\|max\|inherit` | `--effort` (bridged) / agent-definition `effort:` (native) |
| codex | `none\|minimal\|low\|medium\|high\|xhigh\|inherit` | `-c model_reasoning_effort=` (bridged) / `reasoning_effort` spawn param (native) |
| pi | `off\|minimal\|low\|medium\|high\|inherit` | `:<level>` suffix on the model string |
| cursor | `inherit` only | non-inherit → WARN, treat as `inherit` |

Out-of-domain values → WARN, treat as `inherit` (existing policy).

### New key

`SUPER_BRIDGE_RELAY_MODEL` — model of the thin relay subagent that runs the bridge. Default
`haiku` under `SUPER_HARNESS=claude`; `inherit` under `codex` and `cursor` (the CLI's default
subagent model). Validated as a native model value.

### `init` validation additions

- Parse every role key into (harness, model); apply the inference table; validate effort in the
  role's domain.
- Report a table: role · harness · model · effort · dispatch (`native` \| `bridge`).
- For every harness that appears as a bridge target, check its binary is on `PATH`
  (`claude`, `codex`, `agent`, `pi`) — hard error if missing — and warn when auth looks absent
  (`codex`: `OPENAI_API_KEY` or `~/.codex/auth.json`; `pi`: the provider's API-key env var for the
  value's `<provider>/` segment when it is `anthropic` or `openai`; `claude`/`cursor`: binary only).
- Under `SUPER_HARNESS=cursor`, bridged roles are supported through the same relay-definition
  mechanism the cursor build already uses for pins.

## 2. Bridge script — `scripts/role-bridge.sh`

Shipped in the plugin's `scripts/`; the codex build copies it to
`codex/plugins/superagent/scripts/` and the cursor build to `cursor/scripts/` (both builds
currently ship only skills + templates; this adds a `scripts/` copy step and extends the codex
smoke-probe skill to assert the file is present in the plugin cache).

```
role-bridge.sh --harness claude|codex|cursor|pi --model <m|inherit> --effort <e|inherit>
               --cwd <dir> --prompt-file <file> [--role <name>]
```

- Runs the target CLI headless in `<dir>` with the prompt on stdin; writes the CLI's final
  message to **stdout** and nothing else.
- Per-harness argv:
  - `claude`: `env -u CLAUDE_CODE_EFFORT_LEVEL claude -p [--model m] [--effort e] --allowedTools "Read,Edit,Write,Bash,Grep,Glob"` (plus `-u CLAUDECODE` if the nesting probe requires it).
  - `codex`: `codex exec <sandbox flags per SUPER_CODEX_SANDBOX> --skip-git-repo-check -C <dir> [-m m] [-c model_reasoning_effort=e] -o <out> -`; stdout = `<out>`.
  - `cursor`: `agent -p "$(cat file)" --trust --force [--model m] --output-format text`.
  - `pi`: `pi -p [--model m[:e]]`.
- CLI stderr (and, for codex/cursor, its progress chatter) goes to
  `${TMPDIR:-/tmp}/superagent-bridge/<role>-<UTC stamp>.log`; the path is printed on stderr.
- Exit codes: `0` ok · `2` CLI binary not found · `3` CLI exited non-zero · `4` CLI exited 0 with
  an empty result. `inherit` omits the corresponding flag.
- No timeout of its own: the tick's `TICK_TIMEOUT` bounds the whole session, as today.

## 3. Claude harness — relay agent definitions

- New template `templates/super-role-bridge-agent.md`. For a bridged role, `init` renders it to
  `.claude/agents/super-<role>.md` (same path, same `generated-by: superagent:init` marker as the
  pin template) with `model: <SUPER_BRIDGE_RELAY_MODEL>` (line omitted when `inherit`) and a body
  that instructs the relay to:
  1. write the entire prompt it received, verbatim, to a temp file;
  2. run `"${SUPERAGENT_BRIDGE:-<absolute path baked by init>}" --harness <h> --model <m>
     --effort <e> --cwd "$PWD" --prompt-file <tmp> --role <role>`;
  3. return the bridge's stdout verbatim as its final message — nothing added;
  4. on non-zero exit return `BRIDGE-FAILED exit=<n> harness=<h> role=<role> log=<path>` followed
     by the last 40 lines of the log.
- The tick exports `SUPERAGENT_BRIDGE="$PLUGIN_ROOT/scripts/role-bridge.sh"` so headless ticks
  never depend on the baked path (the plugin cache path changes on update). Attended sessions
  fall back to the baked path; the existing "re-run `superagent:init` after a plugin update" rule
  covers re-baking.
- Dispatch rule: on claude a bridged role always dispatches with `subagent_type: super-<role>`
  and no `model:` parameter — the same rule that already applies to full-ID and non-inherit-effort
  pins. `superrun`'s repo profile, `superagent`'s subagent-dispatch section, and `superloop` L7
  each gain one sentence saying so. A bridged panel ignores `SUPER_PANEL_AGENT_TYPE` (WARN) and
  still runs as three parallel relays.

## 4. Codex / Cursor harness — relay via the native subagent

- New template `templates/relay-preamble.md`: the relay body from § 3, parameterised on
  harness/model/effort/role/bridge-path.
- Codex (`codex-only` text in `init`, `superrun`, `superloop`, `superagent`, and the build
  banner): for a bridged role, `spawn_agent` with `model` = `SUPER_BRIDGE_RELAY_MODEL` (omitted
  when `inherit`) and message = rendered preamble + the task prompt verbatim. Bridge path =
  `<plugin_root>/scripts/role-bridge.sh` — skills already resolve the installed plugin root
  (smoke T3). Native roles keep today's `model`/`reasoning_effort` parameters. `init` on codex
  still generates no files.
- Cursor: `init` renders the bridge-agent definition exactly as on claude (the cursor build
  already generates per-role definitions for pins); `SUPERAGENT_BRIDGE` is exported by the tick
  for all harnesses.

## 5. Error handling

- A `BRIDGE-FAILED …` reply is a failed subagent result: `subagent-driven-development`'s
  existing retry/escalation handles implementer and reviewer failures; `superagent`'s existing
  ladder handles planner/executor failures. Nothing new is invented — the relay's only job is to
  fail loudly with a log path.
- A bridged implementer edits the worktree and commits nothing itself; the controller commits, as
  it does for native implementers.
- `init` refuses to generate when a bridge target's binary is missing, so a misconfigured
  `.superenv` fails at init time, not mid-tick.

## 6. Testing

- `scripts/bridge-test.sh` — offline unit test: fake `claude`/`codex`/`agent`/`pi` shims on
  `PATH` record argv and stdin; assert exact argv per harness, prompt relay, stdout passthrough,
  `inherit` flag omission, sandbox-flag selection, and every exit code.
- `scripts/bridge-smoke.sh` — real probes, one per bridge target, each an echo prompt through
  `role-bridge.sh` (T1 claude, T2 codex, T3 cursor, T4 pi — skipped with a note when the binary
  is absent); T5 the **nested-claude probe** (`claude -p` launched with `CLAUDECODE` set);
  T6 relay-definition round trip under `claude` (an Agent-tool dispatch of a generated
  `super-implementer.md` that returns a sentinel); T7 `spawn_agent` relay round trip under
  `codex`.
- `build-codex-skills.sh` probe skill extended to report `role_bridge_present: yes|no`.
- End-to-end: one scratch goal executed by `superrun` with `SUPER_MODEL_IMPLEMENTER=codex:<model>`
  under `SUPER_HARNESS=claude`, and the mirror (`claude:sonnet` implementer under `codex`).

## 7. Documentation and version

- README (`Configuration`, `Codex`, `Cursor` sections): the value grammar, inference table,
  bridge targets, prerequisites per target.
- `templates/superenv.default` header comment: replace the tier/ID-only description with the
  grammar; add `SUPER_BRIDGE_RELAY_MODEL`. `scripts/README.md`: `role-bridge.sh`,
  `bridge-test.sh`, `bridge-smoke.sh`. `codex/README.md`: bridged roles and the shipped
  `scripts/` directory. CHANGELOG entry.
- Version bump to **0.5.0** (the config value grammar changes).

## Pi follow-up (not in this design)

`SUPER_HARNESS=pi` would be a port on the codex pattern: a tick branch (`pi -p --mode json`),
`scripts/build-pi-skills.sh` with `pi-only` markers, skills loaded via `.pi/settings.json`, a
smoke suite, and a decision on role dispatch (require `pi-subagents`, or route every role through
`role-bridge.sh --harness pi`). Because Pi model strings already carry the provider
(`openai/…`, `anthropic/…`), cross-vendor mixing needs no bridge on that harness.
