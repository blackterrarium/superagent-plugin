---
name: superagent-external
description: Use to launch a superagent EXTERNAL (unattended) loop for a goal in one step — given only the goal's root master plan (PLAN.md), it prepares the loop-status file and arms the per-goal scheduler entry (systemd user timer on Linux, launchd LaunchAgent on macOS) so the loop runs in the background with no separate console. Optional interval; defaults are used when omitted.
argument-hint: "<PLAN.md> [--interval 30min]"
license: all rights reserved
related skills: superagent, superloop, superagent-monitor
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
>   resolved model/effort as spawn parameters instead. "Skill tool" = reference the skill by
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

# Superagent external launcher

One-step launcher for an unattended superagent loop. It wraps the deterministic
`${SUPER_PLUGIN_ROOT}/scripts/launch.sh`, which prepares the loop-status file and arms the
per-goal **scheduler entry** (systemd user timer on Linux, launchd LaunchAgent on macOS —
auto-detected) — so the loop runs in the background driven by the
scheduler, not by a console you have to keep open. For monitoring/answering/stopping
afterward, use the `superagent:superagent-monitor` skill.

## Repo configuration (.superenv)

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${SUPER_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.superenv" "${SUPER_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
(checking the env var first, and anchoring at the primary checkout so worktrees resolve the same config). A repo with no `.superenv` runs on the shipped defaults.

## Parameters

- **`<PLAN.md>` — required.** The goal's **root** seed/master plan (the same file
  `superrun` traverses / `superplan` descends), living under this repo's goal-folder
  root `<SUPER_GOAL_ROOT>/<STAMP>-<slug>/master-plans/<seed>.md` (shipped default:
  `SUPER_GOAL_ROOT=vault`, giving `vault/<STAMP>-<slug>/master-plans/<seed>.md`;
  worked example from the originating repo, where
  `SUPER_GOAL_ROOT=vault/network-compose`). This is the only compulsory argument.
- **`--interval <systemd time>` — optional**, default `SUPER_TICK_INTERVAL` (default
  `30m`) (e.g. `5min`, `15min`).
- (Also optional: `--timeout <secs>` per-tick cap, default **none/unlimited** so long
  CI-push ticks are never killed; `--slug <name>`
  to override the derived scheduler instance label; `--output stream|text`, default
  `stream` — live incremental console output in the per-tick log, or final-only;
  `--model <slug>` — the tick model, always passed explicitly so it is used
  regardless of the CLI's default. Resolution order: `TICK_MODEL` env var (if set) >
  `SUPER_MODEL_SUPERVISOR` > `opus` — see
  [scripts/README.md](../../scripts/README.md).)

Parse the user's request into these. When the interval is absent, DO NOT pass
the flag — let `launch.sh` apply its defaults.

## Steps

1. **Resolve the repo root** (run from the primary checkout; if invoked from a
   worktree, resolve `primary_root`), and set `$SUPERAGENT_SCRIPTS` to this plugin's
   installed `scripts/` directory — see [scripts/README.md](../../scripts/README.md)
   for the convention (adjust to wherever the plugin is actually installed on this
   host):

   ```
   primary_root="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
   SUPERAGENT_SCRIPTS="${SUPER_PLUGIN_ROOT}/scripts"   # CLAUDE_PLUGIN_ROOT is set in Claude Code sessions;
   # for cron/systemd use the absolute install path — see scripts/README.md
   ```
2. **Invoke the launcher** with the parsed arguments, from `primary_root`:

   ```
   $SUPERAGENT_SCRIPTS/launch.sh <PLAN.md> [--interval <interval>]
   ```

   `launch.sh` will: derive the goal folder + a default slug from `<PLAN.md>`;
   **fail fast** if the `claude` binary or `gh` auth is missing (nothing is armed in
   that case — surface the message); create the loop-status file in the superloop
   L1 format if none exists for this plan, or **reuse** the existing one (so
   re-invoking just re-arms / resumes); install + enable the per-goal timer; and
   kick the first tick immediately.
3. **Report** the launcher's output to the user: the goal slug, interval,
   the loop-file path, and the monitor/stop commands it prints. Confirm the timer
   is scheduled (`$SUPERAGENT_SCRIPTS/status.sh <slug>` shows the row + `gh auth: ok`).

## Notes

- **Prerequisites** (see [scripts/README.md](../../scripts/README.md)): **the
  `superagent` plugin installed AND enabled for headless sessions in the target
  repo** — the tick reads the skill file directly rather than invoking it by name,
  but the loop's internal `superagent:superplan` / `superagent:superrun` dispatches
  still go through the `Skill` tool, so the plugin must still be installed/enabled
  for those to resolve; `launch.sh` does **not** preflight this (only the `claude`
  binary and `gh` auth are fail-fast), so a missing/disabled plugin arms a timer
  whose ticks then fail opaquely — confirm it before launching. Also: the `claude`
  CLI installed, `OPENAI_API_KEY` and ideally `GH_TOKEN` in `.env`, and — for a
  headless server — user lingering (the installer enables it). If `launch.sh`
  reports a gh-auth or claude-binary failure, fix that and re-invoke; it armed
  nothing.
- **Idempotent.** Re-invoking for the same `<PLAN.md>` reuses the existing loop
  file and re-arms the timer; it does not start a duplicate loop or reset progress
  (progress lives in the vault plan tree; the loop file only holds the tick cursor).
- **Root plan must be on `main`.** The loop reads the vault from local `main`, so
  the goal's supergoal PR should be merged and the checkout synced first.
- This skill only *launches*. To watch, answer a `WAITING FOR INPUT` decision, or
  stop/drain a loop, use the `superagent:superagent-monitor` skill (or the
  `${SUPER_PLUGIN_ROOT}/scripts/*` helpers directly).
