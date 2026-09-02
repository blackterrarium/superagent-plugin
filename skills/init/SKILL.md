---
name: init
description: Bootstrap a repository for the superagent plugin — verify prerequisites, create the .superenv config, create and seed the goal vault if absent, and add the loop-status gitignore entry. Idempotent; safe to re-run. Run this once per repo before supergoal/superagent.
license: MIT
---

# superagent:init — repo bootstrap

Prepare the current repository to run the superagent skill family. Every step is
idempotent: report what was **done** vs **already present**; never overwrite existing
files. Finish with a summary table of step → done/skipped.

Invoke this skill explicitly as `superagent:init` — a built-in `init` skill (CLAUDE.md
authoring) ships unscoped in most sessions, so the bare name `init` is ambiguous the
moment both are available.

<!-- cc-only:start -->
**Harness check (belt-and-suspenders).** This is the **Claude Code** build of the superagent
plugin. If `${CLAUDE_PLUGIN_ROOT}` is not defined in your tool environment — i.e. you are not
running as a Claude Code plugin skill — STOP and report: the wrong harness build is loaded. On
Cursor, install the plugin's native Cursor build (the `cursor/` package in this repository)
instead, and make sure only one build of this plugin is loaded at a time (e.g. Cursor's
"Include third-party Plugins, Skills, and other configs" setting must not load the Claude Code
build alongside the native one — the two inits collide).
<!-- cc-only:end -->
<!-- cursor-only:start
**Harness check (belt-and-suspenders).** This is the **Cursor** build of the superagent plugin
(generated — see the banner above). If you are running under Claude Code — e.g. the
`CLAUDE_PLUGIN_ROOT` environment variable is defined in your tool environment — STOP and report: the wrong harness
build is loaded; install the Claude Code plugin from the repository root instead. Also make sure
only one build of this plugin is loaded at a time (if Cursor's "Include third-party Plugins,
Skills, and other configs" setting is loading the Claude Code build alongside this one, disable
that for this plugin — the two inits collide).
cursor-only:end -->
<!-- codex-only:start
**Harness check (belt-and-suspenders).** This is the **Codex** build of the superagent plugin
(generated — see the banner above). If you are running under Claude Code — e.g. the
`CLAUDE_PLUGIN_ROOT` environment variable is defined in your tool environment — STOP and report:
the wrong harness build is loaded; install the Claude Code plugin from the repository root
instead. Confirm this host can actually drive the loop: the `codex` CLI is on PATH
(`codex --version` succeeds) — else WARN with an install hint (`npm install -g @openai/codex`,
or `brew install codex`). Also make sure only one build of this plugin is loaded at a time —
two builds' inits collide.
codex-only:end -->

## Repo configuration (.superenv)

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${CLAUDE_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.superenv" "${CLAUDE_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
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
<!-- pi-only:start
   On Pi, superpowers is a Pi package: `pi list` must show `superpowers` (install:
   `pi install git:github.com/obra/superpowers`). Then check the `pi-subagents` package per
   `SUPER_PI_SUBAGENTS` (validated below): read its installed version from
   `~/.pi/agent/npm/node_modules/pi-subagents/package.json` or `.pi/npm/node_modules/pi-subagents/package.json`
   (whichever exists); missing or `< 0.58.0` → `recommended`: WARN "pi-subagents missing/old —
   superrun's SDD children will run sequentially in-context without role pins; install:
   `pi install npm:pi-subagents`"; `required`: ABORT with the same hint; `off`: skip the check.
   Record the version (or `absent`) in the summary — Step 3 keys off it.
pi-only:end -->
3. `gh auth status` succeeds — else WARN (PR-based flows need it; planning artifacts are
   drafted either way, but `superauthor`'s A7 commit-and-merge step and every CI/PR
   operation in `superplan`/`superrun` need it). On a macOS host, a sandboxed `gh auth
   status` can fail even when `gh` is actually authenticated, because `gh` needs keychain
   access the tool sandbox blocks — see `SUPER_GH_DISABLE_SANDBOX` in
   `${CLAUDE_PLUGIN_ROOT}/templates/superenv.default`. If the check fails on macOS, note
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
<!-- pi-only:start
   On the Pi harness, also run `pi auth check --provider <p>` for each distinct provider a `pi:`
   role names (WARN on failure).
pi-only:end -->
   Also run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/role-bridge.sh" 2>&1 | head -1` — a usage line
   proves the bridge shipped with this build; a "not found" is a broken install: ABORT.

## Step 2 — Config

If `<repo-root>/.superenv` does not exist, copy
`${CLAUDE_PLUGIN_ROOT}/templates/superenv.default` to `<repo-root>/.superenv` (keep the
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
   also exist in `${CLAUDE_PLUGIN_ROOT}/templates/superenv.default`. Unknown → WARN
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
<!-- pi-only:start
   On Pi `SUPER_PANEL_AGENT_TYPE` is ignored (the panel is a bridge fan-out, not typed subagents) —
   WARN once if it is set to anything.
pi-only:end -->
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
<!-- cc-only:start -->
   anything else → WARN "unrecognized model value" and fall back to arm (a) (`inherit`).
<!-- cc-only:end -->
<!-- cursor-only:start
   anything else → `cursor`, i.e. **native**: Cursor model names are free-form (cf.
   `agent --list-models`), so a bare value matching no prefix and no pattern above is taken as a
   Cursor model name — checked below against the model list rather than rejected here. Arm (c)
   still runs first, so a Codex-looking name such as `gpt-5` infers `codex` and is therefore
   **bridged**; write `cursor:gpt-5` to run that same name natively on Cursor.
cursor-only:end -->
<!-- codex-only:start
   anything else → WARN "unrecognized model value" and fall back to arm (a) (`inherit`).
codex-only:end -->
   Strip the prefix to get the **model**. The role is **native** when its harness equals
   `SUPER_HARNESS`, else **bridged** — so an arm-(a) `inherit` role is always native, item 6
   validates its effort in `SUPER_HARNESS`'s domain, and its summary row shows harness =
   `SUPER_HARNESS`. `SUPER_MODEL_SUPERVISOR` must be native: a foreign harness there is a **hard
   error** (stop and report; the tick refuses it too) — `SUPER_MODEL_SUPERVISOR=inherit` satisfies
   this trivially.
   Native model values are further validated per build:
<!-- cc-only:start -->
   a tier name (`sonnet|opus|haiku|fable`), `inherit`, or a full Claude model ID (`^claude-`);
   anything else → WARN, treat as `inherit` (catches typos like `sonet` before they become an
   agent definition that fails at spawn time).
<!-- cc-only:end -->
<!-- cursor-only:start
   a Cursor model name (`agent --list-models`) or `inherit`; a name not in that list → WARN, treat
   as `inherit` (catches typos before they become an agent definition that fails at spawn time).
cursor-only:end -->
<!-- codex-only:start
   a Codex model name or `inherit`; anything else → WARN, treat as `inherit` (catches typos before
   they become a spawn-time failure).
codex-only:end -->
<!-- pi-only:start
   a Pi model string — exactly one `/` (`<provider>/<model>`, an optional `:<level>` suffix allowed)
   — or `inherit`; anything else → WARN, treat as `inherit`. A bare Claude tier / `claude-*` /
   `gpt-*` value infers its own harness under arm (c) and is therefore **bridged** (its CLI must be
   present per Step 1 item 5), never a Pi model.
pi-only:end -->
   Bridged model values are not validated beyond the grammar (the foreign CLI owns its names), except
   `pi`, whose model must contain exactly one `/` (`<provider>/<model>`).
   `SUPER_BRIDGE_RELAY_MODEL` is validated as a native model value (invalid → WARN, treat as
   `inherit`).
6. **Effort keys** (each `SUPER_EFFORT_<ROLE>`): valid in the domain of the ROLE's harness (from
   item 5; the supervisor's harness is `SUPER_HARNESS`): claude `low|medium|high|xhigh|max`;
   codex `none|minimal|low|medium|high|xhigh` (no `max`); pi `off|minimal|low|medium|high|xhigh|max`;
   cursor: `inherit` only. `inherit` is always valid. Out of domain → WARN, treat as `inherit`.

## Step 3 — Role agents (model/effort pins)

<!-- cc-only:start -->
Nine `SUPER_MODEL_*` role keys dispatch through the Agent tool — all but
`SUPER_MODEL_SUPERVISOR`, which the tick passes straight to `claude --model`. The
Agent tool's `model:` parameter accepts only tier names, so a role whose resolved
value is a **full model ID** (matches `^claude-`, e.g. `claude-fable-5`) is pinned
via a generated per-role agent definition instead — the definition's `model:`
frontmatter accepts full IDs.
<!-- cc-only:end -->
<!-- cursor-only:start
Nine `SUPER_MODEL_*` role keys dispatch through subagents — all but
`SUPER_MODEL_SUPERVISOR`, which the external tick passes straight to `agent --model`.
On Cursor, a **native** model value is a Cursor model name (see `agent --list-models`)
or `inherit`; any native value other than `inherit` is pinned via a generated per-role
agent definition — the definition's `model:` frontmatter carries the name. Claude Code
tier names (`sonnet` | `opus` | `haiku` | `fable`) and Claude model IDs (`claude-*`)
are NOT discarded: under item 5's grammar they resolve to harness `claude`, which is
foreign to this build, so such a role is **bridged** and gets a relay definition
instead of being treated as a typo.
cursor-only:end -->
<!-- codex-only:start
Nine `SUPER_MODEL_*` role keys dispatch through subagents — all but
`SUPER_MODEL_SUPERVISOR`, which the external tick passes straight to `codex exec -m`.
On Codex there are **no generated agent-definition files at all**: role pins dispatch
at runtime as `spawn_agent` parameters — `SUPER_MODEL_<ROLE>` → `model`,
`SUPER_EFFORT_<ROLE>` → `reasoning_effort`, `inherit` = omit the parameter. This step
therefore **generates nothing**; per the design spec it resolves the effective
model/effort per role and REPORTS them, so a misconfigured pin surfaces here instead
of at spawn time.
codex-only:end -->
<!-- pi-only:start
Nine `SUPER_MODEL_*` role keys dispatch through subagents — all but `SUPER_MODEL_SUPERVISOR`,
which the external tick passes straight to `pi --model`. On Pi the supervisor's OWN dispatches
(planner, executor, panel) are bridge processes that take the pins as CLI flags and need no
definition; only superrun's SDD roles (implementer, fix-applier, task-reviewer, re-reviewer,
branch-reviewer, fix-planner) dispatch through the `pi-subagents` `subagent` tool, and THOSE ride
generated `.pi/agents/super-<role>.md` definitions. Generation happens only when Step 1 found
`pi-subagents` ≥ 0.58.0 and `SUPER_PI_SUBAGENTS` ≠ `off`; otherwise this step generates nothing
and reports `dispatch=sequential (no pi-subagents)` for the six SDD roles.
pi-only:end -->

Resolve each role's model key (`SUPER_MODEL_<ROLE>`) and effort key (`SUPER_EFFORT_<ROLE>`), using the validated values from the validation step above:

| Model key | Effort key | Generated definition |
|---|---|---|
| SUPER_MODEL_PLANNER | SUPER_EFFORT_PLANNER | `.claude/agents/super-planner.md` |
| SUPER_MODEL_EXECUTOR | SUPER_EFFORT_EXECUTOR | `.claude/agents/super-executor.md` |
| SUPER_MODEL_PANEL | SUPER_EFFORT_PANEL | `.claude/agents/super-panel.md` |
| SUPER_MODEL_IMPLEMENTER | SUPER_EFFORT_IMPLEMENTER | `.claude/agents/super-implementer.md` |
| SUPER_MODEL_FIX_APPLIER | SUPER_EFFORT_FIX_APPLIER | `.claude/agents/super-fix-applier.md` |
| SUPER_MODEL_TASK_REVIEWER | SUPER_EFFORT_TASK_REVIEWER | `.claude/agents/super-task-reviewer.md` |
| SUPER_MODEL_RE_REVIEWER | SUPER_EFFORT_RE_REVIEWER | `.claude/agents/super-re-reviewer.md` |
| SUPER_MODEL_BRANCH_REVIEWER | SUPER_EFFORT_BRANCH_REVIEWER | `.claude/agents/super-branch-reviewer.md` |
| SUPER_MODEL_FIX_PLANNER | SUPER_EFFORT_FIX_PLANNER | `.claude/agents/super-fix-planner.md` |

<!-- pi-only:start
On Pi the listed path is `.pi/agents/super-<role>.md` for the six SDD roles; planner/executor/panel
never get a file.
pi-only:end -->

(`super-executor.md` is generated for completeness, but the `superagent` loop does not dispatch
`superrun` through it: the executor always runs as the top-level agent of its own CLI process via
`role-bridge.sh --tools executor`, taking `SUPER_MODEL_EXECUTOR` / `SUPER_EFFORT_EXECUTOR` directly —
see superagent **Subagent dispatch**, issue #25.)

<!-- cc-only:start -->
- **Bridged role (its harness ≠ `SUPER_HARNESS`):** render
  `${CLAUDE_PLUGIN_ROOT}/templates/super-role-bridge-agent.md` to the listed path, substituting
  `<role>`, `<KEY>` (both keys), `<harness>`, `<model>` (prefix stripped), `<effort>` (`inherit`
  when unset/invalid), `<relay-model>` = `SUPER_BRIDGE_RELAY_MODEL` (drop the `model:` line when
  `inherit`), and `<bridge-path>` = the absolute path of
  `${CLAUDE_PLUGIN_ROOT}/scripts/role-bridge.sh`. The `generated-by: superagent:init`
  marker/ownership rules stated in the native bullets below apply to this file too (never
  overwrite an unmarked file at that path — report `conflict` and leave it), but the native
  bullets' case selection does not apply to a bridged role. A bridged panel role ignores
  `SUPER_PANEL_AGENT_TYPE` (WARN once).

**Native role (harness == `SUPER_HARNESS`):** the following bullets apply only to native roles —

- **Generate when:** the model value is a **full model ID** (`^claude-`), OR the
  effort value is non-`inherit` (a tier-name model alone rides the Task call's
  `model:` parameter and needs no file). Render
  `${CLAUDE_PLUGIN_ROOT}/templates/super-role-agent.md` to the listed path (create
  `.claude/agents/` if needed), substituting `<role>` (the path's `super-` suffix,
  e.g. `planner`), `<KEY>` (both keys, comma-separated, when both pin), and:
  - the `model:` line — keep it only when the model value is non-`inherit`
    (tier names AND full IDs are both valid frontmatter `model:` values; an
    effort-only definition drops the line entirely);
  - the `effort:` line — keep it only when the effort value is non-`inherit`
    (claude domain: `low|medium|high|xhigh|max`; native roles only — a bridged role's
    effort was validated in the role's own harness domain in item 6 and is carried by
    the bridge definition instead).
  These files are **derived artifacts owned by init** — the
  `generated-by: superagent:init` marker line says so — and rewriting one whose
  pins drifted from `.superenv` is the point of this step, not an overwrite
  violation. Never touch a file at these paths that lacks the marker: report it
  as `conflict` and leave it.
- **Neither key requires a file, but the listed path exists with the marker:**
  delete it (a stale derived artifact) and report `removed (stale)`.
- **Neither key requires a file, no file present:** nothing to do.
<!-- cc-only:end -->
<!-- cursor-only:start
- **Bridged role (its harness ≠ `SUPER_HARNESS`):** render
  `${CLAUDE_PLUGIN_ROOT}/templates/super-role-bridge-agent.md` to the listed path, substituting
  `<role>`, `<KEY>` (both keys), `<harness>`, `<model>` (prefix stripped), `<effort>` (`inherit`
  when unset/invalid), `<relay-model>` = `SUPER_BRIDGE_RELAY_MODEL` (drop the `model:` line when
  `inherit`), and `<bridge-path>` = the absolute path of
  `${CLAUDE_PLUGIN_ROOT}/scripts/role-bridge.sh`. The `generated-by: superagent:init`
  marker/ownership rules stated in the native bullets below apply to this file too (never
  overwrite an unmarked file at that path — report `conflict` and leave it), but the native
  bullets' case selection does not apply to a bridged role. A bridged panel role ignores
  `SUPER_PANEL_AGENT_TYPE` (WARN once).
- **Native role whose value is a model name (anything valid other than `inherit`):** render
  `${CLAUDE_PLUGIN_ROOT}/templates/super-role-agent.md` to the listed path (create
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
cursor-only:end -->
<!-- codex-only:start
- **No files are generated or removed on Codex.** The table's "Generated definition"
  column names the Claude Code artifact and is inapplicable in this build. For each
  role, resolve both keys (using the validated values above) and record the effective
  pair in the summary using the row shape mandated below — e.g.
  `planner · codex · gpt-5.6-sol · inherit · native`. At runtime the loop passes these
  as the `spawn_agent` call's `model` / `reasoning_effort` parameters; `inherit` = omit
  the parameter. For a
  **bridged** role, the loop instead spawns a relay: `model` = `SUPER_BRIDGE_RELAY_MODEL`
  (omit when `inherit`) and a message built from
  `${SUPER_PLUGIN_ROOT}/templates/relay-preamble.md` (substituting `<role>`, `<harness>`,
  `<model>`, `<effort>`, `<bridge-path>` =
  `${SUPER_PLUGIN_ROOT}/scripts/role-bridge.sh`) followed by the task prompt. Record
  `dispatch=bridge(<harness>)` in the summary.
- A leftover `.claude/agents/super-*.md` file from a Claude Code init of the same
  repo belongs to that harness's build: leave it untouched and do not report it as
  stale.
codex-only:end -->
<!-- pi-only:start
- **SDD role, native (`pi:` or inherit) — generate when** the model is non-`inherit` OR the effort is
  non-`inherit`: render `${CLAUDE_PLUGIN_ROOT}/templates/super-role-pi-agent.md` to
  `.pi/agents/super-<role>.md` (create `.pi/agents/` if needed), substituting `<role>`, `<KEY>`,
  `<model>` (prefix stripped; drop the `model:` line when `inherit`) and `<effort>` (drop the
  `thinking:` line when `inherit`). A role with both keys `inherit` needs no file.
- **SDD role, bridged (harness ≠ pi):** render
  `${CLAUDE_PLUGIN_ROOT}/templates/super-role-pi-bridge-agent.md` to the same path, substituting
  `<role>`, `<KEY>`, `<harness>`, `<model>` (prefix stripped), `<effort>` (`inherit` when
  unset/invalid), `<relay-model>` = `SUPER_BRIDGE_RELAY_MODEL` (drop the `model:` line when
  `inherit`) and `<bridge-path>` = the absolute path of `${CLAUDE_PLUGIN_ROOT}/scripts/role-bridge.sh`.
- **Planner / executor / panel:** never a file; record `dispatch=bridge(<harness>)` (native roles
  show `bridge(pi)`).
- Ownership rules are the Claude build's: files carry the `generated-by: superagent:init` marker;
  rewrite marked files whose pins drifted; never touch an unmarked file (report `conflict`);
  delete a marked file no key requires (`removed (stale)`). When `pi-subagents` is absent/`off`,
  existing marked files are left in place and reported `unused (no pi-subagents)`.
- A leftover `.claude/agents/super-*.md` from a Claude Code init of the same repo belongs to that
  harness's build: leave it untouched and do not report it as stale.
pi-only:end -->

<!-- cc-only:start -->
Agent definitions load at session start, so files written here take effect from the
next tick/session, not the current one.
<!-- cc-only:end -->
<!-- cursor-only:start
Agent definitions load at session start, so files written here take effect from the
next tick/session, not the current one.
cursor-only:end -->
<!-- pi-only:start
Agent definitions are read by pi-subagents at child launch, so files written here take effect from
the next superrun dispatch.
pi-only:end -->
Report one summary row per role: `role · harness · model · effort · dispatch` where dispatch is
`native`, `native (definition: generated|regenerated|unchanged|removed (stale)|conflict)`,
`bridge(<harness>)`, or `bridge(<harness>, definition: conflict)` — a bridged role whose
relay definition could not be written (hand-edited file kept, or the write was denied).

<!-- cc-only:start -->
Note: permission layers commonly treat `.claude/` as protected — in a headless or
auto-accept session the write may be auto-denied even when other edits sail through.
init is an attended bootstrap step; if the write prompts, it needs a human approval,
and if it is denied, report the role as blocked rather than retrying.
<!-- cc-only:end -->
<!-- cursor-only:start
Note: permission layers commonly treat `.claude/` as protected — in a headless or
auto-accept session the write may be auto-denied even when other edits sail through.
init is an attended bootstrap step; if the write prompts, it needs a human approval,
and if it is denied, report the role as blocked rather than retrying.
cursor-only:end -->

## Step 4 — Vault

Resolve `SUPER_GOAL_ROOT` per the resolution order above (shipped default `vault`; a
worked example from the originating repo sets it to `vault/network-compose`). Three cases:

- `<repo-root>/<SUPER_GOAL_ROOT>` does not exist: create it and copy
  `${CLAUDE_PLUGIN_ROOT}/templates/vault-root.md` to `<SUPER_GOAL_ROOT>/root.md`.
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
directs `ANTHROPIC_API_KEY`/`GH_TOKEN` into `<repo>/.env` (see `scripts/README.md`'s
Prerequisites), and that file must never be committed.

## Step 6 — Landing

init only prepares files — it never commits. Tell the user what to commit
(`.superenv`, the vault seed, any generated `.claude/agents/super-*.md` role
definitions, `.gitignore` — now covering both the loop-status pattern
and `.env`) and remind them to follow the repo's own change discipline: if
`SUPER_PROTECTED_MAIN=true` (the shipped default), that means a feature branch + PR, same
as every `superauthor`-driven skill's own A7 commit step. `.env` itself (holding
`ANTHROPIC_API_KEY`/`GH_TOKEN`) stays gitignored and is never committed — only the
`.gitignore` entry that excludes it is.
