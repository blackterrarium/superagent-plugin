---
name: superagent-stop
description: Use to stop a superagent EXTERNAL (unattended) loop for a goal, given only the goal's root master plan (PLAN.md). Complements superagent-external. Default is a graceful drain (disable the timer; a running tick finishes); optional --hard halts an in-flight tick immediately and --purge removes the per-goal env file. The loop-status file is always preserved so the loop can be relaunched.
argument-hint: "<PLAN.md> [--hard] [--purge]"
license: all rights reserved
related skills: superagent-external, superagent-monitor, superagent-force-stop, superagent, superloop
---

<!-- GENERATED FILE — Codex build. Do not edit by hand: edit the canonical skill under skills/
     in the plugin repository and re-run scripts/build-codex-skills.sh. -->

> **Codex build notes.**
> - Only the **external** driver exists in this build. Claude Code's in-session cron driver and its
>   `CronCreate` / `CronList` / `CronDelete` and `Monitor` tools do **not** exist on Codex — treat
>   any residual mention of them as inapplicable and NEVER attempt those tool calls.
> - Tool mapping: "Agent tool" / "spawn a subagent" = the `spawn_agent` tool (multi-agent v2 —
>   wait for the child's result). Role pins from `.superenv` map to its parameters:
>   `SUPER_MODEL_<ROLE>` → `model`, `SUPER_EFFORT_<ROLE>` → `reasoning_effort`
>   (`inherit` = omit the parameter). There are NO `.claude/agents/` definition files in this
>   build — where a skill says "dispatch via subagent_type: super-<role>", pass the role's
>   resolved model/effort as spawn parameters instead — and any accompanying "missing definition =
>   hard error / re-run `superagent:init`" clause does not apply in this build (there is nothing to
>   generate; a bridged role's relay spawn needs no definition either). A role whose value names
>   another harness (`claude:sonnet`, `pi:openai/gpt-5`, …) is BRIDGED: spawn a relay child
>   (`model` = `SUPER_BRIDGE_RELAY_MODEL`, omit when `inherit`) whose message is
>   `${SUPER_PLUGIN_ROOT}/templates/relay-preamble.md` rendered for that role followed by the task
>   prompt; the relay runs `${SUPER_PLUGIN_ROOT}/scripts/role-bridge.sh` and returns the foreign
>   CLI's result verbatim. "Skill tool" = reference the skill by
>   name in the conversation. `AskUserQuestion` / `AskQuestion` = ask the user in chat (attended
>   sessions only — never in a headless tick). `EnterWorktree` = not available; use
>   `git worktree` via shell.
> - `${SUPER_PLUGIN_ROOT}` in commands and paths = this plugin's installed root (the directory
>   containing `skills/` and `templates/`, two levels above each SKILL.md — for a marketplace
>   install that is the plugin cache copy; in the source repository it is
>   `<repo>/codex/plugins/superagent`). Substitute its absolute path wherever it appears.
>   Exception: the external-driver `scripts/` helpers (`superagent-tick.sh`, `launch.sh`, …) are
>   not packaged inside the plugin — they live in the plugin source repository. Read
>   `${SUPER_PLUGIN_ROOT}/scripts/` as that repository's `scripts/` directory (the
>   `SUPERAGENT_SCRIPTS` convention in its scripts/README.md).
> - Skill lookup: this plugin installs via the Codex plugin marketplace; skills resolve by name
>   (e.g. `superplan`). The `superagent` supervisor skill is driven by reading its SKILL.md
>   directly (the external tick's file-read prompt), never invoked by name.

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
