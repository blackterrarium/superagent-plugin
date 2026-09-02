# superagent

**superagent** turns a goal description into a tree of self-reviewed plans, then executes that tree
to completion without a human babysitting every step. It ships as a plugin for **Claude Code** (the
primary harness, full feature set) with generated builds for **OpenAI Codex**, **Cursor**, and
**Pi** that run the unattended driver.

It has two halves:

- A family of `super*` **skills** that author plans, execute them, and write closeout reports into a
  goal vault in your repo. Every change lands through a pull request.
- A **driver** that walks the plan tree one step at a time, either inside your session or as an
  unattended loop fired by an OS scheduler (systemd on Linux, launchd on macOS).

## Contents

- [How it works](#how-it-works)
- [Quick start (Claude Code)](#quick-start-claude-code)
- [Prerequisites](#prerequisites)
- [Running the loop](#running-the-loop)
- [Configuration](#configuration)
- [Other harnesses: Codex, Cursor, Pi](#other-harnesses-codex-cursor-pi)
- [Skill reference](#skill-reference)
- [Design notes](#design-notes)
- [Migrating a repo with in-tree copies](#migrating-a-repo-with-in-tree-copies)
- [License](#license)

## How it works

```
goal description
      │
      ▼
  supergoal ──► root master plan (a progress-report table of steps)
      │
      ▼   repeat until every step is planned and executed
  superplan ──► writes the next step's plan (sub-master or leaf)
  superrun  ──► executes the next ready leaf, merges the code PR
  superfinish ─► closeout report, marks rows complete up the tree
      │
      ▼
    DONE
```

The four skills in the cycle:

| Skill | What it does | Touches source code? |
|---|---|---|
| `supergoal` | Turns a goal description into a goal folder and a root master plan with a progress-report table. | No |
| `superplan` | Descends the table, writes the next step's plan (a deeper sub-master or a leaf implementation plan), and marks the row `PLAN WRITTEN — ready to execute`. | No |
| `superrun` | Finds the next ready leaf, executes it by delegating to `superpowers:subagent-driven-development`, and integrates the code PR. | Yes, only via subagent-driven-development |
| `superfinish` | Records findings, writes a closeout report, and flips the tree's rows complete on the way back up. | No |

The **`superagent` supervisor** sits above the cycle. Each **tick** dispatches exactly one
`superplan` or `superrun`, advances the state machine, and stops. Ticks repeat until the tree is
both fully planned and fully executed. The supervisor can run as an in-session cron job (attended)
or as an external loop where an OS scheduler fires a fresh headless session per tick (unattended).
See [Running the loop](#running-the-loop).

## Quick start (Claude Code)

**1. Install the plugin and its dependency.** `superrun` needs the superpowers plugin; planning
skills work without it.

```
/plugin marketplace add blackterrarium/superagent-plugin
/plugin install superagent
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers
```

**2. Authenticate `gh`.** Every skill that writes to the vault merges its own PR, and `superrun`
opens the code PR the same way. See [Prerequisites](#prerequisites) for the macOS keychain caveat.

**3. Bootstrap each target repo once.**

```
superagent:init
```

Use the full namespaced name. A bare `init` collides with a built-in Claude Code skill (CLAUDE.md
authoring), so the two are ambiguous whenever both are available. `superagent:init`:

- verifies prerequisites;
- creates a `.superenv` config from the plugin's shipped defaults if the repo has none;
- seeds the goal vault (`root.md` under `SUPER_GOAL_ROOT`, default `vault`) if absent;
- adds the loop-status gitignore entry;
- on Claude Code, generates per-role agent definitions in `.claude/agents/` for the model and
  effort pins in `.superenv`.

It is idempotent and never overwrites an existing file. It only prepares files and never commits,
so review and commit `.superenv`, the vault seed, and `.gitignore` yourself (through a PR if the
repo protects its default branch).

**4. Create a goal.**

```
superagent:supergoal Build an ingest pipeline for CSV uploads
```

This produces a goal folder with a root master plan.

**5. Drive it.** Pick one:

| Mode | How | Notes |
|---|---|---|
| Manual, one step at a time | Invoke `superagent:superplan`, `superagent:superrun`, `superagent:superfinish` directly. | Full control, no loop. |
| Attended loop | `superagent:superagent <PLAN.md>` | Runs in your session as a cron job. Launch the session with the Bash timeout variables described under [Timeouts](#timeouts). |
| Unattended loop | `superagent:superagent-external <PLAN.md>` | Arms a per-goal OS scheduler entry. Needs no console session. |

`superagent` carries `disable-model-invocation`, so it never auto-triggers from a plain-English
request. Invoke it by its full name, exactly like `superagent:init`.

## Prerequisites

| Requirement | Needed for | Notes |
|---|---|---|
| **superpowers plugin** | `superrun` | `superrun` refuses outright if `superpowers:subagent-driven-development` is not resolvable. `supergoal` and `superplan` work without it. |
| **`gh`, authenticated** | Every PR flow | Skills never push directly when `SUPER_PROTECTED_MAIN=true`. On a sandboxed macOS host `gh auth status` can fail even when `gh` is authenticated, because the tool sandbox blocks keychain access. Set `SUPER_GH_DISABLE_SANDBOX=true` there. |
| **Per-user OS scheduler** | The external (unattended) driver | A `systemd --user` timer on Linux, or a launchd LaunchAgent on macOS (fires only while the user is logged in and the Mac is awake). A crontab fallback is documented in [`scripts/README.md`](scripts/README.md#cron-fallback-instead-of-systemd). Planning-only use and the in-session cron driver are host-independent. |
| **Foreign harness CLIs** | Bridged roles only | If a role is pinned to another harness, that harness's CLI must be installed and authenticated on the host running the tick. See [Bridging a role to another harness](#bridging-a-role-to-another-harness). |

## Running the loop

### The loop-status file

All loop state lives in one **gitignored** file per goal:

```
<SUPER_GOAL_ROOT>/<goal>/<SUPER_LOOP_STATUS_DIRNAME>/<date>-<slug>.md
```

YAML frontmatter holds the machine state (`status`, `iteration`, `driver`, `session_skill_count`,
and so on) and the body is an append-only human log. Because it is gitignored, it is local-only,
survives every skill's branch-switching, and is never swept into a docs commit. It always lives in
the **primary** checkout, never in a worktree.

### Statuses

| Status | Meaning |
|---|---|
| `WAITING FOR PLAN` / `PLANNING` | Next tick dispatches `superplan` / a `superplan` is in flight. |
| `WAITING FOR RUN` / `RUNNING` | Next tick dispatches `superrun` / a `superrun` is in flight. |
| `WAITING FOR CI` | A leaf pushed a long CI run. The loop is parked, not polling. |
| `WAITING FOR INPUT` | The loop needs a human decision. See below. |
| `DONE` | Nothing left to plan **and** nothing left to run. |

A `PLANNING` or `RUNNING` status found on a fresh tick means the previous tick crashed. The loop
self-heals it back to the corresponding ready state.

`WAITING FOR CI` is a durable parked state. The loop never polls a long CI run with `gh run watch`
or a sleep loop. A cron session arms one event-fired `Monitor` and suspends its driver. An external
tick checks the recorded run ids in bash and starts no session until every run is terminal, so
parked fires are free.

### Two drivers

| | `cron` (attended, default) | `external` (unattended) |
|---|---|---|
| Fired by | An in-session `CronCreate` job between turns of the same session. | A systemd user timer, a launchd LaunchAgent, or cron. |
| Context | Accumulates. A per-session heavy-step budget (`SUPER_HEAVY_STEP_LIMIT`, default 6) hands off to a fresh context before the window fills. | Never accumulates. Each tick is a fresh headless session (`claude -p`, `agent -p`, `codex exec`, or `pi -p` per `SUPER_HARNESS`), so the loop runs straight to `DONE`. |
| Launched with | `superagent:superagent <PLAN.md>` | `superagent:superagent-external <PLAN.md>` |

Each tick dispatches **at most one** of `superplan` / `superrun`, never inline in the supervisor's
own context, and always **synchronously**. `superplan` runs in its own subagent. `superrun` runs
as the top-level agent of its **own CLI process**, started through `scripts/role-bridge.sh --tools
executor` from the supervisor's Bash tool (see [Design notes](#design-notes) for why). The
dispatched skill returns its Final Report verbatim; the supervisor relays it, advances the state
machine, and lets the driver fire the next tick.

**Headless ticks require the plugin to be installed and enabled for headless sessions in the
target repo.** The external tick's prompt is a file read (`Read .../skills/superagent/SKILL.md and
run exactly ONE --tick on loop file <loop-file>`) rather than a Skill-tool invocation, but the
loop's internal `superagent:superplan` / `superagent:superrun` dispatches still go through the
`Skill` tool. If the plugin is not enabled there, those dispatches fail opaquely deep inside the
tick.

### Decisions the loop cannot make

When the 3-subagent escalation panel (superloop L7) fails to reach 2-of-3 agreement, the loop needs
a human. In an attended session, the options are put to you via `AskUserQuestion`. On an unattended
tick:

1. The loop writes the pending question plus an `answer: <option>` instruction into the loop file
   and sets `WAITING FOR INPUT`.
2. The driver notifies you once, via `SUPER_NOTIFY_CMD` or a desktop notification.
3. Scheduled fires are free until an answer exists (a bash check, no session).
4. `scripts/answer.sh <slug> "<option>"` records the answer under the lock and kicks a tick, so
   resume is immediate.

### Operating an unattended loop

| Skill | Use it to |
|---|---|
| `superagent:superagent-external` | Launch: prepares the loop file and arms the per-goal scheduler entry in one step (wraps `launch.sh`). |
| `superagent:superagent-monitor` | Watch, answer, drain, hard-stop, uninstall, or re-arm any number of concurrent loops (`status.sh` across every registered goal). |
| `superagent:superagent-stop` | Stop a healthy loop. Default is a graceful drain; `--hard` halts an in-flight tick. The loop-status file is always preserved. |
| `superagent:superagent-force-stop` | Recover a genuinely wedged tick: transient status, held lock, no progress. Halts it, reaps the stale lock, kicks a recovery tick. |

The full runbook, the `$SUPERAGENT_SCRIPTS` convention for finding the installed `scripts/`
directory, and every driver script are documented in [`scripts/README.md`](scripts/README.md).

## Configuration

### How keys resolve

Every `SUPER_*` key is resolved at point of use. Highest wins:

1. A process environment variable of the same name.
2. The repo-root `.superenv` file.
3. The plugin's shipped default, [`templates/superenv.default`](templates/superenv.default).

A repo with no `.superenv` runs entirely on the defaults. `superagent:init` creates one by copying
the template so you can edit knobs in place.

### Roles

Ten role keys control which model and effort each part of the loop uses. The supervisor is the
tick itself; the other nine are dispatched by it.

| Role | Runs |
|---|---|
| `SUPERVISOR` | The superagent tick itself. Always native to `SUPER_HARNESS`; can never be bridged. |
| `PLANNER` | The `superplan` / `supergoal` dispatch subagent. |
| `EXECUTOR` | `superrun`, the subagent-driven-development (SDD) controller. Runs as its own CLI process. |
| `PANEL` | The L7 escalation panel (three read-only agents). |
| `IMPLEMENTER`, `FIX_APPLIER` | SDD worker tasks. |
| `TASK_REVIEWER`, `RE_REVIEWER`, `BRANCH_REVIEWER` | SDD per-task reviewer, post-fix re-reviewer, final whole-branch reviewer. |
| `FIX_PLANNER` | Fix rounds 4–5: diagnoses, then hands the mechanical edit to a fix-applier. |

Each role has a `SUPER_MODEL_<ROLE>` and a `SUPER_EFFORT_<ROLE>` key.

### Model values

A model key accepts `inherit` (the session model; a headless tick has no session, so the supervisor
falls back to `claude-opus-4-8` there) or `[<harness>:]<model>`:

| Harness | Native model string | Inferred when the prefix is omitted and the value... |
|---|---|---|
| `claude` | A tier (`sonnet`, `opus`, `haiku`, `fable`) or a full ID (`claude-<family>-<version>`, e.g. `claude-fable-5`, no date stamp needed) | is a tier name or starts with `claude-` |
| `codex` | A Codex model name (e.g. `gpt-5.6-sol`) | starts with `gpt-`, `o<digit>`, or `codex` |
| `cursor` | A Cursor model name (`agent --list-models`) | never inferred; needs the prefix |
| `pi` | `<provider>/<model>[:<thinking>]` (e.g. `openai/gpt-5`) | contains `/` |

An explicit prefix always wins over inference. A value that matches nothing WARNs and falls back to
`inherit`.

A role is **native** when its resolved harness equals `SUPER_HARNESS`, and **bridged** when it
names a different one. `SUPER_MODEL_SUPERVISOR` is native-only: a prefix equal to `SUPER_HARNESS`
is accepted and stripped, but any other prefix or foreign inference is a hard error in both `init`
and the tick (exit 11).

On Claude Code, a full ID or a non-`inherit` effort on any role except the supervisor needs the
per-role agent definition `.claude/agents/super-<role>.md` that `superagent:init` generates,
because the Agent tool's `model:` parameter accepts tier names only. **Re-run `superagent:init`
after changing such a value.** With the shipped defaults this is the normal path, so a repo whose
`super-*.md` files are missing needs a re-run of init.

### Effort values

Effort keys are resolved the same three-layer way and validated in **the role's own resolved
harness's domain**, not necessarily `SUPER_HARNESS`'s. `inherit` passes no effort flag, so the
CLI's own default applies. Out-of-domain values WARN and fall back to `inherit`.

| Harness | Accepted values | How it is applied |
|---|---|---|
| `claude` | `low`, `medium`, `high`, `xhigh`, `max`, `inherit` | `--effort` when bridged or on the tick; the agent definition's `effort:` frontmatter when native |
| `codex` | `none`, `minimal`, `low`, `medium`, `high`, `xhigh`, `inherit` (no `max`) | `-c model_reasoning_effort=` when bridged or on the tick; the `reasoning_effort` spawn parameter when native |
| `pi` | `off`, `minimal`, `low`, `medium`, `high`, `xhigh`, `max`, `inherit` | `--thinking` on the tick; a `:<level>` suffix on the model string otherwise |
| `cursor` | `inherit` only | The CLI has no effort control. Any other value WARNs in both `init` and the tick and is treated as `inherit`. |

On Claude, the `CLAUDE_CODE_EFFORT_LEVEL` environment variable overrides both the tick flag and
every per-role pin. Leave it unset in scheduler environments.

### Bridging a role to another harness

Pinning a role to a harness other than `SUPER_HARNESS` **bridges** it. The same per-role dispatch
hook is generated, but it points at a thin relay subagent instead of a real one. The relay shells
out to `scripts/role-bridge.sh --harness <h> --model <m> --effort <e>`, which runs that harness's
CLI headless on the prompt and returns its final message verbatim.

Example: a Claude supervisor with an OpenAI implementer and a Pi-hosted panel.

```
SUPER_HARNESS=claude
SUPER_MODEL_IMPLEMENTER=codex:gpt-5.6-terra   SUPER_EFFORT_IMPLEMENTER=medium
SUPER_MODEL_PANEL=pi:openai/gpt-5             SUPER_EFFORT_PANEL=high
```

Every other role stays native. `superagent:init` regenerates `.claude/agents/super-implementer.md`
and `.claude/agents/super-panel.md` as relay definitions, checks that `codex` and `pi` are on
`PATH` (hard error if missing), and warns when auth looks absent. `SUPER_BRIDGE_RELAY_MODEL` pins
the relay subagent's model; keep it on `sonnet` (see the key table for why not `haiku`).

**Security posture.** The bridge runs the foreign CLI with approvals bypassed, exactly the same
unattended posture the tick itself runs under:

| Target | Flags |
|---|---|
| `codex` | `--dangerously-bypass-approvals-and-sandbox`, or `--sandbox workspace-write -c sandbox_workspace_write.network_access=true` when `SUPER_CODEX_SANDBOX=workspace-write` |
| `cursor` | `--trust --force` |
| `claude` | `--allowedTools Read,Edit,Write,Bash,Grep,Glob` |
| `pi` | `--approve --no-session` |

A bridged role has the foreign CLI's full write access to the worktree. Bridge only to a CLI you
would let run unattended there anyway.

#### Timeouts

A relay blocks on the foreign CLI for as long as the real task takes. Claude Code's Bash tool caps
that at 120 s by default and refuses anything above 600 s unless `BASH_DEFAULT_TIMEOUT_MS` and
`BASH_MAX_TIMEOUT_MS` are set in the process environment.

- `scripts/superagent-tick.sh` exports both (1 h / 2 h defaults; operator-set values win) for
  every unattended tick.
- An **attended session must set them itself** before dispatching a bridged role, or the bridge is
  killed mid-run and the role comes back `BRIDGE-FAILED`. This includes the in-session cron driver,
  because the executor is always a bridge call. Launch the session as:

  ```
  BASH_DEFAULT_TIMEOUT_MS=3600000 BASH_MAX_TIMEOUT_MS=7200000 claude
  ```

  The supervisor refuses to dispatch `superrun` when `BASH_MAX_TIMEOUT_MS` is below 2 h.

**Cursor is unverified as a bridge target and as a supervisor for bridged roles.** The `agent` CLI
is absent on the build host, so bridge smoke T3 skips. The relay definition's `tools:` key and tool
names are Claude Code's; adapt them in `.cursor/agents/` if Cursor rejects them.

The three-harness split (Claude supervising, Codex implementing, Pi reviewing) is exercised end to
end by `scripts/mix-e2e.sh`, which also asserts from `role-bridge.sh`'s log lines that every pinned
role ran on its pinned harness. See "Multi-harness mixing e2e testbench" in
[`scripts/README.md`](scripts/README.md).

### Key reference

Defaults shown are the Claude Code build's. Other builds differ; see
[Other harnesses](#other-harnesses-codex-cursor-pi).

**Models and effort**

| Key | Default | Meaning |
|---|---|---|
| SUPER_MODEL_SUPERVISOR | `claude:claude-opus-4-8` | The tick itself. `inherit` resolves to `claude-opus-4-8` on a headless tick. |
| SUPER_MODEL_PLANNER | `claude:claude-opus-4-8` | Plan quality has the most downstream leverage, so this stays on a strong model. |
| SUPER_MODEL_EXECUTOR | `claude:claude-opus-4-8` | `superrun` applies the review confidence filter itself, so it needs judgment. |
| SUPER_MODEL_PANEL | `claude:claude-opus-4-8` | L7 escalation panel. |
| SUPER_MODEL_IMPLEMENTER | `claude:sonnet` | |
| SUPER_MODEL_FIX_APPLIER | `claude:sonnet` | |
| SUPER_MODEL_TASK_REVIEWER | `claude:claude-opus-4-8` | |
| SUPER_MODEL_RE_REVIEWER | `claude:claude-opus-4-8` | |
| SUPER_MODEL_BRANCH_REVIEWER | `claude:claude-opus-4-8` | |
| SUPER_MODEL_FIX_PLANNER | `claude:claude-opus-4-8` | |
| SUPER_BRIDGE_RELAY_MODEL | `sonnet` (Codex build: `gpt-5.6-terra`; Pi build: `openai-codex/gpt-5.6-terra`; Cursor build: `inherit`) | Model of the relay subagent for a bridged role. Bare native name, no harness prefix. It only copies a prompt and returns a result, so keep it cheap, but do not weaken to `haiku`: measured to answer the prompt itself instead of relaying. Every build that has a model choice pins the sonnet-tier peer rather than `inherit`, so the relay does not float with the CLI's default subagent model. |
| SUPER_EFFORT_SUPERVISOR | `medium` | Ticks fire on an interval, so per-tick cost compounds. `medium` covers the routing work. |
| SUPER_EFFORT_PLANNER | `high` | |
| SUPER_EFFORT_EXECUTOR | `medium` | The hard thinking is delegated to the reviewers and fix planner. |
| SUPER_EFFORT_PANEL | `xhigh` | Fires rarely, only when everything cheaper has failed. |
| SUPER_EFFORT_IMPLEMENTER | `medium` | |
| SUPER_EFFORT_FIX_APPLIER | `medium` | |
| SUPER_EFFORT_TASK_REVIEWER | `high` | |
| SUPER_EFFORT_RE_REVIEWER | `high` | |
| SUPER_EFFORT_BRANCH_REVIEWER | `xhigh` | |
| SUPER_EFFORT_FIX_PLANNER | `high` | |
| SUPER_PANEL_AGENT_TYPE | `general-purpose` | Subagent type for the L7 panel, or `Explore`. |

**Harness**

| Key | Default | Meaning |
|---|---|---|
| SUPER_HARNESS | `claude` | `claude` \| `cursor` \| `codex` \| `pi`. Which CLI the external driver fires per tick (`claude -p` / `agent -p` / `codex exec` / `pi -p`). |
| SUPER_CODEX_SANDBOX | `danger-full-access` | Sandbox for the Codex harness and any codex-bridged role. `danger-full-access` matches the unsandboxed claude harness. `workspace-write` keeps the repo's top-level `.git/` read-only, so git fetch/commit fail and the sync gate parks the loop. Out-of-domain values abort the tick. |
| SUPER_PI_SUBAGENTS | `recommended` | Pi harness only. `recommended`: WARN if `pi-subagents` is missing or older than 0.58.0; SDD children then run sequentially without pins. `required`: init aborts instead. `off`: never generate `.pi/agents/` or use the subagent tool. |

**Paths and loop tuning**

| Key | Default | Meaning |
|---|---|---|
| SUPER_GOAL_ROOT | `vault` | Goal folders land at `<SUPER_GOAL_ROOT>/<STAMP>-<slug>/`. |
| SUPER_LOOP_STATUS_DIRNAME | `loop-status` | Gitignored loop-state directory, a sibling of each goal's `master-plans/`. |
| SUPER_HEAVY_STEP_LIMIT | `6` | Heavy skills (one dispatch each) per cron session before the context-handoff gate hands off. |
| SUPER_LOCK_STEAL_MIN | `90` | Minutes before a stale overlap lock from a crashed tick is auto-stolen. |
| SUPER_TICK_INTERVAL | `10m` | External-driver interval when `--interval` is omitted. |

**External driver**

| Key | Default | Meaning |
|---|---|---|
| SUPER_AUTO_DISARM_ON_DONE | `true` | A tick that finds `DONE` uninstalls its own scheduler entry (loop-status and env file kept). `false` keeps the timer polling. |
| SUPER_INPUT_GATE | `true` | A tick that finds `WAITING FOR INPUT` with no `answer:` line exits without launching a session. `false` launches one every interval. |
| SUPER_CI_GATE | `true` | A tick that finds `WAITING FOR CI` checks `ci_wait.runs` with `gh run view` in bash and exits without a session while any run is still running. |
| SUPER_CI_MAX_WAIT_MIN | `180` | Once a CI park is older than this with runs still incomplete, notify once (`ci-stale`) and let the session run each interval. `0` gates until every run completes. |
| SUPER_NOTIFY_CMD | *(empty)* | Shell snippet run when a loop parks on `WAITING FOR INPUT`, reaches `DONE`, or a CI park goes stale. Env: `SUPERAGENT_EVENT` (`waiting-for-input` \| `done` \| `ci-stale`), `SUPERAGENT_SLUG`, `LOOP_FILE`, `SUPERAGENT_TITLE`, `SUPERAGENT_BODY` (carries the `## Pending decision` text). **Single-quote the value**: `.superenv` is sourced under `set -u`, so an unquoted `$SUPERAGENT_BODY` aborts every tick. Empty means a desktop notification (`osascript` / `notify-send`) when available. |

**Git, CI, and review policy**

| Key | Default | Meaning |
|---|---|---|
| SUPER_TEST_EVIDENCE | `local` | `local`: SDD's native local TDD contract. `ci`: the only accepted test evidence is a CI run id plus conclusion. |
| SUPER_CI_FLAG_TEMPLATE | *(empty)* | Commit-message CI flag grammar, e.g. `[test:%s]`. Empty means no commit-flag system. |
| SUPER_CI_ONE_FLAG_PER_PUSH | `true` | Exactly one CI flag per push. Sharding means more pushes, never more flags on one push. |
| SUPER_CI_RUNNERS | `1` | When above 1, queue independent long CI pushes back-to-back instead of serializing them. |
| SUPER_BRANCH_STYLE | `flat` | No slashes in generated branch names (a slashed name can miss some CI branch-name globs). |
| SUPER_REVIEW_CONFIDENCE_FILTER | `controller` | Reviewers report every finding with severity and confidence; the controller filters. Never push the filter into the reviewer prompt (Claude 5 reviewers silently drop findings). |
| SUPER_MERGE_METHOD | `squash` | PR merge method wherever a skill merges its own PR. |
| SUPER_PROTECTED_MAIN | `true` | All changes go through a feature branch plus PR, even docs-only ones. |
| SUPER_ADMIN_MERGE | `false` | `gh pr merge --admin` is used only under explicit, session-scoped authorization. |
| SUPER_SKIP_FINISHING_HANDOFF | `false` | `true` bypasses `superpowers:finishing-a-development-branch`'s interactive menu; `superrun` integrates the code PR itself. |
| SUPER_GH_DISABLE_SANDBOX | `false` | `true` on hosts (e.g. macOS) where `gh` needs keychain access the tool sandbox blocks. |
| SUPER_REPO_NOTES | *(empty)* | Optional path to a repo doc the SDD executor reads before the task loop, treated as standing repo policy. |

## Other harnesses: Codex, Cursor, Pi

Each non-Claude build is generated from the canonical skills by a `scripts/build-<harness>-skills.sh`
script, driven by conditional markers in the skill files (single source of truth; `--check` verifies
the committed tree is fresh). All three ship the **external driver only**, with the Claude Code
in-session machinery stripped at build time. They use the same role keys as Claude Code.

### Codex (experimental)

**Install.** The repo (or a local clone) is itself the marketplace root via
`.agents/plugins/marketplace.json`, which points at the generated [`codex/`](codex/README.md) build.

```
codex plugin marketplace add blackterrarium/superagent-plugin   # or: <path-to-local-clone>
codex plugin add superagent@superagent
```

Skills load from the installed plugin under `~/.codex/plugins/cache/` in every workspace; there is
no per-invocation `--plugin-dir`. Bootstrap each target repo by asking a Codex session to run the
`init` skill (skill names are unprefixed on Codex).

**Auth and sandbox.** `OPENAI_API_KEY` in the target repo's `.env`, else the CLI's stored login
(`codex login`). Sandbox posture is `SUPER_CODEX_SANDBOX` (see the key table).

**Models and effort.** Native roles take Codex model names (e.g. `gpt-5.6-sol`) or `inherit`.
Effort is `none | minimal | low | medium | high | xhigh | inherit`. A native pin rides
`spawn_agent`'s `model` / `reasoning_effort` parameters; there is no agent-definition file. A
bridged role spawns a relay agent from `templates/relay-preamble.md`. Defaults map the Claude
`claude-opus-4-8` pins to `gpt-5.6-sol` and implementer/fix-applier to `gpt-5.6-terra`, with the
same efforts.

**Status: smoke-validated 8/8** (2026-08-12, codex CLI 0.147.0 on macOS): headless `codex exec`,
the marketplace install path, skill enumeration and model invocation from a neutral workspace,
bundled-template access, `spawn_agent` availability, the file-read tick entry with its hard gate,
and the effort override. Remaining gap: no end-to-end multi-tick loop has been driven to `DONE`
on Codex. Re-run with `bash scripts/codex-smoke.sh` from a clone.

### Cursor (experimental)

> **Unverified** as a bridge target and as a supervisor for bridged roles. See
> [Bridging a role to another harness](#bridging-a-role-to-another-harness).

**Install.** Via Cursor's marketplace flow (the root `.cursor-plugin/marketplace.json` points at
the generated [`cursor/`](cursor/README.md) build), or locally with `agent --plugin-dir <repo>/cursor`.

**Models and effort.** Native roles take a Cursor model name or `inherit`. The Cursor CLI has no
effort control, so every model and effort key ships as `inherit` by default. Bridged roles use the
same relay-definition mechanism as Claude when a key is set explicitly.

**Status: smoke-validated** (runs 1–2, 2026-08-12): headless `agent -p` with `--plugin-dir`, skill
enumeration and invocation from a neutral workspace, the tick entry point, and superpowers loading
under Cursor. Remaining gap: no end-to-end multi-tick loop has been driven to `DONE` on Cursor.
Re-run with `bash scripts/cursor-smoke.sh` from a clone.

### Pi (experimental)

**Install.** No install step for the plugin itself: the external driver passes
`--skill <repo>/pi/skills` on every headless run (or `pi install /path/to/superagent-plugin/pi` for
interactive use). Install superpowers as a Pi package and, recommended, `pi-subagents`:

```
npm install -g @earendil-works/pi-coding-agent
pi install git:github.com/obra/superpowers
pi install npm:pi-subagents        # >= 0.58.0, recommended
```

**Auth.** The CLI's `~/.pi/agent/auth.json`, or provider keys in the target repo's `.env`. Every
headless run passes `--approve` (the operator armed the loop on this repo).

**Models and effort.** Model keys are `pi:<provider>/<model>` or a bare `<provider>/<model>`.
Effort is `off | minimal | low | medium | high | xhigh | max`; the tick passes `--thinking`, the
bridge a `:<level>` model suffix. Defaults mirror the Codex build through the `openai-codex`
provider: `pi:openai-codex/gpt-5.6-sol` for supervisor, planner, executor, panel, reviewers, and
fix-planner; `pi:openai-codex/gpt-5.6-terra` for implementer and fix-applier.

**Dispatch is hybrid.** The supervisor never uses a subagent tool. `superplan` and `superrun` are
blocking bash calls to `scripts/role-bridge.sh` with `--tools planner` / `--tools executor`, and
the L7 panel is one blocking call to `scripts/bridge-fanout.sh` (three concurrent bridge runs,
1800 s timeout). `superrun`'s SDD children go through superpowers' Pi mapping (the `pi-subagents`
`subagent` tool with `async: false`), with pins in the `.pi/agents/super-<role>.md` definitions
`init` generates. Without `pi-subagents`, SDD runs sequentially in-context and pins are not
applied; `SUPER_PI_SUBAGENTS=required` makes init abort instead.

**Status: verified end-to-end** (2026-08-31, pi CLI 0.84.3, `pi-subagents` 0.61.0). Live smoke
PASS 10 / FAIL 1 (informational: pi exits 1 for both a bad model and a failed turn). A full loop
was driven to `DONE` in 4 manual ticks on a throwaway repo, including a pinned `pi-subagents`
implementer and two live codex task-reviewer relays. Remaining gap: `TICK_TIMEOUT` needs
`timeout` or `gtimeout` on `PATH`, else the driver WARNs and runs uncapped. Re-run with
`bash scripts/pi-smoke.sh` (`PI_SMOKE_MODEL=<provider>/<id>` to pin a model). The scheduler-fired
path is covered by `scripts/pi-e2e.sh`; see [`scripts/README.md`](scripts/README.md).

## Skill reference

Invoke every skill by its namespaced name on Claude Code (`superagent:<name>`). Names are
unprefixed on Codex, Cursor, and Pi.

| Skill | Purpose |
|---|---|
| `init` | Bootstrap a repo: prerequisite checks, `.superenv`, vault seed, gitignore entry, per-role agent definitions. Idempotent. |
| `supergoal` | Turn a goal description into a goal folder plus root master plan. |
| `superplan` | Author the next step's plan (sub-master or implementation leaf), route it, commit and merge via PR. |
| `superrun` | Execute the next ready leaf via `subagent-driven-development`, integrate the code PR, hand off to `superfinish`. |
| `superfinish` | Post-execution bookkeeping: findings, closeout report, ancestor rows flipped complete. |
| `superagent` | The autonomy supervisor. One dispatch per tick, via either driver. Never auto-triggers; invoke as `superagent:superagent <PLAN.md>`. |
| `superagent-external` | One-step launcher for an unattended loop. |
| `superagent-monitor` | Console across every concurrent loop on a host: status, answering, drain, hard-stop, uninstall, re-arm. |
| `superagent-stop` | Graceful (default) or hard stop for a healthy unattended loop. |
| `superagent-force-stop` | Recovery for a hung tick: halt, reap the stale lock, kick a recovery tick. |
| `superloop` | Shared clause library the supervisor is built on: loop-status file, drivers, overlap lock, context-handoff gate, sync gate, PR-merge discipline, escalation ladder. Not invoked directly. |
| `superauthor` | Shared plan-authoring library used by `supergoal` / `superplan`. Not invoked directly. |
| `supertraverse` | Shared plan-tree navigation used by `superplan` / `superrun` / `superfinish`. Not invoked directly. |

## Design notes

**Why `superrun` runs as its own process.** `superrun` is the SDD controller: it dispatches
implementer and reviewer subagents and must foreground-wait on each. A subagent cannot
foreground-wait on its own children (they background and yield), so dispatching `superrun` as an
Agent-tool subagent, the pre-0.5.1 design, decayed into a `SendMessage`-nudge spiral with two
writers racing on the worktree and ticks that never converged (issue #25). Since 0.5.1 the
supervisor starts `superrun` through `scripts/role-bridge.sh --tools executor` from its own Bash
tool: a fresh top-level `claude -p` (or the executor's harness CLI when bridged) with the executor
allowlist `Read,Edit,Write,Bash,Grep,Glob,Task,Skill`. Inside that process SDD's subagents are
depth 1 and the synchronous wait holds. A CI-pending yield ends the process; the resume tick starts
a fresh one with the recorded packet.

**Why `superplan` stays a subagent.** It spawns no subagents, so a depth-1 subagent is the right
container. A bridged planner's relay still shells out to `role-bridge.sh` with no `--tools` flag.
The `--tools planner` set is Pi-only: a Pi supervisor uses it because it dispatches `superplan` as
its own bridge process.

**Why the headless tick reads `SKILL.md` instead of invoking the skill.** A headless `claude -p`
session cannot run slash commands, and Skill-tool semantics for a `disable-model-invocation` skill
in headless print mode are unverified. So the tick prompt is a file read of the supervisor skill.
Internal dispatches from inside that session still use the `Skill` tool, which is why the plugin
must be enabled for headless sessions in the target repo.

**Why the tick always passes `--model`.** A headless tick has no session to inherit from, so it
pins the model explicitly and records it in the tick log. Defaults pin the full ID
`claude-opus-4-8`, not the `opus` alias, because the alias floats with the CLI.

## Migrating a repo with in-tree copies

If a repo already carries its own copies of these skills and driver scripts from before this plugin
existed, cut it over once the plugin covers the same behavior:

1. **Delete the in-repo copies**: its own `super{agent,agent-external,agent-monitor,agent-stop,
   agent-force-stop,loop,plan,run,goal,author,finish,traverse}/` skill directories and its driver
   scripts directory.
2. **Install the plugin** and run `superagent:init` in the repo.
3. **Edit the generated `.superenv`** to the repo's profile: goal-vault location, CI test-evidence
   mode and flag grammar, runner count, finishing-handoff behavior, `gh` sandbox posture, and so on.
   A repo migrating from an in-tree copy typically reuses its existing values.
4. **Update repo docs that name the old unscoped skills** (e.g. a root `CLAUDE.md`) to the
   namespaced `superagent:*` names.
5. **Re-run `install-timer.sh` on every host with a live timer for this repo**, from the plugin's
   script location, so future ticks resolve `superagent-tick.sh` there. The tick **interval** is
   not stored in `~/.config/superagent/<slug>.env`; it lives in the systemd timer drop-in or the
   launchd plist. Read it back from the prior install (`systemctl --user list-timers` or
   `status.sh`) and re-pass it with `--interval`, or the re-install silently falls back to
   `SUPER_TICK_INTERVAL` (shipped default `10m`; `30m` if the key is unset everywhere).

## License

This repository is private and ships no LICENSE by choice. The skills' `all rights reserved`
frontmatter is accurate; contact the owner before redistribution.
