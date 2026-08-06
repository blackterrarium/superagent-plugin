# superagent

A Claude Code plugin for **plan-tree authoring and autonomy-loop execution**. It ships two things: a
family of `super*` skills that turn a goal description into a self-contained, self-reviewed vault of
plans and closeout reports, and a driver (in-session or an unattended external scheduler) that walks
that tree to completion without a human babysitting every step.

## What this is

The core cycle is **supergoal → superplan → superrun → superfinish**: `supergoal` turns a goal
description into a goal folder and a root master plan with a progress-report table; `superplan`
descends that table, writes the next step's plan (a deeper sub-master or a leaf implementation plan),
and marks the row `PLAN WRITTEN — ready to execute`; `superrun` finds the next ready leaf, executes it
via `superpowers:subagent-driven-development`, and integrates the code PR; `superfinish` records
findings, writes a closeout report, and flips the tree's rows complete on the way back up. All four are
docs/PR-authoring skills except `superrun`, which is the one that actually changes source code — and
only by delegating to `subagent-driven-development`. Sitting above all four, the **`superagent`
supervisor** drives a goal's root plan through repeated ticks of this cycle — one `superplan` or
`superrun` dispatch per tick, unattended, until every step in the tree is both planned and executed —
either as an in-session `cron` job or as an external, unattended loop driven by a systemd user timer (or
cron) firing fresh headless sessions.

## Install

```
/plugin marketplace add blackterrarium/superagent-plugin
/plugin install superagent
```

Then, in **each** target repo, bootstrap it once:

```
superagent:init
```

Invoke it by its full namespaced name, `superagent:init` — a bare `init` collides with a built-in
Claude Code skill (CLAUDE.md authoring) that ships unscoped in most sessions, so the two are ambiguous
the moment both are available. `superagent:init` verifies prerequisites, creates a `.superenv` config
(copied from this plugin's shipped defaults if the repo has none), seeds the goal vault
(`root.md` at `<SUPER_GOAL_ROOT>`, default `vault`) if it doesn't already exist, and adds the loop-status
gitignore entry. It is idempotent — safe to re-run — and never overwrites an existing file; it only
prepares files, it never commits, so review and commit `.superenv` / the vault seed / `.gitignore`
yourself (through a PR, if the repo protects its default branch).

## Prerequisites

- **The `superpowers` plugin, for execution.** Planning skills (`supergoal`, `superplan`) work without
  it, but `superrun` requires `superpowers:subagent-driven-development` to execute a plan and refuses
  outright if it isn't resolvable:
  `/plugin marketplace add obra/superpowers-marketplace` then `/plugin install superpowers`.
- **`gh`, authenticated, for PR flows.** Every `super*` skill that writes to the vault commits and
  merges its own docs via a pull request (never a direct push, when `SUPER_PROTECTED_MAIN=true`), and
  `superrun` opens/merges the code PR the same way. On a sandboxed macOS host, `gh auth status` can fail
  even when `gh` is actually authenticated, because `gh` needs keychain access the tool sandbox blocks —
  see `SUPER_GH_DISABLE_SANDBOX` below.
- **Linux + systemd user timers, for the external (unattended) driver.** `superagent-external` /
  `launch.sh` install a per-goal `systemd --user` timer that fires a fresh headless tick on an interval.
  A crontab fallback is documented in
  [`scripts/README.md`](scripts/README.md#cron-fallback-instead-of-systemd) for hosts without systemd.
  Planning-only usage (`supergoal`/`superplan`) and the in-session `cron` driver are host-independent —
  only the external driver's systemd path is Linux-specific.

## Configuration

Every `SUPER_*` key is resolved at point of use, highest wins: a process environment variable of the
same name, then the repo-root `.superenv` file, then this plugin's shipped default
(`templates/superenv.default`). A repo with no `.superenv` runs entirely on the defaults below —
`superagent:init` creates one by copying this file so the repo can edit knobs in place.

| Key | Default | Meaning |
|---|---|---|
| SUPER_MODEL_SUPERVISOR | `inherit` | Model for the superagent tick itself (a headless tick has no session to inherit from, so `inherit` resolves to `opus` there). |
| SUPER_MODEL_PLANNER | `inherit` | Model for the `superplan` / `supergoal` dispatch subagent. |
| SUPER_MODEL_EXECUTOR | `inherit` | Model for the `superrun` dispatch subagent (the SDD controller). |
| SUPER_MODEL_PANEL | `inherit` | Model for the L7 escalation panel (3 read-only agents). |
| SUPER_MODEL_IMPLEMENTER | `sonnet` | Model for SDD implementer tasks. |
| SUPER_MODEL_FIX_APPLIER | `sonnet` | Model for SDD fix-applier tasks. |
| SUPER_MODEL_TASK_REVIEWER | `opus` | Model for the per-task SDD reviewer. |
| SUPER_MODEL_RE_REVIEWER | `opus` | Model for the SDD re-reviewer (post-fix). |
| SUPER_MODEL_BRANCH_REVIEWER | `opus` | Model for the final whole-branch reviewer. |
| SUPER_MODEL_FIX_PLANNER | `opus` | Model for fix rounds 4–5: diagnoses, then hands the mechanical edit to a fix-applier. |
| SUPER_PANEL_AGENT_TYPE | `general-purpose` | Subagent type used for the L7 panel (or `Explore`). |
| SUPER_GOAL_ROOT | `vault` | Goal folders land at `<SUPER_GOAL_ROOT>/<STAMP>-<slug>/`. |
| SUPER_LOOP_STATUS_DIRNAME | `loop-status` | Gitignored loop-state directory name; a sibling of each goal's `master-plans/`. |
| SUPER_HEAVY_STEP_LIMIT | `6` | Heavy skills (one `superplan`/`superrun` dispatch each) per `cron` session before the context-handoff gate hands off for a fresh context. |
| SUPER_LOCK_STEAL_MIN | `90` | Minutes before a stale overlap lock (a crashed tick) is auto-stolen. |
| SUPER_TICK_INTERVAL | `30m` | External-driver tick interval when `--interval` is omitted. |
| SUPER_TEST_EVIDENCE | `local` | `local` = SDD's native local TDD contract; `ci` = the only accepted test evidence is a CI run id + conclusion. |
| SUPER_CI_FLAG_TEMPLATE | *(empty)* | Commit-message CI flag grammar, e.g. `[test:%s]`; empty means the repo has no commit-flag system. |
| SUPER_CI_ONE_FLAG_PER_PUSH | `true` | Stamp exactly one CI flag per push — sharding means more pushes, never more flags on one push. |
| SUPER_CI_RUNNERS | `1` | When `>1`, queue independent long CI pushes back-to-back instead of serializing them. |
| SUPER_BRANCH_STYLE | `flat` | `flat` = no slashes in generated branch names (a slashed name can miss some CI branch-name globs). |
| SUPER_REVIEW_CONFIDENCE_FILTER | `controller` | Reviewers report every finding with severity + confidence; the controller filters — never push the filter into the reviewer prompt. |
| SUPER_MERGE_METHOD | `squash` | PR merge method used everywhere a `super*` skill merges its own PR. |
| SUPER_PROTECTED_MAIN | `true` | Default branch is protected — all changes go through a feature branch + PR, even docs-only ones. |
| SUPER_ADMIN_MERGE | `false` | Only `true` under explicit, session-scoped authorization; otherwise `gh pr merge --admin` is never used. |
| SUPER_SKIP_FINISHING_HANDOFF | `false` | `true` bypasses `superpowers:finishing-a-development-branch`'s interactive menu entirely (`superrun` Step 3a integrates the code PR itself instead). |
| SUPER_GH_DISABLE_SANDBOX | `false` | `true` on hosts (e.g. macOS) where `gh` needs keychain access the tool sandbox blocks. |
| SUPER_REPO_NOTES | *(empty)* | Optional path to a repo doc the SDD executor reads before starting the task loop, treated as standing repo policy. |

## The loop in one page

All loop state lives in one **gitignored** file per goal:
`<SUPER_GOAL_ROOT>/<goal>/<SUPER_LOOP_STATUS_DIRNAME>/<date>-<slug>.md` — YAML frontmatter as the
machine state (`status`, `iteration`, `driver`, `session_skill_count`, …) plus an append-only human log.
Being gitignored, it is local-only, survives every `super*` skill's `git checkout -b … / checkout main /
pull` dance untouched, and is never swept into a docs commit. It always lives in the **primary**
checkout, never in a worktree.

**Status vocabulary:** `WAITING FOR PLAN` / `PLANNING` → `WAITING FOR RUN` / `RUNNING` →
(`WAITING FOR CI` when a leaf pushed long CI) → back to `WAITING FOR PLAN`, until `DONE`
(nothing left to plan **and** nothing left to run). A persisted `PLANNING`/`RUNNING` on a fresh tick means
a crashed prior tick — self-healed back to its ready state. `WAITING FOR CI` is a durable **parked**
state: the loop never polls a long CI run with `gh run watch` or a sleep loop — a `cron` session arms one
event-fired `Monitor` and suspends its driver for the wait; an `external` tick does one cheap batched
`curl` check per fire and no-ops until every run is terminal.

Each tick dispatches **at most one** of `superplan` / `superrun`, always in its **own subagent**
(`Agent` tool, synchronous — the supervisor waits on the tool result, it never polls a background
subagent), never inline in the supervisor's own context. The subagent invokes the named skill and
returns its Final Report verbatim; the supervisor relays that report to the caller, advances the state
machine, and (unless terminal) lets the driver fire the next tick.

**Two drivers:**
- **`cron`** (default, attended) — an in-session `CronCreate` job re-fires `--tick <loop-file>` between
  turns of the same session, so context accumulates. A per-session heavy-step budget
  (`SUPER_HEAVY_STEP_LIMIT`, default 6) hands off for a fresh context before the window fills.
- **`external`** (unattended) — a systemd user timer (or cron) fires a **fresh headless session per
  tick**, so context never accumulates and the loop runs straight to `DONE`. Because a headless
  `claude -p` session cannot run slash commands, and Skill-tool semantics for a
  `disable-model-invocation` skill in headless print mode are unverified, the tick's prompt is a
  **file read**, not a Skill-tool invocation:
  `Read ${PLUGIN_ROOT}/skills/superagent/SKILL.md and run exactly ONE --tick on loop file <loop-file>`.
  The loop's own **internal** dispatches once that session is running —
  `superagent:superplan` / `superagent:superrun` — still go through the `Skill` tool as normal, so the
  plugin must be **installed AND enabled for headless sessions in the target repo**, or those internal
  dispatches fail opaquely deep inside the tick.

A `WAITING FOR INPUT` decision is one the 3-subagent escalation panel (superloop L7) couldn't converge
on (≥2/3 agreement). Interactively, the panel's options are put to a human via `AskUserQuestion`; on a
scheduled/unattended tick there is no one to prompt, so the loop writes the pending question plus an
`answer: <option>` instruction into the loop file and every subsequent tick polls for it — resume is
automatic once a human (or a separate monitoring console) supplies it.

Launch an unattended loop with `superagent:superagent-external` (wraps `launch.sh`, which prepares the
loop file and arms the timer in one step); watch/answer/drain any number of concurrent loops with
`superagent:superagent-monitor` (`status.sh` across every registered goal); stop a healthy loop with
`superagent:superagent-stop`; recover a genuinely wedged tick (transient status + held lock + no
progress) with `superagent:superagent-force-stop`. Full runbook, prerequisites, and the
`$SUPERAGENT_SCRIPTS` convention runnable examples use to find this plugin's installed `scripts/`
directory: [`scripts/README.md`](scripts/README.md).

## Skill roster

- **`init`** — bootstrap a repo for the plugin: prerequisite checks, `.superenv`, vault seed,
  gitignore entry. Idempotent. Invoke as `superagent:init`.
- **`supergoal`** — turn a goal description into a new goal folder + root master plan (the tree's seed).
- **`superplan`** — descend the plan tree, author the next step's plan (sub-master or implementation
  leaf), route it, and commit + merge it via PR.
- **`superrun`** — find the next ready leaf plan, execute it via `subagent-driven-development`,
  integrate the code PR, and hand off to `superfinish`.
- **`superfinish`** — post-execution bookkeeping: findings, a closeout report, and ancestor
  progress-report rows flipped complete on the way up the tree.
- **`superagent`** — the autonomy supervisor: drives a goal's root plan to completion unattended, one
  `superplan`/`superrun` dispatch per tick, via either driver.
- **`superloop`** — shared clause library the supervisor is built on: the loop-status file, the
  cron/external drivers, the overlap lock, the context-handoff gate, the sync gate, PR-merge discipline,
  and the 3-subagent escalation ladder.
- **`superauthor`** — shared plan-authoring clause library used by `supergoal`/`superplan`: the
  no-execution rule, the authoring standard, no-placeholders, self-review, and commit-and-merge-via-PR.
- **`supertraverse`** — shared plan-tree navigation used by `superplan`/`superrun`/`superfinish`:
  descent to find the next task, ascent to update ancestor rows.
- **`superagent-external`** — one-step launcher for an unattended loop: prepares the loop file and arms
  the per-goal systemd user timer.
- **`superagent-stop`** — graceful (default) or hard stopper for a healthy unattended loop; the
  loop-status file is always preserved so the loop can be relaunched.
- **`superagent-force-stop`** — recovery for a genuinely HUNG tick: halts it, reaps the stale overlap
  lock, and (by default) kicks a fresh recovery tick.
- **`superagent-monitor`** — the console/control plane across every concurrent loop on a host: status,
  answering `WAITING FOR INPUT`, drain/hard-stop/uninstall/re-arm.

## Cutting over an existing repo

If a repo already carries its own in-tree copies of these skills and driver scripts (predating this
plugin), cut it over once the plugin covers the same behavior:

1. **Delete the repo's in-repo copies** — its own `super{agent,agent-external,agent-monitor,agent-stop,
   agent-force-stop,loop,plan,run,goal,author,finish,traverse}/` skill directories and its own copy of
   the driver scripts directory. The plugin now supplies both.
2. **Install the plugin** (`/plugin marketplace add blackterrarium/superagent-plugin`,
   `/plugin install superagent`) and run `superagent:init` in the repo.
3. **Edit the generated `.superenv` to the repo's own profile** — whichever keys the repo actually
   needs to override from the shipped defaults (goal-vault location, CI test-evidence mode and flag
   grammar, runner count, finishing-handoff behavior, `gh` sandbox posture, and so on — see
   **Configuration** above for the full key list). A repo migrating from an in-tree copy that already
   had its own conventions typically reuses those same values here.
4. **Update any repo docs that name the old, unscoped skills** (e.g. a root `CLAUDE.md`) to the
   namespaced `superagent:*` names.
5. **On every host running a live timer for this repo's loop, re-run `install-timer.sh`** from the
   plugin's new script location so future ticks resolve `superagent-tick.sh` there instead of the
   deleted in-repo copy. `install-timer.sh` writes `REPO` and `LOOP_FILE` fresh into
   `~/.config/superagent/<slug>.env` each time it runs, but the tick **interval** is not stored in that
   file (it lives in the systemd timer drop-in) — read it back from the prior install (or
   `systemctl --user list-timers`) and **re-pass it explicitly** with `--interval`, or the re-install
   silently falls back to `SUPER_TICK_INTERVAL`'s default (`30m`).
