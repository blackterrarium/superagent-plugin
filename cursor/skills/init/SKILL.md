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
5. **Bridge targets.** For every harness that appears as a *bridged* role harness in the resolved
   config (item 5 of the validation below): its CLI must be on PATH — `claude`, `codex`, `agent`
   (Cursor), `pi` — else **ABORT** with an install hint (claude: `npm install -g
   @anthropic-ai/claude-code`; codex: `npm install -g @openai/codex`; cursor: the Cursor CLI
   installer; pi: `npm install -g @earendil-works/pi-coding-agent`). Auth is WARN-only: codex →
   `OPENAI_API_KEY` set or `~/.codex/auth.json` present; pi → for a `<provider>/` of `openai` or
   `anthropic`, `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` set; claude/cursor → binary only.
   Also run `bash "${SUPER_PLUGIN_ROOT}/scripts/role-bridge.sh" 2>&1 | head -1` — a usage line
   proves the bridge shipped with this build; a "not found" is a broken install: ABORT.

## Step 2 — Config

If `<repo-root>/.superenv` does not exist, copy
`${SUPER_PLUGIN_ROOT}/templates/superenv.default` to `<repo-root>/.superenv` (keep the
comments — the repo edits knobs in place). If it exists, leave it untouched and report
any `SUPER_*` keys the shipped default defines that the existing file lacks — diff the
key names (`grep -oE '^SUPER_[A-Z_]+='` on each file) rather than the full lines, since
an intentionally edited value is not a gap. This is informational only: a missing key
falls through to the plugin default per the resolution order above.

### .superenv validation (lint — WARN + fallback, never abort — one exception)

Validate the RESOLVED configuration (env > repo `.superenv` > plugin default) before
using it. For each finding emit one WARN row in the summary; the effective value used
by later steps is the fallback shown. Never rewrite the user's `.superenv` — this is
report-only. There is exactly one exception to "never abort": a foreign harness on
`SUPER_MODEL_SUPERVISOR` (item 5) stops init.

1. **Unknown keys:** every `SUPER_*`/`TICK_*` key present in the repo `.superenv` must
   also exist in `${SUPER_PLUGIN_ROOT}/templates/superenv.default`. Unknown → WARN
   "probable typo (ignored)". (Exception: a harness-specific key that belongs to another
   build's template — e.g. `SUPER_CODEX_SANDBOX` on a build whose template drops it — is
   a legitimate key in a portable `.superenv`: report it as `ignored (other-harness
   key)`, not as a typo.)
2. **Enums** (out-of-domain → WARN, fall back to the template default):
   `SUPER_HARNESS` ∈ claude|cursor|codex|pi; `SUPER_CODEX_SANDBOX` ∈
   workspace-write|danger-full-access; `SUPER_TEST_EVIDENCE` ∈ local|ci;
   `SUPER_MERGE_METHOD` ∈ squash|merge|rebase; `SUPER_BRANCH_STYLE` ∈ flat|slashed;
   `SUPER_PANEL_AGENT_TYPE` ∈ general-purpose|Explore;
   `SUPER_REVIEW_CONFIDENCE_FILTER` ∈ controller; `SUPER_PI_SUBAGENTS` ∈
   recommended|required|off.
3. **Booleans** (∈ true|false, else WARN + template default): `SUPER_PROTECTED_MAIN`,
   `SUPER_ADMIN_MERGE`, `SUPER_CI_ONE_FLAG_PER_PUSH`, `SUPER_SKIP_FINISHING_HANDOFF`,
   `SUPER_GH_DISABLE_SANDBOX`.
4. **Numerics** (positive integer, else WARN + template default):
   `SUPER_HEAVY_STEP_LIMIT`, `SUPER_LOCK_STEAL_MIN`, `SUPER_CI_RUNNERS`.
   `SUPER_TICK_INTERVAL` must parse as an interval span (e.g. `600`, `90s`, `30m`, `2h`).
5. **Model keys** (each `SUPER_MODEL_*`): grammar `inherit | [<harness>:]<model>`, `<harness>` ∈
   `claude|codex|cursor|pi`. Resolve each key's **harness** by taking the FIRST arm that matches:
   (a) the value is literally `inherit`, or empty/unset → harness = `SUPER_HARNESS` (i.e. always
   **native**), the key has no model, and inference is skipped entirely — this is the normal case
   and never WARNs; (b) an explicit `<harness>:` prefix → that harness; (c) otherwise infer —
   `sonnet|opus|haiku|fable|claude-*` → `claude`; `gpt-*|o<digit>*|codex*` → `codex`; a value
   containing `/` → `pi`;
   anything else → `cursor`, i.e. **native**: Cursor model names are free-form (cf.
   `agent --list-models`), so a bare value matching no prefix and no pattern above is taken as a
   Cursor model name — checked below against the model list rather than rejected here. Arm (c)
   still runs first, so a Codex-looking name such as `gpt-5` infers `codex` and is therefore
   **bridged**; write `cursor:gpt-5` to run that same name natively on Cursor.
   Strip the prefix to get the **model**. The role is **native** when its harness equals
   `SUPER_HARNESS`, else **bridged** — so an arm-(a) `inherit` role is always native, item 6
   validates its effort in `SUPER_HARNESS`'s domain, and its summary row shows harness =
   `SUPER_HARNESS`. `SUPER_MODEL_SUPERVISOR` must be native: a foreign harness there is a **hard
   error** (stop and report; the tick refuses it too) — `SUPER_MODEL_SUPERVISOR=inherit` satisfies
   this trivially.
   Native model values are further validated per build:
   a Cursor model name (`agent --list-models`) or `inherit`; a name not in that list → WARN, treat
   as `inherit` (catches typos before they become an agent definition that fails at spawn time).
   Bridged model values are not validated beyond the grammar (the foreign CLI owns its names), except
   `pi`, whose model must contain exactly one `/` (`<provider>/<model>`).
   `SUPER_BRIDGE_RELAY_MODEL` is validated as a native model value (invalid → WARN, treat as
   `inherit`).
6. **Effort keys** (each `SUPER_EFFORT_<ROLE>`): valid in the domain of the ROLE's harness (from
   item 5; the supervisor's harness is `SUPER_HARNESS`): claude `low|medium|high|xhigh|max`;
   codex `none|minimal|low|medium|high|xhigh` (no `max`); pi `off|minimal|low|medium|high|xhigh|max`;
   cursor: `inherit` only. `inherit` is always valid. Out of domain → WARN, treat as `inherit`.

## Step 3 — Role agents (model/effort pins)

Nine `SUPER_MODEL_*` role keys dispatch through subagents — all but
`SUPER_MODEL_SUPERVISOR`, which the external tick passes straight to `agent --model`.
On Cursor, a **native** model value is a Cursor model name (see `agent --list-models`)
or `inherit`; any native value other than `inherit` is pinned via a generated per-role
agent definition — the definition's `model:` frontmatter carries the name. Claude Code
tier names (`sonnet` | `opus` | `haiku` | `fable`) and Claude model IDs (`claude-*`)
are NOT discarded: under item 5's grammar they resolve to harness `claude`, which is
foreign to this build, so such a role is **bridged** and gets a relay definition
instead of being treated as a typo.

Resolve each role's model key (`SUPER_MODEL_<ROLE>`) and effort key (`SUPER_EFFORT_<ROLE>`), using the validated values from the validation step above:

| Model key | Effort key | Generated definition |
|---|---|---|
| SUPER_MODEL_PLANNER | SUPER_EFFORT_PLANNER | `.cursor/agents/super-planner.md` |
| SUPER_MODEL_EXECUTOR | SUPER_EFFORT_EXECUTOR | `.cursor/agents/super-executor.md` |
| SUPER_MODEL_PANEL | SUPER_EFFORT_PANEL | `.cursor/agents/super-panel.md` |
| SUPER_MODEL_IMPLEMENTER | SUPER_EFFORT_IMPLEMENTER | `.cursor/agents/super-implementer.md` |
| SUPER_MODEL_FIX_APPLIER | SUPER_EFFORT_FIX_APPLIER | `.cursor/agents/super-fix-applier.md` |
| SUPER_MODEL_TASK_REVIEWER | SUPER_EFFORT_TASK_REVIEWER | `.cursor/agents/super-task-reviewer.md` |
| SUPER_MODEL_RE_REVIEWER | SUPER_EFFORT_RE_REVIEWER | `.cursor/agents/super-re-reviewer.md` |
| SUPER_MODEL_BRANCH_REVIEWER | SUPER_EFFORT_BRANCH_REVIEWER | `.cursor/agents/super-branch-reviewer.md` |
| SUPER_MODEL_FIX_PLANNER | SUPER_EFFORT_FIX_PLANNER | `.cursor/agents/super-fix-planner.md` |


(`super-executor.md` is generated for completeness, but the `superagent` loop does not dispatch
`superrun` through it: the executor always runs as the top-level agent of its own CLI process via
`role-bridge.sh --tools executor`, taking `SUPER_MODEL_EXECUTOR` / `SUPER_EFFORT_EXECUTOR` directly —
see superagent **Subagent dispatch**, issue #25.)

- **Bridged role (its harness ≠ `SUPER_HARNESS`):** render
  `${SUPER_PLUGIN_ROOT}/templates/super-role-bridge-agent.md` to the listed path, substituting
  `<role>`, `<KEY>` (both keys), `<harness>`, `<model>` (prefix stripped), `<effort>` (`inherit`
  when unset/invalid), `<relay-model>` = `SUPER_BRIDGE_RELAY_MODEL` (drop the `model:` line when
  `inherit`), and `<bridge-path>` = the absolute path of
  `${SUPER_PLUGIN_ROOT}/scripts/role-bridge.sh`. The `generated-by: superagent:init`
  marker/ownership rules stated in the native bullets below apply to this file too (never
  overwrite an unmarked file at that path — report `conflict` and leave it), but the native
  bullets' case selection does not apply to a bridged role. A bridged panel role ignores
  `SUPER_PANEL_AGENT_TYPE` (WARN once).
- **Native role whose value is a model name (anything valid other than `inherit`):** render
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
Effort keys are not supported for *native* Cursor roles: a native role's non-inherit
SUPER_EFFORT_* value → WARN and treat as inherit (never render an effort: line). A bridged role's
effort was validated in its own harness's domain (item 6) and is passed through to the relay.

Agent definitions load at session start, so files written here take effect from the
next tick/session, not the current one.
Report one summary row per role: `role · harness · model · effort · dispatch` where dispatch is
`native`, `native (definition: generated|regenerated|unchanged|removed (stale)|conflict)`,
`bridge(<harness>)`, or `bridge(<harness>, definition: conflict)` — a bridged role whose
relay definition could not be written (hand-edited file kept, or the write was denied).

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
