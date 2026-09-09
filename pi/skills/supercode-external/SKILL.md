---
name: supercode-external
description: Use when launching or explicitly resuming an unattended coding-loop project through the external scheduler from its approved READY project directory.
argument-hint: "<project-dir> [--slug <slug>] [--interval <interval>]"
license: MIT
related skills: supercode, superloop, superagent-monitor, superagent-stop, superagent-force-stop
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
>   `.pi/agents/super-<role>.md` definitions `init` generates. `pi-subagents` ≥ 0.58.0 is required;
>   if the tool is absent, stop and report the missing prerequisite. No sequential fallback.
> - "Skill tool / invoke skill X" = `read` `${SUPER_PLUGIN_ROOT}/skills/X/SKILL.md` and follow it
>   (`/skill:` commands are interactive-only). Superpowers skills are listed by Pi from the
>   installed `superpowers` package — reference them by name.
> - `${SUPER_PLUGIN_ROOT}` = the plugin repository's `pi/` directory (two levels above each
>   SKILL.md). It contains `skills/`, `templates/`, and `scripts/` (`role-bridge.sh`,
>   `bridge-fanout.sh`, `_common.sh`, `prd-lint.sh`, `supereval.sh`, `_evalspec.sh`). The external-driver wrappers (`superagent-tick.sh`,
>   `launch.sh`, …) live in the repository's top-level `scripts/` — one directory up.
> - `EnterWorktree` = not available; use `git worktree` via `bash`.

# Supercode external

Bootstrap or resume one project's outer registration with the shared launcher. This skill performs
no planning, evaluation, diagnosis or product work. The scheduler starts native `supercode` ticks.
Input is the real project directory; never fabricate PLAN.md or store it as `master_plan`.

1. Resolve physical primary checkout from the Git common directory. Resolve configuration from
   process environment, primary `.superenv`, then plugin defaults. Resolve `SUPER_GOAL_ROOT` with
   `_common.sh` `vault_root`; an external vault must be its own Git repository. Require the project
   is contained in that vault, READY PRD/evaluation/knowledge-base, successful `prd-lint.sh`, and a
   positive `SUPER_CODE_MAX_ITERATIONS`. SUPERVISOR must be native to the selected harness.
2. Read the complete agreement and referenced binding sources as required by `supercode`. Resolve
   the context with `_coding_loop_state.py context --repo PRIMARY --vault VAULT --project PROJECT`,
   supplying revision-labelled captures when required. Missing context refuses launch; do not
   accept an empty manifest as proof no binding sources exist. Do not change approved inputs.
3. Resolve installed helpers from `${SUPER_PLUGIN_ROOT}/scripts` and the diagnosis template from
   this package's `templates/`; missing package files are an installation error, never a reason to
   fall back to a source checkout. Scheduler scripts are source-repository infrastructure in the
   generated packages. Define local `SUPERAGENT_SCRIPTS` from an existing registration's literal
   `SUPERAGENT_SCRIPT_DIR`, or the explicit operator-provided source-repository `scripts/` path.
   Require `launch.sh` and `superagent-tick.sh` in that directory before any scheduler action; do not
   guess by walking above the installed package. Invoke
   `"$SUPERAGENT_SCRIPTS/launch.sh" PROJECT --supervisor supercode` with only requested
   overrides (`--slug`, `--interval`, harness/model/timeout options). The launcher validates identity,
   reuses the existing registered slug/state, and holds project L3 for bootstrap reconciliation.
   Repeat launch reuses the same outer registration. Conflicting identities refuse mutation.
4. Report project, outer slug/state path, scheduler, round/status and the launcher output. Initial
   `agreement_revision: PENDING` is a bootstrap sentinel; the first native tick must establish the
   complete fingerprint before reserving any operation. Existing ledger without durable operation
   provenance parks for explicit author adoption, retaining its round and historical locators.
   Never infer a past PASS or inner DONE from those cells.

Explicitly relaunching authorizes rearming the **outer** registration only. It does not answer an
existing decision, adopt changed criteria, approve a raised round limit, or rearm a stopped child.
Use `superagent-monitor` to inspect both. Stop the outer with `stop.sh PROJECT` or `stop.sh --slug
OUTER`; its output names the remaining child and exact separate stop command. Invoke both stop
operations only when both are requested. Force recovery similarly targets one registration and
reconciles its own phase; preserve both state files and committed artifacts.
