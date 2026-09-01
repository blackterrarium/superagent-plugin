# Superagent external loop — CLI driver

Run the superagent:superagent autonomy loop skill (built on the
[`superloop`](../skills/superloop/SKILL.md) chassis) unattended from a CLI, driven by an OS
scheduler. This is the **`external` driver** (superloop L2, Driver B): each tick fires in a fresh
headless CLI session, so context never accumulates and the loop runs straight to `DONE` with no restart.

No loop logic lives here — these scripts only *launch* ticks. All loop state lives in the gitignored
loop-status file the skills own.

**Finding this plugin's `scripts/` dir.** Every runnable example below uses `$SUPERAGENT_SCRIPTS` for the
absolute path to this installed plugin's `scripts/` directory — set it once per shell before pasting any
example (`${CLAUDE_PLUGIN_ROOT}` is only defined *inside* a Claude Code tool-execution context, e.g. a
running skill; it does not exist under cron, systemd, or a plain login shell, so examples cannot rely on
it):

```bash
SUPERAGENT_SCRIPTS=~/.claude/plugins/cache/<marketplace-name>/superagent/<version>/scripts
                                                            # that is the real cache shape a plugin
                                                            # marketplace install produces — check the
                                                            # actual path on this host with:
                                                            # ls ~/.claude/plugins/cache/*/superagent/*/scripts
```

## Two planes

- **Driver plane** — an OS scheduler entry (systemd user timer on Linux, launchd LaunchAgent on macOS)
  fires `superagent-tick.sh` on an interval; each run is one
  fresh, unattended tick that advances the state machine. This is the only thing that makes progress.
- **Console plane** — an optional interactive CLI session a human uses to *monitor* the loop and to
  *answer* decisions the loop parks on. It can be started and stopped at any time with no effect on the
  driver, because all state is in the loop file.

```
scheduler (systemd/launchd/cron) ──> superagent-tick.sh ──> claude -p (ONE --tick, fresh ctx)
                                                          │
                                                          ▼
                                   loop-status/<date>-<slug>.md  (local, gitignored)
                                                          ▲
   interactive console (monitor + answer, start/stop anytime) ──┘
```

## Model

The tick **always passes `--model` explicitly**, so it uses the pinned model regardless of the
CLI's own configured default. Resolution order: `TICK_MODEL` env var (if set) > `SUPER_MODEL_SUPERVISOR`
(from the `.superenv` layer below) > `opus`. A headless tick has no session to inherit from, so a
`SUPER_MODEL_SUPERVISOR` value of `inherit` also resolves to `opus`.
Override with `--model <slug>` on `launch.sh` / `install-timer.sh`
(stored per goal as `TICK_MODEL`) or the `TICK_MODEL` env var. The value passes verbatim to
`claude --model`, so a tier name (`opus`) and a full model ID (`claude-fable-5`) both work — no
generated agent definition is involved at this layer, unlike the subagent role keys. The header
line in the tick log records the model in use (`model=...`).

`SUPER_MODEL_SUPERVISOR` (and `TICK_MODEL`) must be **native** to `SUPER_HARNESS`: the value's
grammar is `[<harness>:]<model>` with the same `claude|codex|cursor|pi` prefix and inference rules
as the nine subagent role keys (see the main [`README.md`](../README.md#configuration)'s
Configuration section), but a prefix — explicit or inferred — that names a harness other than the
resolved `SUPER_HARNESS` is a hard error (exit 11; see Exit codes below) rather than a bridge: the
supervisor itself can never be dispatched through `role-bridge.sh`, only the nine dispatch-hook
role keys can.

## Effort

Per-role reasoning effort rides alongside the model pin, resolved the same way: `TICK_EFFORT` env
var (if set) > `SUPER_EFFORT_SUPERVISOR` (from the `.superenv` layer below) > `inherit` (no effort
flag passed — the CLI's own default applies). On the `claude` harness the tick passes `--effort
<value>` only when non-`inherit`; on `codex`, `-c model_reasoning_effort=<value>`. Domain is
harness-native: claude accepts `low|medium|high|xhigh|max`, codex accepts
`none|minimal|low|medium|high|xhigh` (no `max`). The Cursor CLI has no effort control at all — any
non-`inherit` `SUPER_EFFORT_SUPERVISOR`/`TICK_EFFORT` is logged as a warning and dropped, never
passed through.

This domain applies to `SUPER_EFFORT_SUPERVISOR`/`TICK_EFFORT` specifically, since the supervisor
is always native to `SUPER_HARNESS`. The nine subagent role keys (`SUPER_EFFORT_PLANNER`,
`_EXECUTOR`, `_PANEL`, `_IMPLEMENTER`, `_FIX_APPLIER`, `_TASK_REVIEWER`, `_RE_REVIEWER`,
`_BRANCH_REVIEWER`, `_FIX_PLANNER`) are validated in **their own resolved harness's** domain
instead — a bridged role's effort domain follows its own harness, not `SUPER_HARNESS`'s. That adds
a fourth domain beyond the three above: Pi accepts `off|minimal|low|medium|high|xhigh|max|inherit`
(a `:<level>` suffix on the model string, or `--thinking` when the model is `inherit`). See the
main [`README.md`](../README.md#configuration)
for the full per-role-harness table and defaults.

`CLAUDE_CODE_EFFORT_LEVEL` (a `claude` CLI env var) outranks both `--effort` and any per-role agent
frontmatter effort pin, so the tick never sets it itself; if the scheduler environment already
carries it, the tick logs a warning rather than silently letting it shadow the configured effort.

## Harness (Claude CLI vs Cursor CLI vs Codex CLI vs Pi CLI)

Every tick fires one agent-CLI session; **which** CLI is the harness: `SUPER_HARNESS=claude`
(default — `claude -p`), `SUPER_HARNESS=cursor` (the Cursor CLI: `agent -p --trust --force
--plugin-dir <plugin-repo>/cursor`, reading the generated Cursor build of the skills),
`SUPER_HARNESS=codex` (the OpenAI Codex CLI: `codex exec <prompt>`, reading the generated Codex
plugin-marketplace build under `<plugin-repo>/codex`), or `SUPER_HARNESS=pi` (the Pi CLI: `pi -p
--approve --skill <plugin-repo>/pi/skills`, reading the generated Pi build). Set it via `--harness
claude|cursor|codex|pi` on `launch.sh` / `install-timer.sh` (pinned into the per-goal
`~/.config/superagent/<slug>.env` at install time), the target repo's `.superenv`, or the
environment.

- **cursor:** auth is the CLI's stored login or `CURSOR_API_KEY` in the target repo's `.env`; model
  values are Cursor model names (`agent --list-models`), with `inherit` resolving to the CLI's own
  default (`auto`) rather than `opus`; the `cursor/` build must exist in the plugin repo
  (`scripts/build-cursor-skills.sh`).
- **codex:** skills load via the *installed* Codex plugin, not a `--plugin-dir` flag — install once
  with `codex plugin marketplace add <plugin-repo>/codex && codex plugin add
  superagent@superagent`; the tick's own file-read prompt still needs the build tree on disk at
  `<plugin-repo>/codex` (`scripts/build-codex-skills.sh`). Auth is `OPENAI_API_KEY` in the target
  repo's `.env`, else the CLI's own stored login (`codex login`). Model values are Codex model
  names (e.g. `gpt-5.1-codex`), with `inherit` omitting `-m` (the CLI's `config.toml` default
  applies). Sandbox posture is the separate `SUPER_CODEX_SANDBOX` knob (default
  `danger-full-access`, mapping to `--dangerously-bypass-approvals-and-sandbox` — parity with the
  unsandboxed claude harness; the alternative `workspace-write` maps to `--sandbox workspace-write
  -c sandbox_workspace_write.network_access=true`, but codex keeps the repo's top-level `.git/`
  read-only in that mode, so git fetch/commit fail and the L5 sync gate parks the loop) — an
  out-of-domain value aborts the tick (exit 8; see Exit codes below) rather than silently picking a
  posture.
- **pi:** skills are delivered per run via `--skill <plugin-repo>/pi/skills` — no install step
  (build/refresh the tree with `scripts/build-pi-skills.sh`). Auth is the CLI's own
  `~/.pi/agent/auth.json` or provider API keys in the target repo's `.env`. Model values are
  `<provider>/<model>` (e.g. `openai/gpt-5`), with `inherit` omitting `--model` (the CLI's own
  configured default applies); effort maps to `--thinking <level>` (the bridge instead suffixes
  `:<level>` onto a pinned model string), with `inherit` omitting it. Every run passes `--approve`
  (the operator armed the loop on this repo). Exports `SUPERAGENT_FANOUT` (path to
  `bridge-fanout.sh`, for the L7 panel) and `SUPERAGENT_PI_SKILLS` (the `--skill` path, so a
  bridged relay's child sees the plugin's skills too).

### `.superenv` layer

`_common.sh`'s `load_superenv <repo-root>` resolves every `SUPER_*`/`TICK_*` variable in three layers,
highest wins: **process env** (e.g. `TICK_MODEL` exported by the scheduler) > **`<repo-root>/.superenv`**
(repo-local overrides, not checked into the plugin) > **`${CLAUDE_PLUGIN_ROOT}/templates/superenv.default`**
(the plugin's shipped defaults — every `SUPER_*` key with its default, described per key or per
section, lives there; it is the reference). `superagent-tick.sh`, `launch.sh`, and `install-timer.sh` all call
`load_superenv "$REPO"` right after resolving `REPO`, so `SUPER_TICK_INTERVAL` and `SUPER_MODEL_SUPERVISOR`
(defaults in the template) are available before argument parsing.

## Prerequisites

- **The `superagent` plugin installed AND enabled for headless sessions in the target repo.** Slash
  commands and Skill-tool semantics for a disable-model-invocation skill are unverified in headless print
  mode, so the tick's prompt `Read`s `${PLUGIN_ROOT}/skills/superagent/SKILL.md` directly (`PLUGIN_ROOT`
  derived from the wrapper script's own location) rather than invoking the skill by name — but the loop's
  own internal `superagent:superplan` / `superagent:superrun` dispatches still go through the `Skill` tool
  once the session is running, so the plugin must still be installed and enabled for that to resolve. This
  wrapper does **not** probe for plugin presence (no live check); if the plugin is missing or disabled,
  those in-session dispatches fail opaquely deep inside the tick, not as a wrapper-level preflight error.
  The tick log header names this requirement as a hint — check it first if a tick fails with no clear
  cause. Confirm the plugin is installed/enabled before installing the timer.
- The resolved harness's CLI installed (`claude` by default; `agent`/`cursor-agent` for `cursor`,
  `codex` for `codex`, `pi` for `pi`). A systemd user service, launchd job, or cron runs with a
  minimal `PATH` that omits the common user bin dirs, so the wrapper prepends `~/.local/bin`,
  `/opt/homebrew/bin`, and `/usr/local/bin`, plus the directories `install-timer.sh` recorded as
  `SUPERAGENT_CLI_PATH` in the per-goal env file (the dirs of every agent CLI resolvable in the
  shell that armed the loop — this is what makes a CLI installed under a Node version manager such
  as nvm/fnm/volta, e.g. `~/.nvm/versions/node/<v>/bin/pi`, findable), and **fails fast** (exit 5)
  if the binary is still not found. If you move or reinstall a CLI, re-arm the loop from a shell
  where it resolves so the recorded directory is refreshed.
- `ANTHROPIC_API_KEY=...` in the repo `.env` (repo policy — keys live in `.env` only; the wrapper
  sources `.env`) — **or** a `claude` CLI already logged in (subscription/OAuth hosts): when no key is
  set the tick logs a note and relies on the CLI's own stored login instead of aborting.
- **`gh` authenticated in the tick.** `superplan`/`superrun` use `gh` for CI/PR operations
  (`gh pr create` / `gh run watch` / `gh pr merge --admin`). The CLI runs each tick in a tool sandbox
  that blocks `gh` from reading its own config/keyring, so `gh` authenticates only via **`GH_TOKEN` in
  the environment**. Put `GH_TOKEN=<token>` in `.env` (canonical, repo-policy path — the wrapper sources
  it and exports it so the CLI child inherits it). If it is absent, the wrapper falls back to the
  `oauth_token` in `~/.config/gh/hosts.yml`, then to `gh auth token` (hosts where gh stores the token
  in the OS keyring, e.g. the macOS keychain); if `gh` still cannot authenticate, the tick **aborts loudly**
  (a failed preflight) rather than silently breaking every PR/CI step. Check current state any time with
  `$SUPERAGENT_SCRIPTS/status.sh` (the `gh auth:` line).
- A goal **root** seed/master plan (`<PLAN.md>`) — the same file `superrun` traverses.
- For a headless server (Linux): user lingering (so the timer runs without an active login) —
  `install-timer.sh` runs `loginctl enable-linger $USER` for you. macOS has no linger equivalent: a
  LaunchAgent fires only while the user is logged in **and the Mac is awake** (see the launchd section).

## Exit codes (`superagent-tick.sh`)

| Code | Meaning |
|---|---|
| 1 | `REPO` unset and the wrapper isn't running inside a git repo. |
| 2 | `LOOP_FILE` not provided (env or `$1`). |
| 4 | `gh` preflight failed — not authenticated (see Prerequisites above). |
| 5 | The harness's agent CLI binary (`claude` / `agent` / `codex` / `pi`) not found on `PATH`. |
| 6 | `SUPER_HARNESS` is set to something other than `claude`/`cursor`/`codex`/`pi`. |
| 7 | The harness's generated build tree is missing (`cursor/`, `codex/`, or `pi/` — run the matching `scripts/build-*-skills.sh`). |
| 8 | `SUPER_CODEX_SANDBOX` (codex harness only) is set to something other than `workspace-write`/`danger-full-access`, or, on the pi harness, `SUPER_MODEL_SUPERVISOR` is not a `<provider>/<model>` string. |
| 9 | The session was terminated at a print-mode background-task wait ceiling (claude harness, operator-set `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS`) — subagents killed mid-flight while the CLI exited 0. |
| 10 | The session exited 0 but left a **transient** `status` (`PLANNING`/`RUNNING`) in the loop file — the tick completed without advancing or parking (e.g. an interrupted dispatch that ended its turn with a question; issue #17). The next tick self-heals via crash recovery. |
| 11 | `SUPER_MODEL_SUPERVISOR` (or `TICK_MODEL`) names a harness prefix (`[harness:]<model>`) other than the resolved `SUPER_HARNESS` — the supervisor must run natively; it cannot be bridged. |
| *other* | Propagated verbatim from the underlying CLI's (`claude`/`agent`/`codex`/`pi`) own exit status. |

Code 3 is unused.

## One-step launch (recommended)

`launch.sh` (and the `superagent-external` skill that wraps it) does bootstrap + install in a single
command — given only the root master plan it prepares the loop file and arms the timer, so the loop runs
in the background with no separate console:

```bash
$SUPERAGENT_SCRIPTS/launch.sh vault/<STAMP>-<slug>/master-plans/<seed>.md
# optional: --interval 10m (default, SUPER_TICK_INTERVAL)
```

It derives the goal slug + loop file, fails fast if the `claude` binary or `gh` auth is missing (arming
nothing), is idempotent (re-invoking re-arms / resumes), and kicks the first tick immediately. The
manual bootstrap + install-timer flow below remains available if you want the steps separately.

## Quickstart

```bash
# 1) Bootstrap the loop in external mode. Creates the loop-status file, prints the
#    scheduler entry, runs the first tick, and prints a `LOOP_FILE=<abs path>` line.
$SUPERAGENT_SCRIPTS/bootstrap.sh vault/<goal>/master-plans/<seed>.md

# 2) Install + start the per-goal scheduler entry (paste the LOOP_FILE from step 1).
#    Auto-detects the OS: systemd user timer on Linux, launchd LaunchAgent on macOS.
$SUPERAGENT_SCRIPTS/install-timer.sh <goal-slug> <LOOP_FILE> --interval 30m

# 3) Monitor (any of these; start/stop freely).
$SUPERAGENT_SCRIPTS/console-watch.sh <LOOP_FILE>            # alerts on WAITING FOR INPUT / DONE
$SUPERAGENT_SCRIPTS/answer.sh <slug> "<option>"            # answer WAITING FOR INPUT + kick a tick now
tail -f /tmp/superagent-*.log                               # tick body, all schedulers
journalctl --user -u superagent-tick@<goal-slug>.service -f # Linux: service lifecycle + preflight errors
systemctl --user list-timers 'superagent-tick@<goal-slug>.timer'   # Linux
launchctl print gui/$(id -u)/com.superagent.tick.<goal-slug>       # macOS

# 4) Stop to pause. (On DONE the tick wrapper disarms its own scheduler entry —
#    SUPER_AUTO_DISARM_ON_DONE, default true — so no manual stop is needed there.)
$SUPERAGENT_SCRIPTS/uninstall-timer.sh <goal-slug>          # add --purge to also drop the env file
```

## Files

- `superagent-tick.sh` — the per-tick driver. `LOOP_FILE`, `REPO`, `TICK_TIMEOUT`, `LOG_FILE`
  via env (or `LOOP_FILE` as `$1`). Fresh session, never `--resume`. Runs uncapped by default so long
  CI-push ticks are not killed; wraps the CLI in `timeout` **only** when `TICK_TIMEOUT` is set to a
  positive integer, and (claude harness) lifts print mode's 600s background-task wait ceiling
  (`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` unless the operator sets a value) so a long heavy-skill
  dispatch is never guillotined mid-flight. Exports `SUPERAGENT_TICK_PID` for the session's
  `acquire_lock()` owner record, and traps EXIT to reap a leaked L3 lock it owns (a session killed
  before `release_lock()`), never a peer's. A tick whose session was terminated at a background-wait
  ceiling exits non-zero with an explicit `ERROR` log line instead of a silent `exit=0`; likewise a
  session that exits 0 while the loop file still holds a transient `status` (`PLANNING`/`RUNNING`)
  is re-flagged as a loud failed tick (exit 10) — `exit=0` always means the tick advanced or
  parked. Runs the
  `gh` auth preflight (aborts if `gh` can't authenticate). **Self-disarms on `DONE`**: after the
  session ends, if the loop file's `status` is `DONE` it uninstalls its own scheduler entry
  (`uninstall-timer.sh <slug> --from-tick`, slug from the env file's `SUPERAGENT_SLUG` or a registry
  scan matching `LOOP_FILE`), keeping the loop-status and env files so re-arming stays a one-liner —
  gated by `SUPER_AUTO_DISARM_ON_DONE` (default `true`). Without this, a completed loop would keep
  burning a full CLI session per interval forever.
- `_common.sh` — sourced helpers: `ensure_gh_auth` (loads/exports `GH_TOKEN`, fatal preflight),
  `ensure_cli_bin` (fatal binary preflight for whichever harness CLI is resolved — `claude`, `agent`,
  `codex`, or `pi`), and `gh_auth_state` (non-fatal report used by `status.sh`).
- `launch.sh <PLAN.md> [--interval ..] [--timeout ..] [--slug ..] [--output stream|text] [--model <slug>] [--dry-run]`
  — one-step launcher: derive the goal slug, create/reuse the loop file, and arm the timer (what the
  `superagent-external` skill invokes). `--dry-run` previews without creating or arming anything.
- `bootstrap.sh <PLAN.md>` — one-time `--driver=external` bootstrap; prints the `LOOP_FILE=` path.
- `pi-e2e.sh [--dry-run] [--keep]` — the Pi end-to-end testbench (see the last section): empty repo →
  `init` → `supergoal` → scheduler-fired external loop → `DONE`, with assertions and a report.
- `mix-e2e.sh [--dry-run] [--keep]` — the multi-harness **mixing** end-to-end testbench (see the last
  section): the same empty-repo → `init` → `supergoal` → scheduler-fired loop → `DONE` drive as
  `pi-e2e.sh`, but with Claude supervising, the implementer/fix-applier bridged to Codex and the
  task-/re-reviewer bridged to Pi, plus a **harness-evidence** assertion built from `role-bridge.sh`'s
  log header/trailer lines. Writes `mix-e2e-report.md` (gitignored).
- `systemd/superagent-tick@.service` / `systemd/superagent-tick@.timer` — templated user units
  (instance `%i` = goal slug); read `~/.config/superagent/<slug>.env`.
- `launchd/com.superagent.tick.plist.template` — the macOS equivalent; `install-timer.sh` renders it
  per goal (launchd has no template units) into `~/Library/LaunchAgents/com.superagent.tick.<slug>.plist`,
  sourcing the same `~/.config/superagent/<slug>.env`.
- `install-timer.sh <goal-slug> <LOOP_FILE> [--interval ..] [--timeout ..] [--output stream|text] [--model <slug>]`
  — writes the per-goal env file, then arms the OS-appropriate scheduler entry: on Linux installs the
  units, enables lingering, starts the timer; on macOS renders + bootstraps the LaunchAgent.
- `uninstall-timer.sh <goal-slug> [--purge] [--from-tick]` — the external `stop_driver()` (by slug).
  `--from-tick` is the self-disarm mode `superagent-tick.sh` uses on a `DONE` loop: it skips the
  launchd drain-wait (the caller *is* the running tick), removes the plist before the `bootout`, and
  makes the `bootout` its final act (launchd reaps the calling process group with the job).
- `stop.sh <PLAN.md> [--hard] [--purge] [--slug ..] [--dry-run]` — one-step stopper by master plan (what
  the `superagent-stop` skill invokes): finds the installed loop from the plan, drains the timer
  (graceful by default; `--hard` halts an in-flight tick), preserves the loop-status file.
- `force-stop.sh (<PLAN.md> | --slug ..) [--apply] [--drain] [--no-kick]` — HUNG-tick recovery (what the
  `superagent-force-stop` skill invokes). Unlike `stop.sh` (which disarms the scheduler of a healthy
  loop), it targets a wedged/orphaned tick: halts the in-flight tick (reaping its claude child via the
  service cgroup) and removes the stale L3 `.lockd` so the loop self-heals immediately instead of waiting
  out the 90-min lock-steal. Dry-run by default (`--apply` to act); keeps the timer armed + kicks a
  recovery tick unless `--drain`/`--no-kick`. Never edits the loop file — the next tick's crash-recovery
  resets the persisted `RUNNING`/`PLANNING` state.
- `console-watch.sh <LOOP_FILE> [interval]` — read-only monitor that alerts on `WAITING FOR INPUT` /
  `DONE`.
- `answer.sh [--no-kick] [--replace] <slug> <answer…>` — answer a `WAITING FOR INPUT` loop: writes
  `answer: <text>` under `## Pending decision` (holding the L3 lock) and kicks one tick so the loop
  resumes now. Both flags are accepted in any position: `--no-kick` records only, `--replace`
  overwrites an answer already recorded in the block. Exit codes: 2 usage · 1 unknown slug / missing
  loop file · 3 not `WAITING FOR INPUT` · 4 lock held · 5 no `## Pending decision` heading.
- `status.sh [--json] [<slug>]` — enumerate **all** registered loops (from `~/.config/superagent/*.env`)
  with their live status/timer/tick/lock/input state; drill into one with `<slug>`.
- `build-codex-skills.sh [--check]` — derives the committed `codex/` Codex plugin-marketplace build
  from the canonical skills (single source of truth; `--check` rebuilds to a temp dir and diffs
  against the committed tree, exit 1 if stale — for CI / pre-release).
- `codex-smoke.sh` — smoke-tests the `codex/` build against a live Codex CLI (T1–T6: headless exec,
  marketplace + plugin install, skill enumeration, the generated probe skill, `spawn_agent`
  availability, the real tick file-read entry + hard gate, and effort-flag pass-through); always
  exits 0 and writes `codex-smoke-report.md` at the repo root — failures are the data, not a script
  bug.
- `role-bridge.sh --harness claude|codex|cursor|pi --model <m|inherit> --effort <e|inherit> --cwd <dir>
  --prompt-file <file> [--role <name>] [--tools role|planner|executor|<list>]` — runs one agent role
  on a harness CLI, headless: reads the prompt from `<file>`, runs the target CLI in `<dir>`, prints
  its final message on stdout and nothing else (CLI chatter goes to a log file, path printed on
  stderr). The relay definitions a bridged role dispatches through (`templates/super-role-bridge-agent.md`
  on Claude/Cursor, `templates/relay-preamble.md` on Codex, `templates/super-role-pi-bridge-agent.md`
  on Pi) shell out to this script; it is also copied into the `codex/`, `cursor/`, and `pi/` builds.
  `--tools` selects the child's tool allowlist (claude: `--allowedTools`; pi: `--tools`; codex/cursor:
  ignored): `role` (default: claude `Read,Edit,Write,Bash,Grep,Glob` · pi
  `read,edit,write,bash,grep,find,ls`) for a leaf role, `planner` (a `superplan` dispatch: claude adds
  `Task,Skill`; pi = the role set) for a skill-invoking dispatch, `executor` (claude
  `…,Task,Skill` — the tick's own set; pi = no `--tools` flag, so extension tools such as
  `pi-subagents`' `subagent` stay available) for a controller that dispatches subagents itself — this
  is how `superagent` runs `superrun` as the top-level agent of its own process, native or bridged,
  so the SDD controller's children can be foreground-waited on (issue #25). For claude the print-mode
  background-wait ceiling is lifted (`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` defaults to 0) like the
  tick does. Pi children always run with `--approve --no-session`, plus `--skill` from
  `SUPERAGENT_PI_SKILLS` when set.
- `bridge-fanout.sh --harness <h> --model <m|inherit> --effort <e|inherit> --cwd <dir>
  [--tools role|planner|executor|<list>] [--role <name>] [--timeout <sec>] --prompt-file <f> [--prompt-file <f> ...]`
  — runs N `role-bridge.sh` invocations CONCURRENTLY and blocks until all finish; the L7 panel
  primitive for a harness with no blocking parallel subagent tool (pi): one blocking shell call
  returns every panelist's verdict, framed `=== PANELIST <n> exit=<rc> ===` / `=== END <n> ===`.
  Default timeout 1800 s (still-running children killed and reported failed past it). Exit: 0 every
  child ok · 3 any child failed/timed out · 64 usage.
- `bridge-test.sh` — offline tests for `role-bridge.sh` and the `_common.sh` role-grammar parser,
  using `PATH` shims in place of the real CLIs (no network, no live CLI needed); prints `bridge-test:
  N failure(s)` and exits 1 on any failure.
- `bridge-smoke.sh` — live probes for `role-bridge.sh` against whatever real CLIs are installed on
  the host (T1–T7: each harness native, plus Claude↔Codex relay round trips); missing CLIs are
  reported as SKIP, not FAIL. Always exits 0 and writes `bridge-smoke-report.md` at the repo root —
  failures are the data, not a script bug.
- `build-pi-skills.sh [--check]` — derives the committed `pi/` Pi-package build from the canonical
  skills (single source of truth, plus a `pi-only` marker for content inert on the other harnesses;
  `--check` rebuilds to a temp dir and diffs against the committed tree, exit 1 if stale).
- `pi-smoke.sh` — smoke-tests the `pi/` build against a live Pi CLI (P1–P4 live probes: bad-model
  exit status, `--skill` delivery, `pi-subagents` presence, `--tools` allowlisting; T1–T5 tests:
  bridge → pi, bridge-fanout ×3, the tick file-read entry + hard gate, a relay round trip, and
  `build-pi-skills.sh --check`); missing `pi-subagents` SKIPs the tests that need it rather than
  failing. Always exits 0 and writes `pi-smoke-report.md` at the repo root — failures are the data,
  not a script bug.

## Monitoring multiple concurrent loops

`status.sh` is the deterministic, multi-instance enumerator; the `superagent-monitor` skill
(`../skills/superagent-monitor/`) is the interactive control plane on top of it — it lists every
concurrent loop, walks you through answering a `WAITING FOR INPUT` decision, and performs lifecycle
actions (drain, hard-stop, uninstall a DONE loop, re-arm a stopped one). Invoke it from any CLI session
on the loop host (e.g. "monitor my superagents").

```bash
$SUPERAGENT_SCRIPTS/status.sh              # one table across all loops
$SUPERAGENT_SCRIPTS/status.sh <slug>       # drill in: pending decision + log tails
$SUPERAGENT_SCRIPTS/status.sh --json       # machine-readable
```

## Console output (live by default)

Each tick's console output goes to `/tmp/superagent-<loop-basename>.log`. By default the driver runs the
CLI in **streaming** mode (`TICK_OUTPUT_FORMAT=stream`), so output appears **live, incrementally** —
`tail -f` shows progress as the tick runs, instead of only at completion:

```bash
tail -f /tmp/superagent-<loop-basename>.log
```

The stream is raw `stream-json --verbose`. Set `--output text` (on `launch.sh` / `install-timer.sh`,
stored per goal as `TICK_OUTPUT_FORMAT`) to revert to final-only output. Note: `journalctl --user -u
superagent-tick@<slug>.service` shows service lifecycle + preflight errors, not the tick body (which is
redirected to the log file). The log lives in `/tmp` (cleared on reboot, not rotated).

## Answering human decisions

The loop resolves most decisions itself (superloop L7: a 3-subagent panel, ≥2/3 converge). When it
cannot, it parks on `status: WAITING FOR INPUT` and writes a `## Pending decision` block. Two ways to
answer:

1. **Attended tick (preferred, race-free).** Run one tick interactively — with a
   person present, the skill's `WAITING FOR INPUT` branch prompts via `AskQuestion`, applies your answer,
   and continues, all under the L3 lock (serialized against the driver):

   ```bash
   cd <repo>
   claude   # interactive; then: invoke the superagent:superagent skill and run one --tick on <LOOP_FILE>
   ```

2. **`answer.sh` (one command, resumes now).** Records the answer under the lock and kicks a tick:

   ```bash
   $SUPERAGENT_SCRIPTS/answer.sh <slug> "<option>"
   $SUPERAGENT_SCRIPTS/answer.sh --no-kick <slug> "<option>"   # record only, no kick
   $SUPERAGENT_SCRIPTS/answer.sh --replace <slug> "<option>"   # overwrite a recorded answer
   ```

   Both flags parse in any position (`answer.sh <slug> "<option>" --no-kick` works too, and is not
   recorded as part of the answer); an unknown `--flag` is a usage error (exit 2).

   A hand edit also works (add `answer: <option>` under `## Pending decision`, holding
   `.<loop>.lockd` as a tick would) — it is consumed on the next scheduled fire.

While a loop waits, scheduled fires cost nothing: `superagent-tick.sh` checks the loop file in bash and
exits before launching a session until the answer exists (`SUPER_INPUT_GATE=true`, `.superenv`).

Scheduled fires are likewise free while a loop is parked on `WAITING FOR CI`: the wrapper queries each
run in the loop file's `ci_wait.runs` with `gh run view --json status` and launches no session until all
are `completed` (`SUPER_CI_GATE=true`). If the ids cannot be parsed or `gh` fails, it falls through to
the session (the pre-0.4.9 behaviour) rather than stalling. `ci_wait.repo` (`owner/name`, written at
parking) is passed as `gh run view --repo` so runs resolve when the clone's remote is a fork. A park whose
`ci_wait.since` is older than `SUPER_CI_MAX_WAIT_MIN` (default 180 min; `0` disables) with runs still not
`completed` is announced once (`ci-stale` notification) and the gate falls open so a run stuck in
`queued`/`waiting` cannot park the loop silently forever.

The operator is told once when the loop parks on a question they have not seen — a transition into
`WAITING FOR INPUT`, or a changed `## Pending decision` block while already parked (the re-park case) —
or finishes: set `SUPER_NOTIFY_CMD` to any shell snippet (it sees `SUPERAGENT_EVENT` =
`waiting-for-input`|`done`, `SUPERAGENT_SLUG`, `LOOP_FILE`, `SUPERAGENT_TITLE`, `SUPERAGENT_BODY`), e.g.

```bash
SUPER_NOTIFY_CMD='curl -s -d "$SUPERAGENT_BODY" -H "Title: $SUPERAGENT_TITLE" ntfy.sh/<topic>'
```

The value must be **single-quoted**: `.superenv` is *sourced* under `set -euo pipefail`, so an unquoted
`$SUPERAGENT_BODY` expands when the file loads — before those variables exist — and aborts every tick
with "unbound variable"; single quotes defer the expansion to notify time. `SUPERAGENT_BODY` carries
the loop's pending-decision text, so the question itself reaches whatever endpoint the snippet targets.
Unset, the wrapper falls back to a desktop notification (`osascript` on macOS, `notify-send` on Linux)
when available.

(Agent-acquired locks also record the driving PID in `…lockd/owner`; a tick that finds the owner
dead steals the lock immediately instead of waiting out `SUPER_LOCK_STEAL_MIN`.)

The console plane is independent: killing a *monitoring* console is always safe; only avoid hard-killing
a console that is *mid attended-tick* (it self-heals next tick via crash recovery + the lock steal —
immediate once the dead owner is detected, else after the 90-min `SUPER_LOCK_STEAL_MIN` window).

## Safety trade-off (auto-approval)

An unattended driver runs `claude` with `--allowedTools`, so the listed tool actions are not
individually confirmed. This is required for the loop to
write, commit, and merge on its own, but it means the repo norm "seek permission for any command that
deletes host files" cannot be honored by an interactive prompt in driver mode. Bound the blast radius
with the CLI's sandbox / permission deny-lists rather than relying on a
human gate.

## launchd (macOS)

On Darwin every lifecycle script auto-dispatches to launchd — same commands, same flags, same
`~/.config/superagent/<slug>.env` registry (which is what lets `stop.sh`/`status.sh` find the loop; a
hand-rolled plist that skips the env file is invisible to them). Per goal, `install-timer.sh` renders
`launchd/com.superagent.tick.plist.template` into
`~/Library/LaunchAgents/com.superagent.tick.<slug>.plist` and loads it with
`launchctl bootstrap gui/$(id -u)`.

Differences from the systemd driver worth knowing:

- **One job is both timer and service.** systemd separates the `.timer` (schedule) from the `.service`
  (running tick); launchd has a single job with a `StartInterval`. Consequences: a plist change needs a
  `bootout` + `bootstrap` reload, which would kill a tick in flight — so `install-timer.sh` refuses to
  reload while a tick is running, and `uninstall-timer.sh` (the graceful drain) **waits** for an
  in-flight tick to finish before unloading (Ctrl-C is safe; or halt the tick first with
  `stop.sh --hard` / `force-stop.sh`).
- **Halting a tick**: `stop.sh --hard` / `force-stop.sh` use `launchctl kill SIGTERM`; launchd then
  reaps the remaining process group (the claude child included) — the analog of systemd's cgroup stop.
- **Logged-in + awake only.** There is no `enable-linger` equivalent: a LaunchAgent fires only while
  the user has an active GUI login and the Mac is awake. For an always-on loop host keep the Mac awake
  (`caffeinate -s`, or Energy Saver/`pmset` settings). `StartInterval` fires once on wake if the
  interval elapsed during sleep, but there is no `Persistent=true`-style catch-up across reboots.
- **Interval fires on a fixed clock** (every N seconds since load), not N-after-last-finish like
  `OnUnitActiveSec`. Harmless: the L3 lock no-ops any fire that lands while a tick is in flight.
- **No next-fire timestamp.** `status.sh` shows the configured interval (`every 600s`) instead of an
  absolute next-fire time.
- **Logs**: the tick body streams to `/tmp/superagent-<loop-basename>.log` exactly as on Linux; the
  journalctl analog (preflight/loader errors) is `/tmp/superagent-launchd-<slug>.log`, and
  `launchctl print gui/$(id -u)/com.superagent.tick.<slug>` shows job state (`state = running` while a
  tick executes).

## cron fallback (instead of systemd)

If you prefer cron over a systemd user timer. **`cron` does not run a login shell**, so it never sees a
`SUPERAGENT_SCRIPTS` exported in some other shell (and crontab does not expand `~`) — set it as a
crontab environment-assignment line, above the schedule line, to an absolute path:

```cron
# adjust to wherever the superagent plugin is actually installed on this host — that is the real
# cache shape a plugin marketplace install produces; check the actual path with:
#   ls ~/.claude/plugins/cache/*/superagent/*/scripts
SUPERAGENT_SCRIPTS=/home/<user>/.claude/plugins/cache/<marketplace-name>/superagent/<version>/scripts

*/10 * * * * cd /path/to/target/repo && LOOP_FILE=/abs/path/to/loop-status/<date>-<slug>.md $SUPERAGENT_SCRIPTS/superagent-tick.sh >> /tmp/superagent-cron.log 2>&1
```

(Optionally add `TICK_TIMEOUT=<secs>` to cap a tick; unset means no cap.)

Overlap is handled by the L3 lock regardless of scheduler, so a short interval is fine even if a tick
runs long — the next fire no-ops until the lock releases.

## Pi e2e testbench (`pi-e2e.sh`)

`scripts/pi-e2e.sh` is the only thing that runs the whole framework on the Pi harness end to end,
unattended, with the **real OS scheduler firing every tick** (launchd on macOS, the systemd user
timer elsewhere). `pi-smoke.sh` probes mechanisms in isolation; this drives a real goal to `DONE`.

```bash
bash scripts/pi-e2e.sh --dry-run       # preflight + print what would happen; nothing created
bash scripts/pi-e2e.sh                 # the run (~20–40 min, ≈6 Pi sessions of model cost)
bash scripts/pi-e2e.sh --keep          # keep the local clone for inspection
```

Phases, each a section of `pi-e2e-report.md` (gitignored) with a PASS/FAIL line — the first FAIL
aborts after cleanup:

0. **Preflight** — `pi`, `gh` (authenticated), `git`, `python3`, `launchctl`/`systemctl`;
   `build-pi-skills.sh --check` up to date; `pi-subagents` present (WARN only).
1. **Provision** — the remote `PI_E2E_REPO` (default `<gh user>/superagent-pi-e2e`) is created if
   absent and otherwise **reset**: an orphan commit with `README.md` + the run's `.superenv`
   (`SUPER_HARNESS=pi`, `SUPER_TICK_INTERVAL`, `SUPER_NOTIFY_CMD` pointed at the run's
   `events.log`) is force-pushed to `main`, stale branches deleted, stale PRs closed. The repo is
   **never deleted** (no `delete_repo` scope needed); its PR numbers just keep counting.
2. **init** and 3. **supergoal** — headless `pi -p --approve --skill <plugin>/pi/skills
   "Read …/SKILL.md and run it…"`, exactly as the tick delivers skills. `supergoal` runs as **two
   turns in one persistent Pi session**: it drafts and, by design, stops at its confirmation gate
   ("Write this goal folder and root plan to the vault and open the PR?"); the second turn is the
   scripted operator's "yes". Asserts `.superenv` was left alone, the `.pi/agents/super-*.md`
   definitions exist, exactly one root master plan (`vault/*/master-plans/*.md`) landed on `main`, and supergoal merged its PR.
4. **Arm** — `launch.sh <PLAN.md> --harness pi --interval $PI_E2E_INTERVAL --slug pi-e2e-<stamp>`.
   Asserts via `status.sh --json` that the timer is active and that the per-goal env file pins
   `SUPER_HARNESS=pi` and `SUPERAGENT_CLI_PATH` (0.6.3).
5. **Drive** — polls `status.sh --json` every 30 s and logs every `(status, iteration)` transition
   with the tick count. **The script never runs a tick itself.** `done` → PASS; a
   `WAITING FOR INPUT` park or the `PI_E2E_MAX_MIN` ceiling → FAIL with the reason recorded.
6. **Assert** — on `main`: ≥2 ticks in the tick log (so at least one fired on the interval, not just
   the kickstart), the goal's deliverables (`scripts/hello.sh` prints `hello, world`,
   `scripts/test.sh` exits 0), ≥3 merged PRs and 0 open, the timer self-disarmed
   (`SUPER_AUTO_DISARM_ON_DONE`), and the `done` event reached `SUPER_NOTIFY_CMD`.
7. **Cleanup** (trap, always) — `stop.sh --hard` if a tick is in flight, `uninstall-timer.sh --purge`,
   copy the tick log into the run dir, delete the clone unless `--keep`.

Knobs: `PI_E2E_REPO`, `PI_E2E_INTERVAL` (`2m`), `PI_E2E_MAX_MIN` (`90`), `PI_E2E_GOAL` (change it
only together with the deliverable assertions in `e2e_assert_deliverables`), `PI_E2E_SUPERENV_EXTRA`
(extra `.superenv` lines — e.g. `SUPER_MODEL_TASK_REVIEWER=codex:gpt-5.6-sol` to put a codex relay
back in the loop; pure Pi is the default so one CLI suffices). Artifacts land in
`$TMPDIR/pi-e2e-<stamp>/` (`tick.log`, `events.log`, `transitions.log`). The pure helpers are
unit-tested offline in `bridge-test.sh` (`PI_E2E_LIB=1` sources the script without running it).

## Multi-harness mixing e2e testbench (`mix-e2e.sh`)

`scripts/mix-e2e.sh` is the only thing that runs a goal to `DONE` with the roles split across
**three** harness CLIs, unattended, with the real OS scheduler firing every tick — and the only thing
that *proves* which harness ran which role. `bridge-test.sh` checks the bridge offline and
`bridge-smoke.sh` does one relay round-trip; this drives a real goal through the whole loop.

```bash
bash scripts/mix-e2e.sh --dry-run       # preflight + print the mix and the plan; nothing created
bash scripts/mix-e2e.sh                 # the run (~60–120 min; Claude ticks + Codex + Pi sessions)
bash scripts/mix-e2e.sh --keep          # keep the local clone for inspection
```

The mix (every other key is the Claude build's default):

| role | harness / model | why |
|---|---|---|
| supervisor, planner, executor (`superrun`), branch-reviewer, fix-planner, panel | claude (native) | the supervisor cannot be bridged; controller roles stay on the full-feature harness |
| implementer, fix-applier | `MIX_E2E_IMPLEMENTER` = `codex:gpt-5.6-terra` | runs on every SDD task |
| task-reviewer, re-reviewer | `MIX_E2E_REVIEWER` = `pi:openai-codex/gpt-5.6-sol` | runs on every SDD task; Pi on the build host authenticates through the OpenAI Codex subscription, so its model strings are `openai-codex/<id>` |

So every task is controlled by Claude, written by Codex and judged by Pi. The plugin routes per
**role**, not per task — that is the feature under test.

Phases, each a section of `mix-e2e-report.md` with a PASS/FAIL line — the first FAIL aborts after
cleanup:

0. **Preflight** — `claude`, `codex`, `pi`, `gh` (authenticated), `git`, `python3`,
   `launchctl`/`systemctl`; `pi --list-models` lists the reviewer pin's provider; `codex login status`
   (WARN); the superagent plugin **installed and enabled** in the local `claude` — the claude tick's
   in-session `superagent:superplan` / `superrun` dispatches resolve through the *installed* plugin
   while the scripts run from this checkout, so a version mismatch is recorded and WARNed
   (`claude plugin update superagent@superagent-marketplace`); all three `build-*-skills.sh --check`
   clean; no loop registered under the run's slug.
1. **Provision** — the remote `MIX_E2E_REPO` (default `<gh user>/superagent-mix-e2e`) is created if
   absent and otherwise **reset** to an orphan commit with `README.md` + the mix `.superenv`; stale
   branches deleted, stale PRs closed. Never deleted.
2. **init** — headless `claude -p` (prompt on **stdin**: `--allowedTools` is variadic and swallows a
   positional prompt) invoking `superagent:init` through the Skill tool. Asserts `.superenv` was left
   alone and that `.claude/agents/super-implementer.md` / `super-fix-applier.md` are **codex relays**
   (`--harness codex --model "gpt-5.6-terra"`) and `super-task-reviewer.md` / `super-re-reviewer.md`
   are **pi relays** (`--harness pi --model "openai-codex/gpt-5.6-sol"`), all carrying the
   `generated-by: superagent:init` marker.
3. **supergoal** — two `claude -p` turns in one session (`--session-id`, then `--resume`): the goal,
   then the scripted operator's "yes" at its confirmation gate. Asserts exactly one root master plan on
   `main` and a merged PR.
4. **Arm** — `launch.sh <PLAN.md> --harness claude --interval $MIX_E2E_INTERVAL --slug mix-e2e-<stamp>`;
   asserts the timer is active and the env file pins `SUPER_HARNESS=claude` and `SUPERAGENT_CLI_PATH`
   (the codex/pi bridges from a scheduler tick depend on it — `pi` lives under nvm on the build host).
5. **Drive** — watch only (`status.sh --json` every 30 s), logging every `(status, iteration)`
   transition with the tick and bridge-call counts. `done` → PASS; a `WAITING FOR INPUT` park or the
   `MIX_E2E_MAX_MIN` ceiling → FAIL.
6. **Assert** — ≥2 ticks; the goal's deliverables (the default goal is a POSIX-sh key-value store,
   `scripts/kv.sh set|get|del|list` against `$KV_FILE`, checked behaviourally, plus `scripts/test.sh`
   exit 0); ≥3 merged / 0 open PRs; self-disarm; the `done` event. **6b. Harness evidence** — every
   `$TMPDIR/superagent-bridge/*.log` whose header `start=` is at or after the run start becomes a row
   `role harness model effort exit secs`; the table goes into the report and the run must show ≥1
   successful `implementer` on codex with the pinned model, ≥1 `task-reviewer` on pi with the pinned
   model, ≥1 `executor` on claude (the executor is always a bridge process, issue #25), no
   implementer/fix-applier/task-reviewer/re-reviewer row on a foreign harness, and no `BRIDGE-FAILED`
   in the tick log. A bridged relay that answered the prompt itself instead of shelling out leaves
   **no** row — which is exactly how it fails.
7. **Evaluation** (report-only) — elapsed minutes, ticks, loop iterations, merged PRs, bridge calls per
   harness (count / total secs / longest), per-role counts (fix-applier calls = fix rounds, panelist
   calls / 3 = L7 escalations), non-zero bridge exits, tick ERROR lines, the loop log's tail.
8. **Cleanup** (trap, always) — `stop.sh --hard` if a tick is in flight, `uninstall-timer.sh --purge`,
   copy the tick log **and the run's bridge logs** into the run dir, delete the clone unless `--keep`.

Knobs: `MIX_E2E_REPO`, `MIX_E2E_INTERVAL` (`2m`), `MIX_E2E_MAX_MIN` (`150`), `MIX_E2E_GOAL` (change
it only together with `mix_assert_deliverables`), `MIX_E2E_IMPLEMENTER` (must name codex),
`MIX_E2E_REVIEWER` (must name pi; its provider must appear in `pi --list-models`),
`MIX_E2E_SUPERENV_EXTRA` (extra `.superenv` lines appended last, e.g. `SUPER_MODEL_PANEL=pi:…`).
Artifacts land in `$TMPDIR/mix-e2e-<stamp>/` (`tick.log`, `events.log`, `transitions.log`,
`bridge/`). The pure helpers are unit-tested offline in `bridge-test.sh` (`MIX_E2E_LIB=1` sources the
script without running it); the shared drive/report helpers come from `pi-e2e.sh` (`PI_E2E_LIB=1`).
