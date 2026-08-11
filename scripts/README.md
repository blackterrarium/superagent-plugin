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
(stored per goal as `TICK_MODEL`) or the `TICK_MODEL` env var. The header line in the tick log records the
model in use (`model=...`).

### `.superenv` layer

`_common.sh`'s `load_superenv <repo-root>` resolves every `SUPER_*`/`TICK_*` variable in three layers,
highest wins: **process env** (e.g. `TICK_MODEL` exported by the scheduler) > **`<repo-root>/.superenv`**
(repo-local overrides, not checked into the plugin) > **`${CLAUDE_PLUGIN_ROOT}/templates/superenv.default`**
(the plugin's shipped defaults, 28 `SUPER_*` keys covering models, paths, loop tuning, CI policy, and
review protocol). `superagent-tick.sh`, `launch.sh`, and `install-timer.sh` all call `load_superenv "$REPO"`
right after resolving `REPO`, so `SUPER_TICK_INTERVAL` (default `30m`) and `SUPER_MODEL_SUPERVISOR` (default
`inherit`, which the tick treats as `opus`) are available before argument parsing.

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
- The `claude` CLI installed. A systemd user service, launchd job, or cron runs with a minimal `PATH`
  that omits the common user bin dirs, so the wrapper prepends `~/.local/bin`, `/opt/homebrew/bin`, and
  `/usr/local/bin` and **fails fast** if the binary is
  still not found. If your `claude` lives elsewhere, add its directory to `PATH` in the scheduler env.
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

## One-step launch (recommended)

`launch.sh` (and the `superagent-external` skill that wraps it) does bootstrap + install in a single
command — given only the root master plan it prepares the loop file and arms the timer, so the loop runs
in the background with no separate console:

```bash
$SUPERAGENT_SCRIPTS/launch.sh vault/<STAMP>-<slug>/master-plans/<seed>.md
# optional: --interval 30m (default)
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
tail -f /tmp/superagent-*.log                               # tick body, all schedulers
journalctl --user -u superagent-tick@<goal-slug>.service -f # Linux: service lifecycle + preflight errors
systemctl --user list-timers 'superagent-tick@<goal-slug>.timer'   # Linux
launchctl print gui/$(id -u)/com.superagent.tick.<goal-slug>       # macOS

# 4) Stop on DONE (or to pause).
$SUPERAGENT_SCRIPTS/uninstall-timer.sh <goal-slug>          # add --purge to also drop the env file
```

## Files

- `superagent-tick.sh` — the per-tick driver. `LOOP_FILE`, `REPO`, `TICK_TIMEOUT`, `LOG_FILE`
  via env (or `LOOP_FILE` as `$1`). Fresh session, never `--resume`. Runs uncapped by default so long
  CI-push ticks are not killed; wraps the CLI in `timeout` **only** when `TICK_TIMEOUT` is set to a
  positive integer. Runs the `gh` auth preflight (aborts if `gh` can't authenticate).
- `_common.sh` — sourced helpers: `ensure_gh_auth` (loads/exports `GH_TOKEN`, fatal preflight),
  `ensure_claude_bin` (fatal binary preflight), and `gh_auth_state` (non-fatal report used by `status.sh`).
- `launch.sh <PLAN.md> [--interval ..] [--timeout ..] [--slug ..] [--output stream|text] [--model <slug>] [--dry-run]`
  — one-step launcher: derive the goal slug, create/reuse the loop file, and arm the timer (what the
  `superagent-external` skill invokes). `--dry-run` previews without creating or arming anything.
- `bootstrap.sh <PLAN.md>` — one-time `--driver=external` bootstrap; prints the `LOOP_FILE=` path.
- `systemd/superagent-tick@.service` / `systemd/superagent-tick@.timer` — templated user units
  (instance `%i` = goal slug); read `~/.config/superagent/<slug>.env`.
- `launchd/com.superagent.tick.plist.template` — the macOS equivalent; `install-timer.sh` renders it
  per goal (launchd has no template units) into `~/Library/LaunchAgents/com.superagent.tick.<slug>.plist`,
  sourcing the same `~/.config/superagent/<slug>.env`.
- `install-timer.sh <goal-slug> <LOOP_FILE> [--interval ..] [--timeout ..] [--output stream|text] [--model <slug>]`
  — writes the per-goal env file, then arms the OS-appropriate scheduler entry: on Linux installs the
  units, enables lingering, starts the timer; on macOS renders + bootstraps the LaunchAgent.
- `uninstall-timer.sh <goal-slug> [--purge]` — the external `stop_driver()` (by slug).
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
- `status.sh [--json] [<slug>]` — enumerate **all** registered loops (from `~/.config/superagent/*.env`)
  with their live status/timer/tick/lock/input state; drill into one with `<slug>`.

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

2. **Answer injection.** Edit the loop file directly — add `answer: <option>` under `## Pending
   decision` — then let the next scheduled tick poll it and resume. Acquire the same lock first to avoid
   racing a poll tick:

   ```bash
   d="$(dirname "$LOOP_FILE")"; b="$(basename "$LOOP_FILE")"
   mkdir "$d/.$b.lockd"                       # acquire; if it exists, a tick is running — wait
   $EDITOR "$LOOP_FILE"                        # write: answer: <option>  under ## Pending decision
   rm -rf "$d/.$b.lockd"                       # release
   ```

The console plane is independent: killing a *monitoring* console is always safe; only avoid hard-killing
a console that is *mid attended-tick* (it self-heals next tick via crash recovery + the 90-min lock
steal).

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
