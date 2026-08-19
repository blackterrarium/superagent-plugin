---
name: superagent-monitor
description: Use to monitor and control the superagent external loops running on this host — list every concurrent loop and its live state (status, iteration, timer/tick/lock, WAITING FOR INPUT, DONE), answer a parked decision, and perform lifecycle actions (drain, hard-stop, uninstall a DONE loop, re-arm a stopped one). The console/control plane for the plugin's external driver.
argument-hint: "[<slug>]   (omit to cover all loops)"
license: all rights reserved
related skills: superagent, superloop
---

# Superagent monitor

The **console / control plane** for superagent external loops (the driver plane is this
plugin's `scripts/` directory + the per-goal scheduler entry, a systemd user timer on
Linux or a launchd LaunchAgent on macOS — see
[scripts/README.md](../../scripts/README.md)). This skill is read-first and
start/stop-independent of the driver: it reads the same gitignored loop-status files the
drivers own and never blocks their ticks. It is **multi-instance by default** — the
registry is every per-goal env file under `~/.config/superagent/*.env`, so one invocation
covers all concurrent loops. Pass a `<slug>` to scope to one.

## Repo configuration (.superenv)

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${CLAUDE_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.superenv" "${CLAUDE_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
(checking the env var first, and anchoring at the primary checkout so worktrees resolve the same config). A repo with no `.superenv` runs on the shipped defaults.

Everything here runs on the **host that runs the loops** (the primary checkout holding
the gitignored `<SUPER_LOOP_STATUS_DIRNAME>/` files — worked example from the originating
repo: `SUPER_LOOP_STATUS_DIRNAME=loop-status` — and the `.<loop>.lockd` locks). Resolve
`primary_root` first if invoked from a worktree, and locate this plugin's installed
`scripts/` directory via `$SUPERAGENT_SCRIPTS` (see
[scripts/README.md](../../scripts/README.md) for the convention):

```
primary_root="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
cd "$primary_root"
SUPERAGENT_SCRIPTS="${CLAUDE_PLUGIN_ROOT}/scripts"   # CLAUDE_PLUGIN_ROOT is set in Claude Code sessions;
# for cron/systemd use the absolute install path — see scripts/README.md
```

Run every `$SUPERAGENT_SCRIPTS/*.sh` helper from `primary_root` (so each script's own
`REPO` auto-detection targets the right checkout) and every `git` command against
`primary_root`.

## Step 1 — Enumerate (always safe, read-only)

Run the deterministic enumerator and present its table to the user:

```
$SUPERAGENT_SCRIPTS/status.sh          # table across ALL loops
$SUPERAGENT_SCRIPTS/status.sh <slug>   # drill into one (pending decision + tails)
$SUPERAGENT_SCRIPTS/status.sh --json    # machine-readable, for your own parsing
```

The output opens with a host-wide `gh auth:` line, then columns `SLUG STATUS ITER TIMER TICK
LOCK INPUT`. Read them, then **interpret** for the user:

- **`gh auth: unauth`** (or `no-gh`) — a **host-wide blocker**: `superplan`/`superrun` cannot do CI/PR
  operations, and every tick's preflight aborts loudly, so no loop can make progress. Flag this first;
  fix by setting `GH_TOKEN` in `.env` (see [scripts/README.md](../../scripts/README.md#prerequisites)).
- **`INPUT=YES`** (status `WAITING FOR INPUT`) — the loop is parked on a decision the L7 panel could not
  resolve. Offer to answer it (Step 2).
- **`STATUS=DONE`** — the goal is complete. The tick wrapper self-disarms the scheduler entry on the
  `DONE` tick (`SUPER_AUTO_DISARM_ON_DONE`, default `true`), so the timer is normally already gone;
  if one is still armed (opt-out, or a loop armed by a pre-0.4.6 build), offer to uninstall it (Step 3).
- **`STATUS=WAITING FOR CI`** — the loop is **parked on a long CI wait** (run ids in the loop file's
  `ci_wait:` block), not stuck: external ticks do one cheap status check each and no-op until the runs
  are terminal. A long park is normal for 60–120 min lanes; check the runs (`gh run view <id>`) only if
  the user asks or the park exceeds the lane's expected runtime.
- **`TIMER!=active` but STATUS non-terminal** — the driver was stopped/removed while work remains; offer
  to re-arm (Step 3).
- **`TICK=yes` / `LOCK=yes`** — a tick is running right now. Do **not** mutate that loop's file or
  hard-stop without warning the user; monitoring is still fine.
- **loop file missing** (`status.sh` shows `<none>`/exists=no) — the local loop-status file is gone
  (wiped checkout / different host). Progress lives in the vault plan tree, not the loop file — resuming
  means re-running `bootstrap.sh` (a FRESH START that re-derives next-step from the tree); flag this.

For live following, either re-run Step 1 on request, or arm the watcher (event-gated, one per loop):
`$SUPERAGENT_SCRIPTS/console-watch.sh <LOOP_FILE>` (it emits
`AGENT_LOOP_WAKE_superagent {...}` on `WAITING FOR INPUT`/`DONE`).

## Step 2 — Answer a `WAITING FOR INPUT` loop

Drill in first (`status.sh <slug>`) and show the user the `## Pending decision` block verbatim (the
question + the panel's per-option analysis). Then choose a path. **Prefer the attended tick** — it is
race-free (runs under the L3 lock and applies + continues in one step).

Read the loop's `LOOP_FILE` from `~/.config/superagent/<slug>.env`.

**Path A — attended tick (preferred).** Present the decision options to the user with `AskQuestion`, then
run exactly one interactive tick, passing the chosen answer as guidance. The skill's
`WAITING FOR INPUT` branch consumes it, records it under `## Decisions`, restores `prior_status`, and
continues the tick — all under the lock, serialized against the scheduler. Derive the plugin root from
`$SUPERAGENT_SCRIPTS` and read the skill file directly (this is a headless `claude -p` call, so it cannot
run a slash command or rely on `${CLAUDE_PLUGIN_ROOT}`, which is undefined outside a live tool-execution
context — superloop L2 Driver B):

```
cd "$primary_root"
PLUGIN_ROOT="$(cd "$SUPERAGENT_SCRIPTS/.." && pwd)"
claude -p "Read ${PLUGIN_ROOT}/skills/superagent/SKILL.md and run exactly ONE --tick on loop file <LOOP_FILE>. The pending decision is answered: <ANSWER>. Apply it and continue the tick." --allowedTools "Read,Edit,Write,Bash,Task,Skill"
```

**Path B — answer injection (durable, no tick now).** Write `answer: <option>` under `## Pending
decision`; the next scheduled tick polls and resumes. Hold the loop's own lock so you never race a poll
tick:

```
d="$(dirname "<LOOP_FILE>")"; b="$(basename "<LOOP_FILE>")"
if mkdir "$d/.$b.lockd" 2>/dev/null; then
  # edit <LOOP_FILE>: add `answer: <option>` under ## Pending decision
  rm -rf "$d/.$b.lockd"
else
  echo "a tick holds the lock; retry shortly"   # do NOT edit while held
fi
```

Never call `AskUserQuestion`/`AskQuestion` on behalf of a *headless* tick — that is the driver's job to
avoid. This skill is the interactive plane, so `AskQuestion` here (to the human at the console) is correct.

## Step 3 — Lifecycle actions (confirm destructive ones first)

All wrap the existing driver scripts; run them from `primary_root` via `$SUPERAGENT_SCRIPTS`. **Ask the
user before any stop / uninstall / purge.**

- **Drain (graceful stop):** `$SUPERAGENT_SCRIPTS/uninstall-timer.sh <slug>` — disables the timer so no
  new ticks fire; a **running tick finishes on its own** (it is not killed). Leaves the loop file + env
  so it can be re-armed.
- **Hard stop (halt an in-flight tick):** after confirming, `systemctl --user stop
  superagent-tick@<slug>.service`. Abrupt — leaves a stale lock (auto-stolen on the next tick: at once
  when its recorded owner PID is dead, else after `SUPER_LOCK_STEAL_MIN` minutes, default 90) and a
  persisted `PLANNING`/`RUNNING` state, both self-healed by crash-recovery on
  the next run. May interrupt a git/PR/CI op. Prefer drain unless an immediate halt is needed.
- **Force-stop a HUNG tick (halt + reap the lock now):** when a tick is wedged (transient status + held
  lock + no progress) and you don't want to wait out the `SUPER_LOCK_STEAL_MIN`-minute (default 90)
  lock-steal, use the `superagent:superagent-force-stop` skill
  (`$SUPERAGENT_SCRIPTS/force-stop.sh (<PLAN.md> | --slug <slug>) [--apply]`). It halts the tick,
  removes the stale `.lockd`, and kicks a recovery tick so the loop self-heals immediately (dry-run first;
  confirm before `--apply`). This is the recover-a-stuck-loop path; plain hard stop above just halts.
- **Uninstall a DONE loop:** `$SUPERAGENT_SCRIPTS/uninstall-timer.sh <slug>` (add `--purge` to also drop
  `<slug>.env`) — confirm `--purge`.
- **Re-arm a stopped loop:** `$SUPERAGENT_SCRIPTS/install-timer.sh <slug> <LOOP_FILE>`
  (re-pass `--interval`/`--timeout`/`--model` — `install-timer.sh` rewrites the env file and drop-in
  from scratch). No `bootstrap.sh` needed when the loop file still exists.
- **Tail output:** `journalctl --user -u superagent-tick@<slug>.service -f` or
  `tail -f /tmp/superagent-<loop-basename>.log`. Verbatim per-tick reports land here.

## Safety invariants

- **Read-only enumeration (Step 1) is always safe** and never affects loop progress — start/stop this
  monitor freely.
- **Locks are load-bearing.** Only edit a loop-status file (Path B) while holding that loop's
  `.<loop>.lockd`; never touch a loop whose `LOCK=yes`/`TICK=yes` without the lock.
- **Confirm before destructive actions** (hard stop, `--purge`). Drain and re-arm are reversible.
- **Operate per `primary_root`.** The loop files and locks exist only in the primary checkout; a `<slug>`
  with a missing loop file is a resume-via-bootstrap situation, not an error to paper over.
