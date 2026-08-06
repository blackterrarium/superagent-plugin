---
name: superagent-stop
description: Use to stop a superagent EXTERNAL (unattended) loop for a goal, given only the goal's root master plan (PLAN.md). Complements superagent-external. Default is a graceful drain (disable the timer; a running tick finishes); optional --hard halts an in-flight tick immediately and --purge removes the per-goal env file. The loop-status file is always preserved so the loop can be relaunched.
argument-hint: "<PLAN.md> [--hard] [--purge]"
license: all rights reserved
related skills: superagent-external, superagent-monitor, superagent-force-stop, superagent, superloop
---

# Superagent stop

One-step stopper for an unattended superagent loop — the complement of
`superagent-external`. It wraps the deterministic `${CLAUDE_PLUGIN_ROOT}/scripts/stop.sh`,
which identifies the installed loop from the master plan and disarms its per-goal
systemd user timer.

## Repo configuration (.superenv)

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${CLAUDE_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' .superenv "${CLAUDE_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
(checking the env var first). A repo with no `.superenv` runs on the shipped defaults.

## Parameters

- **`<PLAN.md>` — required.** The goal's **root** master plan (the same file passed
  to `superagent-external`). This is the only compulsory argument.
- **`--hard` — optional.** Also halt an in-flight tick immediately (SIGTERM the
  service). Default is a graceful drain: the timer is disabled so no new ticks fire,
  and a tick already running finishes on its own.
- **`--purge` — optional.** Also remove the per-goal env file
  (`~/.config/superagent/<slug>.env`).

When these are absent, DO NOT pass them — default graceful drain, env kept.

## Steps

1. **Resolve the repo root** (run from the primary checkout; if invoked from a
   worktree, resolve `primary_root`):
   `primary_root="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"`.
   Also set `$SUPERAGENT_SCRIPTS` to this plugin's installed `scripts/` directory —
   see [scripts/README.md](../../scripts/README.md) for the convention.
2. **Invoke the stopper** with the parsed arguments, from `primary_root`:

   ```
   $SUPERAGENT_SCRIPTS/stop.sh <PLAN.md> [--hard] [--purge]
   ```

   `stop.sh` finds the installed loop by matching the plan against the registered
   env files (`~/.config/superagent/*.env`) — robust even if a custom `--slug` was
   used at launch — disables + stops the timer, optionally halts the in-flight tick
   (`--hard`) and removes the env file (`--purge`). It **always preserves the
   loop-status file** so the loop can be relaunched/resumed.
3. **Report** the stopper's output: the goal slug, whether a running tick was
   drained vs halted, whether the env was kept vs purged, and the relaunch command.

## Notes

- **Graceful by default.** Without `--hard`, a tick that is mid-flight (e.g. driving
  CI) completes cleanly; only the scheduling stops. Use `--hard` only when you need
  an immediate halt (it may interrupt a git/PR/CI op; the next run self-heals via
  crash recovery).
- **Idempotent / safe.** If no loop is installed for the plan, it reports "nothing
  to stop" and exits 0.
- **Relaunch** later with the `superagent:superagent-external` skill (or
  `$SUPERAGENT_SCRIPTS/launch.sh`); since the loop-status file is preserved, it
  resumes from where it left off.
- To *inspect* rather than stop (or to answer a `WAITING FOR INPUT` decision), use
  the `superagent:superagent-monitor` skill.
- **For a HUNG tick** (stuck at a transient `RUNNING`/`PLANNING` with the lock held and
  no progress) use the `superagent:superagent-force-stop` skill, not this one.
  `--hard` here only halts and leaves the stale lock for the `SUPER_LOCK_STEAL_MIN`-minute
  (default 90) steal; `superagent-force-stop` reaps the lock and kicks a recovery tick
  so the loop self-heals at once.
