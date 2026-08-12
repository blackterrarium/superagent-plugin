---
name: init
description: Bootstrap a repository for the superagent plugin — verify prerequisites, create the .superenv config, create and seed the goal vault if absent, and add the loop-status gitignore entry. Idempotent; safe to re-run. Run this once per repo before supergoal/superagent.
license: all rights reserved
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
>   not available — use an OS scheduler.
> - `${SUPER_PLUGIN_ROOT}` in commands and paths = this plugin's installed root directory (the one
>   containing `skills/` and `templates/`, two levels above this SKILL.md). Substitute its absolute
>   path wherever it appears.

# superagent:init — repo bootstrap

Prepare the current repository to run the superagent skill family. Every step is
idempotent: report what was **done** vs **already present**; never overwrite existing
files. Finish with a summary table of step → done/skipped.

Invoke this skill explicitly as `superagent:init` — a built-in `init` skill (CLAUDE.md
authoring) ships unscoped in most sessions, so the bare name `init` is ambiguous the
moment both are available.

**Harness check (belt-and-suspenders).** This is the **Cursor** build of the superagent plugin
(generated — see the banner above). If you are running under Claude Code — e.g. the
`CLAUDE_PLUGIN_ROOT` environment variable is defined in your tool environment — STOP and report: the wrong harness
build is loaded; install the Claude Code plugin from the repository root instead. Also make sure
only one build of this plugin is loaded at a time (if Cursor's "Include third-party Plugins,
Skills, and other configs" setting is loading the Claude Code build alongside this one, disable
that for this plugin — the two inits collide).

## Repo configuration (.superenv)

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${SUPER_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.superenv" "${SUPER_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
(checking the env var first, and anchoring at the primary checkout so worktrees resolve the same config). A repo with no `.superenv` runs on the shipped defaults —
which is exactly the case Step 2 below fixes by creating one.

## Step 1 — Prerequisite checks

1. `git rev-parse --path-format=absolute --git-common-dir` succeeds — else ABORT: "init
   must run inside a git repository." Derive `<repo-root>` as the `dirname` of that path
   — the same `primary_root()` formula `skills/superloop/SKILL.md`'s L1 clause uses:
   `dirname "$(git rev-parse --path-format=absolute --git-common-dir)"`. In the primary
   checkout, `--git-dir` == `--git-common-dir` (both `.git`); in a linked worktree they
   differ (`--git-dir` → `<primary>/.git/worktrees/<name>`, `--git-common-dir` →
   `<primary>/.git`), so `dirname` of the common dir is the primary checkout root —
   regardless of the primary's current branch. **Never** use `git rev-parse
   --show-toplevel` for this: inside a linked worktree (e.g. one `EnterWorktree` created
   for plan execution) it returns the *worktree* root, and init would bootstrap a
   throwaway checkout instead of the primary repo every other superagent skill actually
   reads `.superenv`/`SUPER_GOAL_ROOT` from. `cd` to `<repo-root>` (or prefix every
   relative read in Steps 2-5 with it) before continuing — the `.superenv` resolver above
   greps a bare `.superenv` relative to the current directory, so without this, invoking
   init from a subdirectory (of either the primary checkout or a worktree) would silently
   read the wrong file, or none, and fall through to plugin defaults instead of the
   repo's actual config.
2. The `superpowers` plugin is resolvable (its skills, e.g. `superpowers:writing-plans`,
   appear in the available-skills list). If not: WARN with install instructions
   (`/plugin marketplace add obra/superpowers-marketplace`, `/plugin install superpowers`)
   — planning skills (`supergoal`, `superplan`) work without it, but `superrun` requires
   `superpowers:subagent-driven-development` to execute a plan and will refuse.
3. `gh auth status` succeeds — else WARN (PR-based flows need it; planning artifacts are
   drafted either way, but `superauthor`'s A7 commit-and-merge step and every CI/PR
   operation in `superplan`/`superrun` need it). On a macOS host, a sandboxed `gh auth
   status` can fail even when `gh` is actually authenticated, because `gh` needs keychain
   access the tool sandbox blocks — see `SUPER_GH_DISABLE_SANDBOX` in
   `${SUPER_PLUGIN_ROOT}/templates/superenv.default`. If the check fails on macOS, note
   that possibility rather than reporting a bare WARN.
4. Informational: external (unattended) mode runs on Linux (systemd user timers) and
   macOS (launchd LaunchAgents — logged-in + awake only; crontab fallback documented in
   [scripts/README.md](../../scripts/README.md#cron-fallback-instead-of-systemd)). Run
   `uname -s` and say which scheduler this host would use — planning-only usage
   (`supergoal`/`superplan`) is host-independent.

## Step 2 — Config

If `<repo-root>/.superenv` does not exist, copy
`${SUPER_PLUGIN_ROOT}/templates/superenv.default` to `<repo-root>/.superenv` (keep the
comments — the repo edits knobs in place). If it exists, leave it untouched and report
any `SUPER_*` keys the shipped default defines that the existing file lacks — diff the
key names (`grep -oE '^SUPER_[A-Z_]+='` on each file) rather than the full lines, since
an intentionally edited value is not a gap. This is informational only: a missing key
falls through to the plugin default per the resolution order above.

## Step 3 — Role agents (full model IDs only)

Nine `SUPER_MODEL_*` role keys dispatch through subagents — all but
`SUPER_MODEL_SUPERVISOR`, which the external tick passes straight to `agent --model`.
On Cursor, valid model values are Cursor model names (see `agent --list-models`) or
`inherit`. Any value other than `inherit` is pinned via a generated per-role agent
definition — the definition's `model:` frontmatter carries the name. Claude Code tier
names (`sonnet` | `opus` | `haiku` | `fable`) and Claude model IDs (`claude-*`) are
NOT valid Cursor model names unless they appear in `agent --list-models`: if a
resolved value is one of these and not listed there, WARN and treat it as `inherit`.

Resolve each key below per the resolution order above:

| Key | Generated definition |
|---|---|
| SUPER_MODEL_PLANNER | `.cursor/agents/super-planner.md` |
| SUPER_MODEL_EXECUTOR | `.cursor/agents/super-executor.md` |
| SUPER_MODEL_PANEL | `.cursor/agents/super-panel.md` |
| SUPER_MODEL_IMPLEMENTER | `.cursor/agents/super-implementer.md` |
| SUPER_MODEL_FIX_APPLIER | `.cursor/agents/super-fix-applier.md` |
| SUPER_MODEL_TASK_REVIEWER | `.cursor/agents/super-task-reviewer.md` |
| SUPER_MODEL_RE_REVIEWER | `.cursor/agents/super-re-reviewer.md` |
| SUPER_MODEL_BRANCH_REVIEWER | `.cursor/agents/super-branch-reviewer.md` |
| SUPER_MODEL_FIX_PLANNER | `.cursor/agents/super-fix-planner.md` |

- **Value is a model name (anything valid other than `inherit`):** render
  `${SUPER_PLUGIN_ROOT}/templates/super-role-agent.md` to the listed path (create
  the agents directory if needed), substituting `<role>` (the path's `super-` suffix,
  e.g. `planner`), `<KEY>`, and `<model-id>`. These files are **derived artifacts
  owned by init** — the `generated-by: superagent:init` marker line says so — and
  rewriting one whose model drifted from `.superenv` is the point of this step, not
  an overwrite violation. Never touch a file at these paths that lacks the marker:
  report it as `conflict` and leave it.
- **Value is `inherit` (or invalid → treated as `inherit`), but the listed path
  exists with the marker:** delete it (a stale derived artifact) and report
  `removed (stale)`.
- **Value is `inherit`, no file present:** nothing to do.

Agent definitions load at session start, so files written here take effect from the
next tick/session, not the current one. Report per-key results (`generated` /
`regenerated` / `unchanged` / `removed (stale)` / `conflict` / `n/a`) as one summary
row.

Note: permission layers commonly treat `.cursor/` as protected — in a headless or
auto-accept session the write may be auto-denied even when other edits sail through.
init is an attended bootstrap step; if the write prompts, it needs a human approval,
and if it is denied, report the role as blocked rather than retrying.

## Step 4 — Vault

Resolve `SUPER_GOAL_ROOT` per the resolution order above (shipped default `vault`; a
worked example from the originating repo sets it to `vault/network-compose`). Three cases:

- `<repo-root>/<SUPER_GOAL_ROOT>` does not exist: create it and copy
  `${SUPER_PLUGIN_ROOT}/templates/vault-root.md` to `<SUPER_GOAL_ROOT>/root.md`.
- the directory exists but has no `root.md`: seed `root.md` from the same template.
  Writing a file that is currently absent is not an overwrite, so the intro's
  never-overwrite invariant still holds. `root.md` is not a precondition any skill
  requires — it exists so the goal root has a human-maintained, navigable index of goals
  and lessons from the moment it exists. Leaving it unseeded would silently leave that
  index missing, and because this case only re-checks "does the directory exist," a later
  re-run of init would never heal it — seeding on every run when `root.md` is specifically
  missing is what makes this case actually idempotent-and-self-healing rather than
  idempotent-and-stuck.
- the directory exists and already has a `root.md`: touch nothing.

Report which of the three happened in the summary table — `created` / `seeded root.md
into existing goal root` / `already present` — rather than collapsing the middle case
into either of the other two rows.

## Step 5 — Gitignore

Before appending anything in this step, ensure `<repo-root>/.gitignore` (if it already
exists and is non-empty) ends with a newline — if its last byte is not `\n`, run
`printf '\n' >> .gitignore` first, so an append below never fuses onto the file's last
existing line.

Resolve `SUPER_LOOP_STATUS_DIRNAME` per the resolution order above (shipped default
`loop-status`). Append the line `<SUPER_GOAL_ROOT>/**/<SUPER_LOOP_STATUS_DIRNAME>/` to
`<repo-root>/.gitignore` unless an identical line is already present (create
`.gitignore` if absent). This is the exact pattern `superloop`'s L1 clause documents as
gitignored local-only state (worked example from the originating repo: `vault/**/loop-status/`) — every loop-status
file `superagent`/`superagent-external` write must never be tracked or swept into a
docs-only PR commit.

Also append the line `.env` to `<repo-root>/.gitignore` unless an identical line is
already present (same idempotent check, same newline guard). External (unattended) mode
directs `CURSOR_API_KEY`/`GH_TOKEN` into `<repo>/.env` (see `scripts/README.md`'s
Prerequisites), and that file must never be committed.

## Step 6 — Landing

init only prepares files — it never commits. Tell the user what to commit
(`.superenv`, the vault seed, any generated `.cursor/agents/super-*.md` role
definitions, `.gitignore` — now covering both the loop-status pattern
and `.env`) and remind them to follow the repo's own change discipline: if
`SUPER_PROTECTED_MAIN=true` (the shipped default), that means a feature branch + PR, same
as every `superauthor`-driven skill's own A7 commit step. `.env` itself (holding
`CURSOR_API_KEY`/`GH_TOKEN`) stays gitignored and is never committed — only the
`.gitignore` entry that excludes it is.
