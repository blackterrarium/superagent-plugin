---
name: init
description: Bootstrap a repository for the superagent plugin — verify prerequisites, create the .superenv config, create and seed the goal vault if absent (an external vault becomes its own git repo), and add the loop-status gitignore entry. `--local-only` routes every ignore entry to .git/info/exclude so a dogfooded checkout with an external vault has nothing to commit. Idempotent; safe to re-run. Run this once per repo before supergoal/superagent.
argument-hint: "[--local-only]"
license: MIT
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
>   `${SUPER_PLUGIN_ROOT}/scripts/` as that repository's `scripts/` directory for nonpackaged
>   helpers, including assignments to `SUPERAGENT_SCRIPTS`. The coding-loop helpers
>   (`prd-lint.sh`, `supereval.sh`, `_evalspec.sh`, `_common.sh`) and `role-bridge.sh` ARE
>   packaged at `${SUPER_PLUGIN_ROOT}/scripts/`; use their installed paths.
> - Skill lookup: this plugin installs via the Codex plugin marketplace; skills resolve by name
>   (e.g. `superplan`). The `superagent` supervisor skill is driven by reading its SKILL.md
>   directly (the external tick's file-read prompt), never invoked by name.

# superagent:init — repo bootstrap

Prepare the current repository to run the superagent skill family. Every step is
idempotent: report what was **done** vs **already present**; never overwrite existing
files. Finish with a summary table of step → done/skipped.

## Arguments

- **`--local-only`** — optional. Every line Step 5 would append to `<repo-root>/.gitignore` is
  appended to `<git-common-dir>/info/exclude` instead (`git rev-parse --path-format=absolute
  --git-common-dir` — so linked worktrees share it), plus two more lines: `.superenv` and
  `.claude/agents/super-*.md`. `.gitignore` is not touched. The flag routes **ignore entries
  only**: with an **external** vault that leaves the checkout with nothing to commit (Step 6),
  but with an **internal** vault the vault seed and every later plan-tree commit still land in
  the code repo, so Step 6 warns that the combination is probably unintended. Use it when the
  repository's history must not carry superagent's bootstrap files — dogfooding the plugin on
  its own checkout, or any repo whose maintainers did not opt in. Re-running later without the
  flag never removes the exclude lines (init never deletes).

Invoke this skill explicitly as `superagent:init` — a built-in `init` skill (CLAUDE.md
authoring) ships unscoped in most sessions, so the bare name `init` is ambiguous the
moment both are available.

**Harness check (belt-and-suspenders).** This is the **Codex** build of the superagent plugin
(generated — see the banner above). If you are running under Claude Code — e.g. the
`CLAUDE_PLUGIN_ROOT` environment variable is defined in your tool environment — STOP and report:
the wrong harness build is loaded; install the Claude Code plugin from the repository root
instead. Confirm this host can actually drive the loop: the `codex` CLI is on PATH
(`codex --version` succeeds) — else WARN with an install hint (`npm install -g @openai/codex`,
or `brew install codex`). Also make sure only one build of this plugin is loaded at a time —
two builds' inits collide.

## Repo configuration (.superenv)

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${SUPER_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.superenv" "${SUPER_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
(checking the env var first, and anchoring at the primary checkout so worktrees resolve the same config). A repo with no `.superenv` runs on the shipped defaults —
which is exactly the case Step 2 below fixes by creating one.

## Project-only prerequisite

Stage 3 is under acceptance at 0.8.1. Before launching a coding-loop **project**, verify
`python3 -c 'import sys; assert sys.version_info >= (3, 9)'`. Missing/older Python blocks project
launch; it does not block legacy goal initialization, launch or controls. `SUPER_CODE_MAX_ITERATIONS`
must be a positive integer and limits created project rounds, not ticks/retries. The supervisor must
be native to `SUPER_HARNESS`; bridged worker roles remain supported. Outer/inner registrations stop
independently. Adoption of changed agreement and AUTHOR INPUT resume require the author's explicit
answer; init or a configuration edit does not provide that authorization.

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

### .superenv validation (lint — WARN + fallback, except hard errors)

Validate the RESOLVED configuration (env > repo `.superenv` > plugin default) before
using it. For each finding emit one WARN row in the summary; the effective value used
by later steps is the fallback shown. Never rewrite the user's `.superenv` — this is
report-only. Hard errors stop init: a foreign harness on `SUPER_MODEL_SUPERVISOR` (item 5),
a `SUPER_GOAL_ROOT` that resolves to `$HOME` or `/` (item 7), or on Pi a
`SUPER_PI_SUBAGENTS` value other than `required` or its deprecated `recommended` alias (item 2).

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
   `SUPER_REVIEW_CONFIDENCE_FILTER` ∈ controller; `SUPER_PI_SUBAGENTS` ∈ required.
   On Pi, normalize legacy `recommended` to `required` for this run and report
   "SUPER_PI_SUBAGENTS=recommended is deprecated; enforcing required" without editing the
   user's environment or .superenv. `off` (or any other value) is a migration error:
   ABORT with "set SUPER_PI_SUBAGENTS=required in the overriding environment or .superenv;
   pi-subagents >= 0.58.0 is mandatory". No value permits a sequential fallback.
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
   anything else → WARN "unrecognized model value" and fall back to arm (a) (`inherit`).
   Strip the prefix to get the **model**. The role is **native** when its harness equals
   `SUPER_HARNESS`, else **bridged** — so an arm-(a) `inherit` role is always native, item 6
   validates its effort in `SUPER_HARNESS`'s domain, and its summary row shows harness =
   `SUPER_HARNESS`. `SUPER_MODEL_SUPERVISOR` must be native: a foreign harness there is a **hard
   error** (stop and report; the tick refuses it too) — `SUPER_MODEL_SUPERVISOR=inherit` satisfies
   this trivially.
   Native model values are further validated per build:
   a Codex model name or `inherit`; anything else → WARN, treat as `inherit` (catches typos before
   they become a spawn-time failure).
   Bridged model values are not validated beyond the grammar (the foreign CLI owns its names), except
   `pi`, whose model must contain exactly one `/` (`<provider>/<model>`).
   `SUPER_BRIDGE_RELAY_MODEL` is validated as a native model value (invalid → WARN, treat as
   `inherit`).
6. **Effort keys** (each `SUPER_EFFORT_<ROLE>`): valid in the domain of the ROLE's harness (from
   item 5; the supervisor's harness is `SUPER_HARNESS`): claude `low|medium|high|xhigh|max`;
   codex `none|minimal|low|medium|high|xhigh` (no `max`); pi `off|minimal|low|medium|high|xhigh|max`;
   cursor: `inherit` only. `inherit` is always valid. Out of domain → WARN, treat as `inherit`.
7. **Paths:** `SUPER_GOAL_ROOT` must be non-empty and without a `..` segment (→ WARN, fall back
   to the template default `vault`). A trailing `/` is a WARN that **strips the slash and keeps
   the value** — the same normalisation `vault_root` performs — never a fall-back to `vault`. An
   absolute or `~`-prefixed value selects **external vault mode** (see Step 4); if that value
   resolves to a directory *inside* `<repo-root>`, WARN "external form for an in-repo path —
   treated as internal" and use it as the equivalent repo-relative path. If `<vault_root>`
   resolves physically (`cd "<vault_root>" && pwd -P`) to `$HOME` or to `/`, **ABORT** init with
   "SUPER_GOAL_ROOT resolves to your home directory / the filesystem root; choose a subdirectory
   such as `~/superagent-vaults/<repo>`" — Step 4 would otherwise `git init` the whole home
   directory or filesystem root and scatter goal folders through it. A `<vault_root>` that does not
   exist yet cannot be `$HOME` or `/`, so this check cannot fire on a fresh external vault; Step 4
   creates it. `SUPER_PROJECT_DIRNAME` and
   `SUPER_LOOP_STATUS_DIRNAME` must be a single path segment (no `/`) — else WARN + default.

## Step 3 — Role agents (model/effort pins)

Thirteen `SUPER_MODEL_*` role keys dispatch through subagents — all but
`SUPER_MODEL_SUPERVISOR`, which the external tick passes straight to `codex exec -m`.
On Codex there are **no generated agent-definition files at all**: role pins dispatch
at runtime as `spawn_agent` parameters — `SUPER_MODEL_<ROLE>` → `model`,
`SUPER_EFFORT_<ROLE>` → `reasoning_effort`, `inherit` = omit the parameter. This step
therefore **generates nothing**; per the design spec it resolves the effective
model/effort per role and REPORTS them, so a misconfigured pin surfaces here instead
of at spawn time.

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
| SUPER_MODEL_PRD_REVIEWER | SUPER_EFFORT_PRD_REVIEWER | `.claude/agents/super-prd-reviewer.md` |
| SUPER_MODEL_META_PLANNER | SUPER_EFFORT_META_PLANNER | `.claude/agents/super-meta-planner.md` |
| SUPER_MODEL_EVALUATOR | SUPER_EFFORT_EVALUATOR | `.claude/agents/super-evaluator.md` |
| SUPER_MODEL_DIAGNOSER | SUPER_EFFORT_DIAGNOSER | `.claude/agents/super-diagnoser.md` |

The last four rows are the **coding-loop roles** (0.7.0): `super-prd-reviewer` is dispatched by
`superprd`, `super-meta-planner` backs `supermeta`, and `super-evaluator` grades the judged
objectives `supereval` dispatches (all Stage 2); `super-diagnoser` follows with `superdiagnose`
when that skill lands.
They follow the harness-specific generate/skip/conflict rules below.


(`super-executor.md` is generated for completeness, but the `superagent` loop does not dispatch
`superrun` through it: the executor always runs as the top-level agent of its own CLI process via
`role-bridge.sh --tools executor`, taking `SUPER_MODEL_EXECUTOR` / `SUPER_EFFORT_EXECUTOR` directly —
see superagent **Subagent dispatch**, issue #25.)

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

Report one summary row per role: `role · harness · model · effort · dispatch` where dispatch is
`native`, `native (definition: generated|regenerated|unchanged|removed (stale)|conflict)`,
`bridge(<harness>)`, or `bridge(<harness>, definition: conflict)` — a bridged role whose
relay definition could not be written (hand-edited file kept, or the write was denied).


## Step 4 — Vault

**Resolve `<vault_root>`.** Read `SUPER_GOAL_ROOT` per the resolution order above (shipped
default `vault`; a worked example from the originating repo sets it to `vault/network-compose`).
If it starts with `/` or `~`, the vault is **external**: `<vault_root>` is that path with `~`
expanded to `$HOME`, and the vault is its own git repository outside the checkout. Otherwise
`<vault_root>` is `<repo-root>/<SUPER_GOAL_ROOT>` (**internal**, today's default). Strip one
trailing `/` if present. This is the same rule `vault_root` in `scripts/_common.sh` implements;
never join `SUPER_GOAL_ROOT` onto `<repo-root>` when it is absolute.

**Seed the goal root** at `<vault_root>` — three cases:

- `<vault_root>` does not exist: create it (`mkdir -p`) and copy
  `${SUPER_PLUGIN_ROOT}/templates/vault-root.md` to `<vault_root>/root.md`.
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

**External vault only — make it a git repository.** Vault docs in external mode are committed
into the vault itself (superauthor A7's external target), so it must be a repo:

1. **"Already a git repo" test.** `git -C "<vault_root>" rev-parse --show-toplevel` succeeds AND
   its output, resolved physically (`cd "<that output>" && pwd -P`), equals `<vault_root>`
   resolved the same way (`cd "<vault_root>" && pwd -P`) → `Vault repo: already a git repo`. Any
   other outcome — not inside a work tree at all, or the top level is a different directory (the
   vault sits inside another repo's tree) — run `git -C "<vault_root>" init -q` (summary row
   `Vault repo: initialised`), which makes `<vault_root>` its own nested repository (legitimate
   git usage; git treats a nested `.git` as a boundary). A vault deliberately placed inside
   another repository's tree therefore still gets its own nested repo; an operator who wants
   otherwise removes `<vault_root>/.git` after init and accepts that A7's vault commits then land
   in the enclosing repo. Never `git init` inside the code checkout — if `<vault_root>` resolves
   inside `<repo-root>` the lint (item 7) already downgraded it to internal mode.
2. Ensure `<vault_root>/.gitignore` contains the line `**/<SUPER_LOOP_STATUS_DIRNAME>/` (same
   newline guard and idempotent append as Step 5). This also covers the `.<loop>.lockd/` and
   `.<loop>.ci-stale` markers, which sit inside that directory.
3. If the vault repo has no commits yet (`git -C "<vault_root>" rev-parse --verify HEAD` fails):
   `git -C "<vault_root>" add root.md .gitignore && git -C "<vault_root>" commit -q -m
   "chore(vault): seed goal root"`. This is a **deliberate, narrow exception** to "init never
   commits": it is the plugin-owned vault repo, never the user's code repo, and only its very
   first commit — a later re-run finds `HEAD` and does nothing. Add a summary row
   `Vault seed commit: created <short-sha>` / `already committed`.

A vault repo with a remote is the operator's choice (`git -C "<vault_root>" remote add origin …`);
A7 pushes only when one exists. init never adds one.

## Step 5 — Gitignore

**Target file.** Without `--local-only` the target is `<repo-root>/.gitignore`. With
`--local-only` it is `<git-common-dir>/info/exclude` (create `info/` if absent) and
`.gitignore` is never touched. Every append below uses the same two rules, in this order:

1. **newline guard** — if the target exists, is non-empty, and its last byte is not `\n`, run
   `printf '\n' >> <target>` first, so an append never fuses onto the file's last line;
2. **idempotent append** — `grep -qxF -- '<line>' <target> || printf '%s\n' '<line>' >> <target>`.

(`scripts/vault-external-test.sh` section 3 pins exactly these two rules as `append_ignore`.)

**Lines to append.** Resolve `SUPER_LOOP_STATUS_DIRNAME` per the resolution order above
(shipped default `loop-status`).

- `<SUPER_GOAL_ROOT>/**/<SUPER_LOOP_STATUS_DIRNAME>/` — **internal vault mode only**. This is
  the exact pattern `superloop`'s L1 clause documents as gitignored local-only state (worked
  example from the originating repo: `vault/**/loop-status/`) — every loop-status file
  `superagent`/`superagent-external` write must never be tracked or swept into a docs-only PR
  commit. In **external vault mode** this line is **not** written here: the pattern lives in
  the vault repo's own `.gitignore` (Step 4).
- `.env` — always. External (unattended) mode directs `OPENAI_API_KEY`/`GH_TOKEN` into
  `<repo>/.env` (see `scripts/README.md`'s Prerequisites), and that file must never be
  committed.
- `.superenv` and `.claude/agents/super-*.md` — **`--local-only` only**. These are the two
  bootstrap artifacts that cannot leave the checkout (every skill resolves `.superenv` at the
  primary root; Step 3's role definitions are read by the harness from `.claude/agents/`), so
  under `--local-only` they are excluded locally instead of being committed.

Report the target file and each line as `added` / `already present` in the summary table
(`Ignore target: .gitignore` or `Ignore target: .git/info/exclude`).

## Step 6 — Landing

init only prepares files — it never commits to the user's repository (the one exception is the
external vault repo's own first commit in Step 4, which is plugin-owned). What to tell the user
depends on the mode:

- **Internal vault, no `--local-only`:** list what to commit — `.superenv`, the vault seed
  (`<SUPER_GOAL_ROOT>/root.md`), any generated `.claude/agents/super-*.md` role definitions,
  `.gitignore` (now covering the loop-status pattern and `.env`) — and remind them to follow
  the repo's own change discipline: if `SUPER_PROTECTED_MAIN=true` (the shipped default), that
  means a feature branch + PR, same as every `superauthor`-driven skill's own A7 commit step.
- **External vault, no `--local-only`:** the same list **without** the vault seed (it is
  committed in the vault repo already) and with `.gitignore` covering only `.env`.
- **External vault with `--local-only`:** state that **nothing needs committing**; list the paths
  now excluded via `.git/info/exclude` (`.env`, `.superenv`, `.claude/agents/super-*.md`), and
  note that the loop-status pattern lives in the vault repo's own `.gitignore` (Step 4).
- **Internal vault with `--local-only`:** the flag routes **ignore entries only**, so this is
  **not** a checkout with nothing to commit: the vault seed (`<SUPER_GOAL_ROOT>/root.md`) and
  every later plan-tree commit from `supergoal`/`superplan`/`superfinish` still land in the code
  repo. List the paths now excluded via `.git/info/exclude` (`.env`, `.superenv`,
  `.claude/agents/super-*.md`, the loop-status pattern), say the vault seed still needs
  committing, and **WARN** that `--local-only` with an internal vault is probably unintended —
  it hides the bootstrap files while the goal vault itself stays in the repo's history. An
  external vault (`SUPER_GOAL_ROOT` absolute or `~`-prefixed) is what makes the checkout
  genuinely commit-free.

`.env` itself (holding `OPENAI_API_KEY`/`GH_TOKEN`) is never committed in any mode — only
the ignore entry that excludes it is.
