# Pi e2e testbench — design

**Date:** 2026-09-01 · **Status:** approved by default (built autonomously; the operator asked for
the testbench after the 0.6.3 scheduler-PATH fix — review the *Decisions* section and reopen any
you disagree with) · **Scope:** one script, `scripts/pi-e2e.sh`, plus offline tests and docs.

## Problem

Nothing reproduces the superagent framework running on the Pi harness end to end. What exists:
`pi-smoke.sh` (13 isolated probes — one tick reaches the supervisor's hard gate, no state
advances), `bridge-test.sh` (offline, shimmed CLIs), and one **manual** loop-to-DONE run on
2026-08-31 recorded as prose in `pi/README.md`. In particular no OS scheduler has ever fired a Pi
tick on its own; 0.6.3 fixed the concrete defect on that path (`SUPERAGENT_CLI_PATH`) but the
path is still unexercised.

## Goal

A single command that, from an empty repository, drives a tiny but real goal through
`init → supergoal → external loop (launchd/systemd fires every tick) → DONE`, asserts the
observable results, cleans up, and writes a report — repeatable, unattended, honest about cost.

Non-goals (YAGNI): exercising WAITING FOR INPUT / CI parks, L7 escalation, multi-goal
concurrency, other harnesses (the phases are harness-agnostic by construction, but only
`SUPER_HARNESS=pi` is wired and tested here).

## Design

### Command

```
scripts/pi-e2e.sh [--dry-run] [--keep]
  PI_E2E_REPO=<owner>/<name>     remote to (re)use   (default: <gh user>/superagent-pi-e2e)
  PI_E2E_INTERVAL=2m             scheduler interval   (launchd StartInterval / systemd OnUnitActiveSec)
  PI_E2E_MAX_MIN=90              wall-clock ceiling for the loop phase
  PI_E2E_GOAL="…"                goal text            (default: the hello-world shell goal below)
  PI_E2E_SUPERENV_EXTRA="…"      extra .superenv lines (e.g. a codex-bridged reviewer)
```

Exit 0 only when every assertion holds. Report: `pi-e2e-report.md` at the repo root
(gitignored, same convention as `pi-smoke-report.md`); per-run artifacts (tick log copy, event
log, status transitions) under `$TMPDIR/pi-e2e-<stamp>/`.

### Phases

Each phase appends a `## <n>. <name>` section to the report with the commands run, their
output (head+tail truncated like `pi-smoke.sh`), and a `**Result: PASS|FAIL (<why>)**` line.
The first FAIL aborts the run (after cleanup); the report is the deliverable either way.

0. **Preflight** — `pi`, `gh` (authenticated), `git`, `python3`, the scheduler
   (`launchctl` on Darwin / `systemctl --user` elsewhere); `build-pi-skills.sh --check` up to
   date; `pi-subagents` present (WARN only, mirrors `SUPER_PI_SUBAGENTS=recommended`); no loop
   registered under the run's slug. `--dry-run` stops here after printing what would happen.
1. **Provision** — ensure `PI_E2E_REPO` exists (`gh repo create --private` if not; **never
   deleted** — the operator's token has no `delete_repo` scope and a per-run repo would leak).
   Clone into the run dir, reset to an **orphan** commit carrying `README.md` and the run's
   `.superenv`, force-push `main`, delete every other remote branch, close any open PRs left by
   a previous run. Result: a clean repo whose PR numbers keep counting up.
2. **Init** — `pi -p --approve --no-session --skill <plugin>/pi/skills "Read
   <plugin>/pi/skills/init/SKILL.md and run it."` in the clone. Assert `.superenv` still says
   `SUPER_HARNESS=pi` (init must not overwrite), `.pi/agents/super-implementer.md` and the
   vault root exist. Commit and push anything init left uncommitted.
3. **Goal** — `supergoal` in a **persistent** Pi session (`--session-dir`/`--session-id`), two
   turns: the goal text (supergoal drafts, then by design stops at its §7 confirmation gate —
   *"Write this goal folder and root plan to the vault and open the PR?"*), then the scripted
   operator's "yes". A single headless turn can never pass that gate; on 2026-08-31 a human
   typed the yes. Assert exactly one root master plan (`vault/*/master-plans/*.md`) appeared on `main` after `git pull`
   (supergoal merges its own PR) and at least one merged PR exists.
4. **Arm** — `scripts/launch.sh <PLAN.md> --harness pi --interval $PI_E2E_INTERVAL --slug
   <slug>`. Assert via `status.sh --json`: the slug is registered, `timer_active`, the loop file
   exists with `status: WAITING FOR PLAN`; the per-goal env file contains `SUPER_HARNESS=pi`
   and `SUPERAGENT_CLI_PATH=` (0.6.3 in effect).
5. **Drive** — poll `status.sh --json` every 30 s until `done`, `pending_input`, or the ceiling.
   Log every `(status, iteration)` transition with a timestamp. **The script never invokes the
   tick itself** — that is the point. Ticks are counted from the tick log's session headers;
   the assertion is `ticks ≥ 2` (kickstart + at least one scheduler fire). `pending_input` is a
   FAIL that records the parked question; the ceiling is a FAIL that records the last status.
6. **Assert outcome** — on `main` after `git pull`: the goal's named deliverables exist and its
   own test passes (the default goal prescribes `scripts/hello.sh` printing `hello, world` and
   `scripts/test.sh` exit 0 so the check is deterministic); merged PRs ≥ 3 (goal, plan, code —
   the closeout is usually a 4th) and 0 open; `SUPER_AUTO_DISARM_ON_DONE` took effect (timer no
   longer active); the `done` event reached `SUPER_NOTIFY_CMD` (the `.superenv` points it at the
   run's `events.log`; **single-quoted**, per the 0.4.10 footgun).
7. **Cleanup** (trap, always) — `uninstall-timer.sh <slug> --purge` if still registered
   (`stop.sh --hard` first if a tick is in flight), copy the tick log into the run dir, remove
   the clone unless `--keep`. The remote stays for the next run.

### Default goal

> Add `scripts/hello.sh` (POSIX sh) that prints exactly `hello, world`, and `scripts/test.sh`
> that runs it and exits non-zero unless the output matches. One implementation plan is enough.

Small enough that one `superplan` + one `superrun` tick complete it (as on 2026-08-31: 4 ticks
to DONE), specific enough that phase 6 can assert file paths and behaviour.

### `.superenv` written by phase 1

```
SUPER_HARNESS=pi
SUPER_TICK_INTERVAL=<PI_E2E_INTERVAL>
SUPER_NOTIFY_CMD='printf "%s\n" "$SUPERAGENT_EVENT" >>"<run-dir>/events.log"'
<PI_E2E_SUPERENV_EXTRA>
```

Model/effort keys are left at the Pi build's defaults (`inherit` → the CLI's configured
default, `gpt-5.6-sol` on the build host). A codex-bridged reviewer, as in the 08-31 run, is one
`PI_E2E_SUPERENV_EXTRA` line away and deliberately not the default: the testbench should not
need a second CLI to pass.

### Slug

`pi-e2e-<YYYYmmdd-HHMMSS>` passed to `launch.sh --slug`, so stale scheduler entries from an
aborted run can never collide with a new one, and preflight can refuse if one is still registered.

### Testing the testbench

Offline, in `bridge-test.sh` (shimmed `pi`/`gh`/`git`, no network): the script sources as a
library when `PI_E2E_LIB=1`, exposing the pure helpers — status-JSON extraction, transition
dedupe, `.superenv` rendering (quoting!), deliverable assertions, tick counting — each with a
red-then-green case; plus `--dry-run` under shims exits 0 and prints the plan without touching
the remote. The live run itself is the integration test; its result is recorded in
`pi/README.md` via the build script, as the smoke's is.

## Decisions (assumptions the operator can override)

1. **Reuse one remote, reset per run** (vs. create+delete) — the token lacks `delete_repo`;
   leaking a repo per run is worse than a growing PR history in one.
2. **Scheduler fires the ticks; the script only watches** — otherwise the testbench proves
   nothing the 08-31 manual run didn't.
3. **Pure Pi by default** (no codex bridge) — one CLI dependency; the bridge is opt-in.
4. **`python3` for JSON** — `status.sh --json` is the control-plane contract; macOS ships
   python3 with the CLT and `jq` is not guaranteed. Only the testbench needs it.
5. **Interval 2 m, ceiling 90 min** — launchd won't overlap ticks and the L3 lock backstops;
   the 08-31 run needed 4 ticks. Cost ≈ 6 Pi sessions (init, supergoal, 4 ticks).
6. **No answering of parked decisions** — a park is a FAIL: the default goal must not need
   input; if it does, that is a finding about the plan authoring, not something to paper over.

## Error handling

- Any preflight miss → exit 2 with the missing prerequisite named; nothing created.
- Remote operations are idempotent (`gh repo view || gh repo create`; branch/PR cleanup tolerates
  "nothing to do").
- The cleanup trap runs on EXIT/INT/TERM; it is the only place that touches the scheduler on the
  way out, and it re-checks `status.sh --json` before acting so a DONE loop that already
  self-disarmed is not "stopped" twice.
- The run dir and report survive every failure mode; the tick log is copied, not moved.
