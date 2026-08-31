---
name: superagent-force-stop
description: Use to recover a HUNG or wedged superagent EXTERNAL tick — a loop stuck at a transient status (RUNNING/PLANNING) with the L3 overlap lock held and no forward progress (e.g. a tick process that hung, or a tick killed mid-flight that orphaned its lock). Halts the in-flight tick, reaps the stale `.lockd` lock so the loop self-heals immediately instead of waiting out the 90-min lock-steal window, and (by default) kicks a fresh recovery tick. Distinct from superagent-stop (which disarms the scheduler for a healthy loop); this is the force/recover path for a stuck one. Identify the loop by its root master plan (PLAN.md) or --slug.
argument-hint: "(<PLAN.md> | --slug <goal-slug>) [--drain] [--no-kick]"
license: all rights reserved
related skills: superagent-monitor, superagent-stop, superagent-external, superagent, superloop
---

<!-- GENERATED FILE — Pi build. Do not edit by hand: edit the canonical skill under skills/
     in the plugin repository and re-run scripts/build-pi-skills.sh. -->

> **Pi build notes.**
> - Only the **external** driver exists in this build. Claude Code's in-session cron driver and its
>   `CronCreate` / `CronList` / `CronDelete` / `Monitor` / `AskUserQuestion` tools do **not** exist
>   on Pi — treat any residual mention as inapplicable and NEVER attempt those tool calls.
> - Tool mapping in the SUPERVISOR (`superagent`, `superloop`): "Agent tool" / "dispatch a
>   subagent" = a blocking `bash` call to `${SUPER_PLUGIN_ROOT}/scripts/role-bridge.sh`
>   (`superplan`, `superrun`) or `${SUPER_PLUGIN_ROOT}/scripts/bridge-fanout.sh` (the L7 panel),
>   per the Pi-specific guidance embedded in those skills. The supervisor never uses a subagent tool.
> - Tool mapping in `superrun` (the SDD controller): "dispatch a subagent" = the `subagent` tool
>   from the `pi-subagents` package with `async: false`, one child per call; role pins ride the
>   `.pi/agents/super-<role>.md` definitions `init` generates. If the tool is absent, follow SDD's
>   sequential fallback and report it.
> - "Skill tool / invoke skill X" = `read` `${SUPER_PLUGIN_ROOT}/skills/X/SKILL.md` and follow it
>   (`/skill:` commands are interactive-only). Superpowers skills are listed by Pi from the
>   installed `superpowers` package — reference them by name.
> - `${SUPER_PLUGIN_ROOT}` = the plugin repository's `pi/` directory (two levels above each
>   SKILL.md). It contains `skills/`, `templates/`, and `scripts/` (`role-bridge.sh`,
>   `bridge-fanout.sh`, `_common.sh`). The external-driver wrappers (`superagent-tick.sh`,
>   `launch.sh`, …) live in the repository's top-level `scripts/` — one directory up.
> - `EnterWorktree` = not available; use `git worktree` via `bash`.

# Superagent force-stop

Recovery path for a **hung** superagent external tick — the complement of
`superagent-stop` (which gracefully disarms the scheduler of a *healthy* loop).
It wraps the deterministic `${SUPER_PLUGIN_ROOT}/scripts/force-stop.sh`, which halts the
wedged tick and removes the stale **L3 overlap lock** so the loop resumes at once
instead of waiting out the `SUPER_LOCK_STEAL_MIN`-minute (default 90) lock-steal window.

## Repo configuration (.superenv)

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${SUPER_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.superenv" "${SUPER_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
(checking the env var first, and anchoring at the primary checkout so worktrees resolve the same config). A repo with no `.superenv` runs on the shipped defaults.

Everything here runs on the **host that runs the loops** (the primary checkout
holding the gitignored `<SUPER_LOOP_STATUS_DIRNAME>/` files — worked example from the
originating repo: `SUPER_LOOP_STATUS_DIRNAME=loop-status` — and the `.<loop>.lockd`
locks). Resolve `primary_root` first if invoked from a worktree, set
`$SUPERAGENT_SCRIPTS` to this plugin's installed `scripts/` directory (see
[scripts/README.md](../../scripts/README.md) for the convention), and run the script
from `primary_root`:

```
primary_root="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
SUPERAGENT_SCRIPTS="${SUPER_PLUGIN_ROOT}/scripts"   # CLAUDE_PLUGIN_ROOT is set in Claude Code sessions;
# for cron/systemd use the absolute install path — see scripts/README.md
```

## When to use this (vs superagent-stop)

Reach for force-stop only when a tick is genuinely **stuck**, diagnosed via the
`superagent:superagent-monitor` skill (`status.sh <slug>`):

- `STATUS` is a **transient** (`RUNNING` / `PLANNING`) **and** `LOCK=yes`, but the
  tick is making no progress — either the tick process has hung (`TICK=yes`/`activating`
  for far longer than the work should take) or a prior tick was killed and left an
  **orphaned lock** (`TICK=no` but `LOCK=yes`).
- You do **not** want to wait for the automatic `SUPER_LOCK_STEAL_MIN`-minute
  (default 90) lock-steal self-heal.

If the loop is **healthy** and you simply want to pause/stop it, use the
`superagent:superagent-stop` skill (graceful drain). If a tick is legitimately
mid-flight (e.g. driving a long CI push — ticks run uncapped by default), it is
**not** hung; leave it alone. Never force-stop a tick that is doing real work.

## Parameters

- **`<PLAN.md>` or `--slug <goal-slug>` — one is required.** Identify the loop by its
  **root** master plan (matched against the registered env files, like
  `superagent-stop`) or directly by slug.
- **`--drain` — optional.** After cleanup, also disable the timer (stop the loop).
  Default keeps the timer armed so the loop resumes.
- **`--no-kick` — optional.** Do not immediately start a recovery tick after cleanup.
  Default kicks one (when the timer stays armed) for immediate self-heal.

The script is **DRY-RUN by default**; the steps below run the preview first, confirm
with the human, then re-run with `--apply`.

## Steps

1. **Resolve the repo root** (run from the primary checkout): see **Repo
   configuration (.superenv)** above.
2. **Diagnose first with the `superagent:superagent-monitor` skill.** Confirm the
   loop is actually stuck (transient status + held lock + no progress). If it is
   healthy or a tick is doing real work, STOP — force-stop is the wrong tool.
3. **Preview (dry-run).** From `primary_root`:

   ```
   $SUPERAGENT_SCRIPTS/force-stop.sh (<PLAN.md> | --slug <slug>) [--drain] [--no-kick]
   ```

   It prints the target's status/iteration, whether the tick service is active,
   whether the lock is held (and its age), the planned post-action, and any
   worktrees to review — changing nothing.
4. **Confirm with the human** (`AskQuestion`), showing the dry-run summary. Halting a
   tick and removing its lock is destructive — get explicit consent before applying.
5. **Apply.** Re-run with `--apply` appended:

   ```
   $SUPERAGENT_SCRIPTS/force-stop.sh (<PLAN.md> | --slug <slug>) --apply [--drain] [--no-kick]
   ```

   It halts the in-flight tick (`systemctl --user stop` reaps the service cgroup,
   including the wrapped `claude` child — precise, no blind `pkill`),
   removes the stale `.lockd`, and either kicks a recovery tick (default) or drains
   the timer (`--drain`).
6. **Report** the outcome and what happens next: the next/kicked tick's
   crash-recovery (superloop L2) resets the persisted `RUNNING`/`PLANNING` →
   `WAITING FOR RUN`/`WAITING FOR PLAN` and re-dispatches. Confirm with the
   `superagent:superagent-monitor` skill after a minute.

## Safety invariants

- **The loop-status file is never edited** by this skill. The status reset is left to
  the next tick's crash-recovery (L2), which owns the `prior_status` handling — the
  script only removes the lock and halts the service, so it can never corrupt the
  state machine.
- **Precise process kill only.** `systemctl --user stop` kills exactly the tick
  service's cgroup. The script never blanket-`pkill`s `claude` (that
  would kill unrelated interactive sessions). If a tick's CLI process is wedged but
  detached from any service cgroup, the script reports it and you must identify +
  kill that PID manually.
- **Worktrees are reported, not removed.** A killed `superrun` tick may leave a
  worktree with uncommitted work; `superrun` reconciles/recreates its own on
  re-dispatch. Review listed worktrees by hand before removing any.
- **Dry-run first, confirm before `--apply`.** Preview and human consent precede any
  mutation.
- **The loop-status file is preserved**, so a `--drain`ed loop relaunches with the
  `superagent:superagent-external` skill (`$SUPERAGENT_SCRIPTS/launch.sh <PLAN.md>`).
