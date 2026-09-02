---
name: superagent-stop
description: Use to stop a superagent EXTERNAL (unattended) loop for a goal, given only the goal's root master plan (PLAN.md). Complements superagent-external. Default is a graceful drain (disable the timer; a running tick finishes); optional --hard halts an in-flight tick immediately and --purge removes the per-goal env file. The loop-status file is always preserved so the loop can be relaunched.
argument-hint: "<PLAN.md> [--hard] [--purge]"
license: MIT
related skills: superagent-external, superagent-monitor, superagent-force-stop, superagent, superloop
---

<!-- GENERATED FILE — Cursor build. Do not edit by hand: edit the canonical skill under skills/
     in the plugin repository and re-run scripts/build-cursor-skills.sh. -->

> **Cursor build notes.**
> - Only the **external** driver exists in this build. Claude Code's in-session cron driver and its
>   `CronCreate` / `CronList` / `CronDelete` and `Monitor` tools do **not** exist on Cursor — treat
>   any residual mention of them as inapplicable and NEVER attempt those tool calls.
> - Tool mapping: "Agent tool" = spawn a subagent (synchronously — wait for its result). "Skill
>   tool" = invoke a skill. `AskUserQuestion` / `AskQuestion` = ask the user in chat (attended
>   sessions only — never in a headless tick). `EnterWorktree` = not available; where a skill
>   manages worktrees, use `git worktree` via shell. "Desktop routine" = a Claude Desktop feature,
>   not available — use an OS scheduler. A role whose `.superenv` value names another harness
>   (`codex:gpt-5.6-sol`, `pi:openai/gpt-5`, …) is BRIDGED: dispatch it with
>   `subagent_type: super-<role>` — the relay definition `superagent:init` generates — and treat a
>   reply beginning `BRIDGE-FAILED` as a failed subagent.
> - `${SUPER_PLUGIN_ROOT}` in commands and paths = this plugin's installed root directory (the one
>   containing `skills/` and `templates/`, two levels above this SKILL.md). Substitute its absolute
>   path wherever it appears.
> - Skill names are **unprefixed** on Cursor: `superagent:superplan` means the `superplan` skill
>   from this plugin, `superpowers:subagent-driven-development` means `subagent-driven-development`,
>   and so on — strip the `<plugin>:` prefix when looking a skill up. The `superagent` supervisor
>   skill itself carries `disable-model-invocation` and is invisible to model-driven skill lookup —
>   it is driven by reading its SKILL.md directly (the external tick's file-read prompt), never
>   invoked by name.

# Superagent stop

One-step stopper for an unattended superagent loop — the complement of
`superagent-external`. It wraps the deterministic `${SUPER_PLUGIN_ROOT}/scripts/stop.sh`,
which identifies the installed loop from the master plan and disarms its per-goal
scheduler entry (systemd user timer on Linux, launchd LaunchAgent on macOS).

## Repo configuration (.superenv)

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${SUPER_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.superenv" "${SUPER_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
(checking the env var first, and anchoring at the primary checkout so worktrees resolve the same config). A repo with no `.superenv` runs on the shipped defaults.

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
   worktree, resolve `primary_root`), and set `$SUPERAGENT_SCRIPTS` to this plugin's
   installed `scripts/` directory — see [scripts/README.md](../../scripts/README.md)
   for the convention:

   ```
   primary_root="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
   SUPERAGENT_SCRIPTS="${SUPER_PLUGIN_ROOT}/scripts"   # CLAUDE_PLUGIN_ROOT is set in Claude Code sessions;
   # for cron/systemd use the absolute install path — see scripts/README.md
   ```
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
  `--hard` here only halts and leaves the stale lock to the next tick's steal (immediate
  when the recorded owner PID is dead, else the `SUPER_LOCK_STEAL_MIN`-minute (default 90)
  window); `superagent-force-stop` reaps the lock and kicks a recovery tick
  so the loop self-heals at once.
