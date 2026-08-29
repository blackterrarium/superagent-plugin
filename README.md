# superagent

A plugin for **plan-tree authoring and autonomy-loop execution** — for **Claude Code, Cursor, and
OpenAI Codex**. Claude Code is the primary harness with the full feature set; Cursor and Codex run
the external (unattended) driver from generated builds derived from the same canonical skills. It
ships two things: a family of `super*` skills that turn a goal description into a self-contained,
self-reviewed vault of plans and closeout reports, and a driver (in-session or an unattended
external scheduler) that walks that tree to completion without a human babysitting every step.

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
either as an in-session `cron` job or as an external, unattended loop driven by an OS scheduler
(systemd user timer on Linux, launchd on macOS) firing fresh headless sessions — `claude -p`,
`agent -p` (Cursor), or `codex exec`, per the repo's configured harness.

## Install

### Claude Code

```
/plugin marketplace add blackterrarium/superagent-plugin
/plugin install superagent
```

### Codex

The Codex build installs through the Codex plugin marketplace — the manifest at
`.agents/plugins/marketplace.json` points at the generated [`codex/`](codex/README.md) build, so
the repo (or a local clone) is itself the marketplace root:

```
codex plugin marketplace add blackterrarium/superagent-plugin   # or: <path-to-local-clone>
codex plugin add superagent@superagent
```

Skills then load from the *installed* plugin (`~/.codex/plugins/cache/…`) in every workspace —
there is no per-invocation `--plugin-dir` on Codex. Bootstrap each target repo by asking a Codex
session to run the `init` skill (skill names are unprefixed on Codex). Auth, sandbox posture, and
the model/effort key domains are covered in the [Codex section](#codex-experimental) below.

### Cursor

Install via Cursor's marketplace flow (the root `.cursor-plugin/marketplace.json` points at the
generated [`cursor/`](cursor/README.md) build), or locally with `agent --plugin-dir <repo>/cursor`.

### Pi

No install step for the plugin itself: the external driver passes `--skill <repo>/pi/skills` on
every headless run (or `pi install /path/to/superagent-plugin/pi` for interactive use). Install
superpowers as a Pi package and, recommended, `pi-subagents`:

    npm install -g @earendil-works/pi-coding-agent
    pi install git:github.com/obra/superpowers
    pi install npm:pi-subagents        # ≥ 0.58.0 — recommended; see the Pi section below

### Bootstrap (all harnesses)

Then, in **each** target repo, bootstrap it once:

```
superagent:init
```

On Claude Code, invoke it by its full namespaced name, `superagent:init` — a bare `init` collides
with a built-in Claude Code skill (CLAUDE.md authoring) that ships unscoped in most sessions, so the
two are ambiguous the moment both are available. (On Cursor and Codex, skill names are unprefixed —
ask the session to run this plugin's `init` skill.) `superagent:init` verifies prerequisites, creates a `.superenv` config
(copied from this plugin's shipped defaults if the repo has none), seeds the goal vault
(`root.md` at `<SUPER_GOAL_ROOT>`, default `vault`) if it doesn't already exist, and adds the loop-status
gitignore entry. It is idempotent — safe to re-run — and never overwrites an existing file; it only
prepares files, it never commits, so review and commit `.superenv` / the vault seed / `.gitignore`
yourself (through a PR, if the repo protects its default branch).

This repository is private and ships no LICENSE by choice; the skills' `all rights reserved`
frontmatter is accurate — contact the owner before redistribution.

### First goal

With the repo bootstrapped, start a new initiative with `superagent:supergoal` and a goal description:

```
superagent:supergoal Build an ingest pipeline for CSV uploads
```

That produces a goal folder with a root master plan. To drive it yourself, one step at a time, invoke
`superagent:superplan` / `superagent:superrun` / `superagent:superfinish` directly. To drive it
end-to-end, attended, start the loop by typing the full namespaced invocation explicitly:

```
superagent:superagent <PLAN.md>
```

`superagent` carries `disable-model-invocation`, so it will **never auto-trigger** from a plain-English
request — it must be invoked by name, exactly like `superagent:init` above. For an unattended loop
(no console session babysitting it), use `superagent:superagent-external` instead, which wraps the
same supervisor with a systemd-timer-driven external driver.

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

`SUPER_MODEL_*` keys on the nine role keys (`_PLANNER`, `_EXECUTOR`, `_PANEL`, `_IMPLEMENTER`,
`_FIX_APPLIER`, `_TASK_REVIEWER`, `_RE_REVIEWER`, `_BRANCH_REVIEWER`, `_FIX_PLANNER`) accept
`inherit` (run on the session model) or `[<harness>:]<model>` — an optional harness prefix
(`claude` | `codex` | `cursor` | `pi`) plus that harness's own native model string: for `claude`, a
tier name (`sonnet` | `opus` | `haiku` | `fable`) or a **full model ID**
(`claude-<family>-<version>`, e.g. `claude-fable-5` — no date stamp needed); for `codex`, a Codex
model name (e.g. `gpt-5.6-sol`); for `cursor`, a Cursor model name; for `pi`, a
`<provider>/<model>[:<thinking>]` string (e.g. `openai/gpt-5`). When the prefix is omitted the
harness is *inferred* from the value's shape (an explicit prefix always wins over inference):
`sonnet`/`opus`/`haiku`/`fable`/a `claude-`-prefixed ID → `claude`; a `gpt-`-, `o<digit>`-, or
`codex`-prefixed value → `codex`; a value containing `/` → `pi`; anything else WARNs and falls back
to `inherit`, as before this feature. A role is **native** when its resolved harness equals
`SUPER_HARNESS` — dispatched exactly as always (a full ID or non-default effort on any role except
`SUPER_MODEL_SUPERVISOR` still needs the per-role agent definition, `.claude/agents/super-<role>.md`,
that `superagent:init` generates — re-run init after changing such a value; the Agent tool's `model:`
parameter is tier-enum-only). A role naming a *different* harness is **bridged**: the same per-role
dispatch hook is generated to point at a thin relay subagent instead of a real one — it shells out
to `scripts/role-bridge.sh --harness <h> --model <m> --effort <e>`, which runs that harness's own
CLI headless on the prompt and returns its final message verbatim, so the bridge target's CLI
(`claude` / `codex` / `agent` / `pi`) must be installed and already authenticated on the host
running the tick — `superagent:init` checks the binary is on `PATH` (hard error if missing) and
warns when auth looks absent. `SUPER_MODEL_SUPERVISOR` is native-only: a prefix equal to
`SUPER_HARNESS` is accepted and stripped, but any other prefix (or a foreign inference) is a hard
error in both `init` and the tick itself (exit 11) — the supervisor can never be bridged.

**Security posture.** The bridge runs the foreign CLI with approvals bypassed — codex
`--dangerously-bypass-approvals-and-sandbox` (or `--sandbox workspace-write -c
sandbox_workspace_write.network_access=true` when `SUPER_CODEX_SANDBOX=workspace-write`), cursor
`--trust --force`, claude `--allowedTools Read,Edit,Write,Bash,Grep,Glob` — i.e. exactly the same
unattended posture the tick itself runs under. A bridged role therefore has the foreign CLI's full
write access to the worktree it is pointed at; bridge only to a CLI you would let run unattended
there anyway.

**Timeouts.** A relay subagent shells out to `role-bridge.sh` and then blocks on the foreign CLI for
as long as the real task takes. Claude Code's Bash tool caps that at 120 s by default and refuses
anything above 600 s unless `BASH_DEFAULT_TIMEOUT_MS` / `BASH_MAX_TIMEOUT_MS` are set in the
process environment. `scripts/superagent-tick.sh` exports both (1 h / 2 h defaults; operator-set
values win) for every unattended tick, but an **attended (non-tick) session must set them in its own
environment before dispatching a bridged role** — otherwise the bridge is killed mid-run and the
role comes back `BRIDGE-FAILED`. The same applies to the `cron` (in-session) driver, because the
executor is always a bridge call (next paragraph): launch that session as
`BASH_DEFAULT_TIMEOUT_MS=3600000 BASH_MAX_TIMEOUT_MS=7200000 claude`; the supervisor refuses to
dispatch `superrun` when `BASH_MAX_TIMEOUT_MS` is below 2 h.

**The executor always runs as its own process.** `superrun` is the `subagent-driven-development`
controller: it dispatches implementer/reviewer subagents and must foreground-wait on each. A subagent
cannot foreground-wait on its own children (they background and yield), so dispatching `superrun` as
an Agent-tool subagent — the pre-0.5.1 design — decayed into a `SendMessage`-nudge spiral with two
writers racing on the worktree and ticks that never converged (issue #25). Since 0.5.1 the
supervisor starts `superrun` through `scripts/role-bridge.sh --tools executor` from its own Bash tool
— a fresh top-level `claude -p` (or the executor's harness CLI, when `SUPER_MODEL_EXECUTOR` is
bridged) with the tick's `Read,Edit,Write,Bash,Grep,Glob,Task,Skill` allowlist — and blocks on it
exactly as it blocked on the subagent. Inside that process SDD's subagents are depth 1 and the
synchronous wait holds. A CI-PENDING yield ends the process; the resume tick starts a fresh one with
the recorded packet (the `ci_wait.subagent` field is gone). `superplan` is unchanged (it spawns no
subagents, so a depth-1 subagent is the right container) — a bridged `superplan` role's relay still
shells out to `scripts/role-bridge.sh` with no `--tools` flag (the relay template passes only
`--harness`/`--model`/`--effort`/`--cwd`/`--prompt-file`/`--role`), it just stays inside the
ordinary Agent-tool subagent rather than becoming its own process. The `--tools planner` set is a
Pi-only construct — it's what a Pi supervisor passes when *it* dispatches `superplan` as its own
bridge process (see the `pi-only` dispatch block in `skills/superagent/SKILL.md`), not something
the Claude-native relay path above uses.

**Cursor is unverified as a bridge target and as a supervisor for bridged roles** (no live smoke;
the `agent` CLI is absent on the build host, so smoke T3 skips) — the relay definition's `tools:`
key and tool names are Claude Code's; adapt in `.cursor/agents/` if Cursor rejects them.

`SUPER_EFFORT_*` keys set per-role reasoning effort independently of the model pin, resolved the
same three-layer way, and validated in **the role's own resolved harness's domain**, not
necessarily `SUPER_HARNESS`'s: on `claude`, `low | medium | high | xhigh | max | inherit`
(`--effort` when bridged, the agent definition's `effort:` frontmatter when native); on `codex`,
`none | minimal | low | medium | high | xhigh | inherit` (no `max`; `-c
model_reasoning_effort=` bridged, the `reasoning_effort` spawn param native); on `pi`, `off |
minimal | low | medium | high | xhigh | max | inherit` (a `:<level>` suffix on the model string); on `cursor`,
`inherit` only — the CLI has no effort control at all, so any other value is a no-op and both
`superagent:init`'s validation pass and the tick itself WARN and fall back to `inherit`.
Out-of-domain values always WARN and fall back to `inherit` the same way, regardless of harness.
`inherit` means no effort flag is passed, so the CLI's own default applies. The Claude build pins
every *native* role: the four dispatch roles (supervisor/planner/executor/panel) default to
`opus` at effort `medium`/`high`/`medium`/`xhigh` respectively, and the SDD worker roles keep
their nonzero efforts (`medium` for implementer/fix-applier, `high` for the reviewers and
fix-planner, `xhigh` for the branch reviewer) — see the table below. The Agent tool has no effort
parameter, so on the Claude build a non-`inherit` effort on any subagent role pins via the
per-role agent definition `superagent:init` generates (a relay definition, generated from
`templates/super-role-bridge-agent.md`, for a bridged role; a real one otherwise) — with these
defaults that is the normal path, so a repo whose `.claude/agents/super-*.md` files are missing
(e.g. a hand-trimmed `.superenv` falling through to the plugin defaults) needs a re-run of init.
The Codex build maps the `opus` pins to `gpt-5.6-sol` (and implementer/fix-applier to
`gpt-5.6-terra`) with the same efforts and generates relay spawns from
`templates/relay-preamble.md` for a bridged role instead of an agent-definition file; the Cursor
build ships every model and effort key as `inherit` by default, since Claude tier names are not
valid Cursor model names and the Cursor CLI has no effort control, but still supports bridged
roles through the same relay-definition mechanism as Claude when a role key is set explicitly.
`SUPER_BRIDGE_RELAY_MODEL` pins the model of that thin relay subagent — see the table below for
its default and why it must not be weakened to `haiku`.

| Key | Default | Meaning |
|---|---|---|
| SUPER_MODEL_SUPERVISOR | `opus` | Model for the superagent tick itself. (`inherit` = the session model; a headless tick has no session, so `inherit` resolves to `opus` there.) |
| SUPER_MODEL_PLANNER | `opus` | Model for the `superplan` / `supergoal` dispatch subagent — plan quality has the most downstream leverage, so this stays on a strong model. |
| SUPER_MODEL_EXECUTOR | `opus` | Model for the `superrun` dispatch subagent (the SDD controller) — it applies the review confidence filter itself, so it needs judgment. |
| SUPER_MODEL_PANEL | `opus` | Model for the L7 escalation panel (3 read-only agents). |
| SUPER_MODEL_IMPLEMENTER | `sonnet` | Model for SDD implementer tasks. |
| SUPER_MODEL_FIX_APPLIER | `sonnet` | Model for SDD fix-applier tasks. |
| SUPER_MODEL_TASK_REVIEWER | `opus` | Model for the per-task SDD reviewer. |
| SUPER_MODEL_RE_REVIEWER | `opus` | Model for the SDD re-reviewer (post-fix). |
| SUPER_MODEL_BRANCH_REVIEWER | `opus` | Model for the final whole-branch reviewer. |
| SUPER_MODEL_FIX_PLANNER | `opus` | Model for fix rounds 4–5: diagnoses, then hands the mechanical edit to a fix-applier. |
| SUPER_BRIDGE_RELAY_MODEL | `sonnet` (Codex/Cursor builds: `inherit`) | Model of the thin relay subagent that runs `role-bridge.sh` for a bridged role — it only copies a prompt and returns a result, so keep it cheap; do not weaken to `haiku` — measured to answer the prompt itself instead of relaying. |
| SUPER_EFFORT_SUPERVISOR | `medium` | Reasoning effort for the superagent tick itself (claude: `--effort`; codex: `-c model_reasoning_effort=`; `inherit` passes no effort flag). Ticks fire on an interval, so per-tick cost compounds — `medium` covers the routing work. |
| SUPER_EFFORT_PLANNER | `high` | Reasoning effort for the `superplan` / `supergoal` dispatch subagent. |
| SUPER_EFFORT_EXECUTOR | `medium` | Reasoning effort for the `superrun` dispatch subagent (the SDD controller) — the hard thinking is delegated to the reviewers and fix planner. |
| SUPER_EFFORT_PANEL | `xhigh` | Reasoning effort for the L7 escalation panel — it fires rarely and only when everything cheaper has failed. |
| SUPER_EFFORT_IMPLEMENTER | `medium` | Reasoning effort for SDD implementer tasks. |
| SUPER_EFFORT_FIX_APPLIER | `medium` | Reasoning effort for SDD fix-applier tasks. |
| SUPER_EFFORT_TASK_REVIEWER | `high` | Reasoning effort for the per-task SDD reviewer. |
| SUPER_EFFORT_RE_REVIEWER | `high` | Reasoning effort for the SDD re-reviewer (post-fix). |
| SUPER_EFFORT_BRANCH_REVIEWER | `xhigh` | Reasoning effort for the final whole-branch reviewer. |
| SUPER_EFFORT_FIX_PLANNER | `high` | Reasoning effort for fix rounds 4–5. |
| SUPER_CODEX_SANDBOX | `danger-full-access` | Sandbox posture for the Codex harness, and for any codex-bridged role on other harnesses: `danger-full-access` (`--dangerously-bypass-approvals-and-sandbox`) or `workspace-write` (`--sandbox workspace-write -c sandbox_workspace_write.network_access=true`; note codex keeps the repo's top-level `.git/` read-only in this mode, so git fetch/commit fail and the sync gate parks the loop). Out-of-domain values abort the tick. |
| SUPER_PI_SUBAGENTS | recommended | Pi harness only: recommended (WARN if pi-subagents is missing/old; SDD children then run sequentially without pins) · required (init aborts) · off. |
| SUPER_PANEL_AGENT_TYPE | `general-purpose` | Subagent type used for the L7 panel (or `Explore`). |
| SUPER_GOAL_ROOT | `vault` | Goal folders land at `<SUPER_GOAL_ROOT>/<STAMP>-<slug>/`. |
| SUPER_LOOP_STATUS_DIRNAME | `loop-status` | Gitignored loop-state directory name; a sibling of each goal's `master-plans/`. |
| SUPER_HEAVY_STEP_LIMIT | `6` | Heavy skills (one `superplan`/`superrun` dispatch each) per `cron` session before the context-handoff gate hands off for a fresh context. |
| SUPER_LOCK_STEAL_MIN | `90` | Minutes before a stale overlap lock (a crashed tick) is auto-stolen. |
| SUPER_TICK_INTERVAL | `10m` | External-driver tick interval when `--interval` is omitted. |
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

Mixing example — Claude supervisor, OpenAI implementer, Pi-hosted panel:

    SUPER_HARNESS=claude
    SUPER_MODEL_IMPLEMENTER=codex:gpt-5.6-terra   SUPER_EFFORT_IMPLEMENTER=medium
    SUPER_MODEL_PANEL=pi:openai/gpt-5             SUPER_EFFORT_PANEL=high

The supervisor and every other role stay on the native Claude harness; `implementer` and `panel` are
bridged — each dispatch runs a relay subagent that shells out to `scripts/role-bridge.sh` on, respectively,
an authenticated `codex` CLI and an authenticated `pi` CLI, and returns that CLI's final message
verbatim. `superagent:init` regenerates `.claude/agents/super-implementer.md` and
`.claude/agents/super-panel.md` as relay definitions and checks both `codex` and `pi` are on `PATH`.

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
`curl` check per fire and no-ops until every run is terminal. On the shipped external driver, parked
fires are free — the wrapper checks the recorded run ids in bash and starts no session until they are
terminal.

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
scheduled/unattended tick there is no one to prompt,
so the loop writes the pending question plus an `answer: <option>` instruction into the loop file,
the driver notifies the operator once (`SUPER_NOTIFY_CMD` / desktop notification), and scheduled
fires are free until an answer exists (a bash check, no session). `scripts/answer.sh <slug> "<option>"`
records the answer under the lock and kicks a tick, so resume is immediate.

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
  `superplan`/`superrun` dispatch per tick, via either driver. Carries `disable-model-invocation`, so it
  never auto-triggers — invoke it explicitly by its full name, `superagent:superagent <PLAN.md>`.
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

## Cursor (experimental)

> **Unverified:** Cursor as a bridge *target* and as a supervisor for bridged roles has no live
> smoke coverage (the `agent` CLI is absent on the build host, so bridge smoke T3 skips) — the relay
> definition's `tools:` key and tool names are Claude Code's; adapt in `.cursor/agents/` if Cursor
> rejects them.

A generated Cursor build of the plugin lives in [`cursor/`](cursor/README.md) — external
(unattended) driver only, with the Claude Code in-session machinery stripped at build time.
`scripts/build-cursor-skills.sh` derives it from conditional markers in the canonical skills
(single source of truth; `--check` verifies the committed tree is fresh). Install on Cursor via
its marketplace flow (this repo's root `.cursor-plugin/marketplace.json` points at `cursor/`) or
locally with `agent --plugin-dir <repo>/cursor`. Model keys (`SUPER_MODEL_*`) take a Cursor model
name or `inherit` when native, or `[<harness>:]<model>` to bridge a role to another harness's CLI
(`claude` | `codex` | `pi`) via `scripts/role-bridge.sh`, shipped in this build; a bridged role
generates a relay agent definition the same way the Claude build does — see Configuration above.

**Status: smoke-validated** (runs 1–2, 2026-08-12): headless `agent -p` + `--plugin-dir` loading,
skill enumeration/invocation from a neutral workspace, and the tick entry point all work; the
external-driver scripts are harness-aware (`SUPER_HARNESS=cursor`), and superpowers-under-Cursor
(required by `superrun`) loads on a host with it configured. Remaining gap: no end-to-end
multi-tick loop has been driven to DONE on Cursor — see `cursor/README.md`. To re-run the smoke:

```
git clone https://github.com/blackterrarium/superagent-plugin && cd superagent-plugin
bash scripts/cursor-smoke.sh
```

## Codex (experimental)

A generated Codex build of the plugin lives in [`codex/`](codex/README.md) — external (unattended)
driver only, in the shape of a Codex plugin-marketplace tree. Install (see also Install above):
`codex plugin marketplace add blackterrarium/superagent-plugin` (or a local clone path — the root
`.agents/plugins/marketplace.json` makes the repo itself the marketplace root; `<clone>/codex`
works too) then `codex plugin add superagent@superagent`; the skills and bundled templates load via
the *installed* plugin copy under `~/.codex/plugins/cache/`, not a `--plugin-dir` flag.
`scripts/build-codex-skills.sh` derives the build from the same conditional markers as the Cursor
build (single source of truth; `--check` verifies the committed tree is fresh) — plus a
`codex-only` marker for content inert in the Claude Code and Cursor builds.

Auth is `OPENAI_API_KEY` in the target repo's `.env`, else the CLI's own stored login (`codex
login`). Sandbox posture is a separate `.superenv` knob, `SUPER_CODEX_SANDBOX`:
`danger-full-access` (default — `--dangerously-bypass-approvals-and-sandbox`, matching the
unsandboxed claude harness) or `workspace-write` (`--sandbox workspace-write -c
sandbox_workspace_write.network_access=true`; codex keeps the repo's top-level `.git/` read-only
in this mode, so git fetch/commit fail and the sync gate parks the loop). Model keys (`SUPER_MODEL_*`)
take Codex model names (e.g. `gpt-5.1-codex`) or `inherit` when native, or `[<harness>:]<model>`
to bridge a role to another harness's CLI (`claude` | `cursor` | `pi`) via `scripts/role-bridge.sh`,
shipped in this build; effort keys (`SUPER_EFFORT_*`) take `none | minimal | low | medium | high |
xhigh | inherit` when the role is native to Codex, or the bridged role's own harness domain — see
Configuration above for the shared defaults table (same role keys as Claude Code; a native role's
pin rides `spawn_agent`'s `model`/`reasoning_effort` parameters, there is no `.claude/agents/`-style
definition file on Codex — a bridged role instead spawns a relay agent from
`templates/relay-preamble.md`).

**Status: smoke-validated 8/8** (2026-08-12, codex CLI 0.147.0 on macOS): headless `codex exec`,
the marketplace install path, skill enumeration and model-invocation from a neutral workspace,
bundled-template access from the installed plugin copy, `spawn_agent` availability (the subagent
mapping), the file-read tick entry with its hard gate, and the `-c model_reasoning_effort` effort
override — see `codex/README.md` for the full validated list. Remaining gap: no end-to-end
multi-tick loop has been driven to DONE on Codex. To re-run the smoke:

```
git clone https://github.com/blackterrarium/superagent-plugin && cd superagent-plugin
bash scripts/codex-smoke.sh
```

## Pi (experimental)

A generated Pi build lives in [`pi/`](pi/README.md) — external (unattended) driver only, laid out
as a Pi package but delivered per run by `--skill`. `scripts/build-pi-skills.sh` derives it from
the same markers as the other builds plus a `pi-only` marker.

**Dispatch is hybrid.** The supervisor never uses a subagent tool: `superplan` and `superrun` are
blocking `bash` calls to `scripts/role-bridge.sh` (child `pi -p` — or `codex`/`claude`/`agent` for a
bridged role — with `--tools planner` / `--tools executor`), and the L7 panel is one blocking call
to `scripts/bridge-fanout.sh` (three concurrent bridge runs, 1800 s timeout, framed output).
superrun's SDD children go through superpowers' own Pi mapping — the `pi-subagents` `subagent`
tool with `async: false` — and their model/thinking pins ride `.pi/agents/super-<role>.md`
definitions `init` generates (native: `templates/super-role-pi-agent.md`; a role bridged to
another harness: `templates/super-role-pi-bridge-agent.md`, a relay). Without `pi-subagents`,
SDD runs sequentially in-context and pins are not applied (`SUPER_PI_SUBAGENTS=required` makes
init abort instead).

Every headless run passes `--approve` (the operator armed the loop on this repo — Cursor `--trust`
parity). Auth is the CLI's `~/.pi/agent/auth.json` or provider keys in the target repo's `.env`.
Model keys are `pi:<provider>/<model>` (or a bare `<provider>/<model>`); effort keys
`off | minimal | low | medium | high | xhigh | max` — the tick passes `--thinking`, the bridge the
`:<level>` suffix (or `--thinking` when the model is `inherit`).

**Status:** live smoke on 2026-08-29, pi CLI 0.84.3, `pi-subagents` NOT installed on the build
host — PASS 7 / FAIL 1 (informational) / SKIPPED 3. P1 (bad-model exit status): pi exits a plain
**1** for both a bad model and a failed turn — no distinct code — which is the datum the bridge's
exit-3 mapping relies on. P2 (`--skill` delivery): PASS. P4a (tool-list probe, informational):
PASS. P4b (tool-list probe, informational): **inconclusive** — no extension tools were installed
on the smoke host, so the probe returned the base tool set and never exercised the case it checks.
P3a/P3c (`pi-subagents` probes) and T4 (relay round trip) were **SKIPPED**, not verified —
`pi-subagents` was not installed on this host, so the P3c nested-wait verdict is **unverified**
pending a re-run on a host with `pi-subagents ≥0.58.0`. Remaining gaps: no tick, single or
multi, has been driven end-to-end on a real loop file on Pi (T3 only exercised the file-read +
hard-gate rejection path with no `PLAN.md` supplied); superpowers was not installed as a Pi
package on the smoke host (`superpowers package: 0`), so Pi skill listing and superpowers' Pi
SDD mapping are unverified; `superagent:init` has not been run on Pi; S3 with `pi-subagents` not
exercised inside a real superrun (all pending the deferred Task 10). Re-run:
`bash scripts/pi-smoke.sh` (`PI_SMOKE_MODEL=<provider>/<id>` to pin a model).

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
