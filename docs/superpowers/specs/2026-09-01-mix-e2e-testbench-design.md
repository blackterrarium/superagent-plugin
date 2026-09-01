# Multi-harness mixing e2e testbench — design

**Date:** 2026-09-01 · **Status:** approved by default (built autonomously on the operator's
request "build a testbench to test the multi-harness mixing feature … use the claude, codex and
pi harnesses"; review the *Decisions* section and reopen any you disagree with) · **Scope:** one
script, `scripts/mix-e2e.sh`, one instrumentation change in `scripts/role-bridge.sh`, offline
tests, docs.

## Problem

0.5.0 made every role key accept `[<harness>:]<model>` so a goal's work can be split across
harness CLIs: a role whose harness differs from `SUPER_HARNESS` is *bridged* through
`scripts/role-bridge.sh`. What exists to test it: `bridge-test.sh` (offline, shimmed CLIs),
`bridge-smoke.sh` (one relay round-trip per direction), and one hand-driven run on 2026-08-31 with
a codex reviewer inside a Pi loop. Nothing has ever run a goal to `DONE` with **three** harnesses
sharing the roles, unattended, with the scheduler firing the ticks — and nothing *proves* which
harness executed which role: a bridged pi or claude role leaves a **0-byte** log
(`role-bridge.sh` captures only the CLI's stderr), so the evidence today is the relay's word.

## Goal

A single command that, from an empty repository, drives a small but real goal through
`init → supergoal → external loop (launchd/systemd fires every tick) → DONE` with the supervisor on
Claude, the implementer on Codex and the task reviewer on Pi; asserts the deliverables; and
asserts — from artifacts, not from prose — that each pinned role ran on its pinned harness with
its pinned model. Plus an *evaluation* section in the report (ticks, minutes, PRs, bridge calls
per harness with durations, fix rounds, escalations) so the operator can judge the framework on an
actual goal, not on hello-world.

Non-goals (YAGNI): per-*task* harness routing (the plugin routes per **role**; that is the
feature under test), Cursor (no CLI on the host), a Pi or Codex *supervisor* with bridged roles
(`pi-e2e.sh` covers the Pi supervisor; a `MIX_E2E_SUPERENV_EXTRA` line can flip the mix),
WAITING FOR INPUT / CI parks, multi-goal concurrency.

## Design

### Command

```
scripts/mix-e2e.sh [--dry-run] [--keep]
  MIX_E2E_REPO=<owner>/<name>     remote to (re)use   (default: <gh user>/superagent-mix-e2e)
  MIX_E2E_INTERVAL=2m             scheduler interval
  MIX_E2E_MAX_MIN=150             wall-clock ceiling for the loop phase
  MIX_E2E_GOAL="…"                goal text (default: the kv-store goal below)
  MIX_E2E_IMPLEMENTER=codex:gpt-5.6-terra          role pins for the two mixed pairs
  MIX_E2E_REVIEWER=pi:openai-codex/gpt-5.6-sol
  MIX_E2E_SUPERENV_EXTRA="…"      extra .superenv lines (appended last; override anything)
```

Exit 0 only when every assertion holds. Report: `mix-e2e-report.md` at the repo root
(gitignored); per-run artifacts under `$TMPDIR/mix-e2e-<stamp>/` (tick log copy, event log,
status transitions, **the run's bridge logs**).

### The mix

```
SUPER_HARNESS=claude
SUPER_MODEL_IMPLEMENTER=$MIX_E2E_IMPLEMENTER      SUPER_MODEL_FIX_APPLIER=$MIX_E2E_IMPLEMENTER
SUPER_MODEL_TASK_REVIEWER=$MIX_E2E_REVIEWER       SUPER_MODEL_RE_REVIEWER=$MIX_E2E_REVIEWER
SUPER_TICK_INTERVAL=$MIX_E2E_INTERVAL
SUPER_NOTIFY_CMD='printf "%s\n" "$SUPERAGENT_EVENT" >>"<run-dir>/events.log"'
```

Every other key is the Claude build's default: supervisor, planner, executor (`superrun`),
branch reviewer, fix planner and panel are native Claude. Rationale: the implementer and the task
reviewer run on **every** SDD task, so with this mix every task is provably controlled by Claude,
written by Codex and reviewed by Pi; the fix-applier / re-reviewer share their sibling's harness so
a fix round does not change who is writing or judging. Pi on the build host authenticates through
the OpenAI Codex subscription (`~/.pi/agent/auth.json` has only `openai-codex`), so its model
strings are `openai-codex/<id>` — the README's `openai/gpt-5` example needs an API key this host
does not have. Efforts stay at the defaults (`medium` implementer → codex
`model_reasoning_effort=medium`; `high` reviewer → pi `…gpt-5.6-sol:high`).

### Default goal

> Add `scripts/kv.sh`, a POSIX-sh file-backed key-value store — `kv.sh set <key> <value>`,
> `kv.sh get <key>` (prints the value; exit 1 and nothing on stdout when absent), `kv.sh del <key>`,
> `kv.sh list` (every `key=value`, sorted by key, one per line); the store file is `$KV_FILE`
> (default `.kv` in the current directory); keys are `[A-Za-z0-9_-]+`, values are single lines;
> setting an existing key replaces its value — and `scripts/test.sh` (POSIX sh) that exercises all
> four commands against a temp store and exits non-zero on any mismatch. One implementation plan,
> two or three tasks; no files beyond the two scripts and the plan-tree bookkeeping.

Real enough to need more than one SDD task (so the mixed roles fire several times and a fix round
is plausible), small enough for one `superplan` + one `superrun`, and deterministic to assert:
`mix_assert_deliverables` runs set/get/replace/del/list/missing-key against a temp `KV_FILE` and
runs `scripts/test.sh`.

### Evidence: `role-bridge.sh` writes a header and a trailer

`role-bridge.sh` gains two lines in its own log file (nothing on stdout — the contract "stdout is
the CLI's final message and nothing else" is untouched):

```
role-bridge: start=20260901T120000Z harness=codex model=gpt-5.6-terra effort=medium tools=role role=implementer cwd=/…
… CLI stderr/chatter as before …
role-bridge: end=20260901T120742Z exit=0 secs=462 result_bytes=1834
```

`exit` is the bridge's exit code (0 · 3 CLI non-zero · 4 empty result). The header is written
before the CLI starts (a killed bridge leaves a header with no trailer — itself evidence). Both
lines are greppable and stable; `bridge-test.sh` pins their shape.

The testbench snapshots `T0` before phase 1 and, in phase 6, collects every
`$TMPDIR/superagent-bridge/*.log` whose header `start=` is ≥ `T0`, parses the header/trailer into a
table `role harness model effort exit secs`, copies the logs into the run dir, and asserts:

- ≥1 row `implementer codex <MIX_E2E_IMPLEMENTER's model> … exit=0`
- ≥1 row `task-reviewer pi <MIX_E2E_REVIEWER's model> … exit=0`
- ≥1 row `executor claude … exit=0` (the executor is always a bridge process, issue #25)
- no row for `implementer|fix-applier|task-reviewer|re-reviewer` with a harness other than the
  pinned one (a relay that answered itself instead of bridging leaves *no* row — caught by the
  first two bullets — but a wrong-harness row is a routing bug)
- the tick log contains no `BRIDGE-FAILED`

Corroboration, not asserted: a codex log also carries codex's own `model: gpt-5.6-terra` header;
the claude tick log (stream-json) shows the `super-implementer` / `super-task-reviewer` Agent
dispatches.

### Phases

Same skeleton, framing and trap discipline as `pi-e2e.sh` (whose pure helpers this script sources
with `PI_E2E_LIB=1`): report sections with fenced command output and a `**Result: PASS|FAIL**`
line, the first FAIL aborts after cleanup, long children run via `e2e_run` (`cmd & wait`) so
SIGINT/SIGTERM reach the handler.

0. **Preflight** — `claude`, `codex`, `pi`, `gh` (authenticated), `git`, `python3`, the
   scheduler; `pi --list-models` lists `openai-codex` (else the reviewer pin cannot work);
   `codex login status` ok (WARN only if the subcommand is unknown); the `superagent` plugin is
   installed **and enabled** in the local `claude` (`claude plugin list`) — the claude tick's
   in-session `superagent:superplan` / `superrun` dispatches resolve through the *installed*
   plugin, while the scripts run from this checkout — and its version is recorded next to the
   repo's `plugin.json` version with a WARN when they differ; `build-*-skills.sh --check` clean; no
   loop registered under the run's slug. `--dry-run` stops here.
1. **Provision** — as `pi-e2e.sh` (reused remote, orphan reset, stale branches/PRs cleared) with
   the mix `.superenv` above.
2. **Init** — `claude -p` (prompt on **stdin** — `--allowedTools` is variadic and swallows a
   positional prompt), allowlist `Read,Edit,Write,Bash,Grep,Glob,Skill,Task`, model `opus`:
   "Use the Skill tool to invoke `superagent:init` and run it to completion, unattended…".
   Assert `.superenv` intact; `.claude/agents/super-implementer.md` exists, carries the
   `generated-by: superagent:init` marker and `--harness codex`; `.claude/agents/super-task-reviewer.md`
   likewise with `--harness pi`; `.claude/agents/super-executor.md` is *not* required (the executor is
   a bridge process, not an agent definition); `vault/` exists. Commit + push leftovers.
3. **Goal** — `supergoal` as two `claude -p` turns in one session (`--session-id <uuid>`, then
   `--resume <uuid>`): the goal, then the scripted operator's "yes" at its §7 confirmation gate.
   Assert exactly one `vault/*/master-plans/*.md` on `main` and ≥1 merged PR.
4. **Arm** — `launch.sh <PLAN.md> --harness claude --interval … --slug mix-e2e-<stamp>`. Assert
   `timer_active`, the loop file, the env file's `SUPER_HARNESS=claude` and `SUPERAGENT_CLI_PATH`
   (pi lives under nvm on the host — the codex/pi bridges from a launchd tick depend on it).
5. **Drive** — watch only (`status.sh --json` every 30 s); DONE → PASS, a park or the ceiling →
   FAIL.
6. **Assert** — ≥2 ticks; deliverables; ≥3 merged / 0 open PRs; self-disarm; `done` event; **the
   evidence table and its assertions above**.
7. **Evaluate** (report-only, never fails) — ticks, elapsed minutes, merged PRs, bridge calls per
   harness (count / total secs / max secs), fix-applier and re-reviewer counts (= fix rounds),
   panelist rows (= L7 escalations), loop-file iteration count, tail of the loop file's log.
8. **Cleanup** (trap, always) — as `pi-e2e.sh`, plus copying the run's bridge logs into the run dir.

### Testing the testbench

Offline in `bridge-test.sh`: the bridge header/trailer for each harness (shape, `exit=3`/`4` on
the fail/empty shims, header-without-trailer on kill); `MIX_E2E_LIB=1` sources the script and
exposes `mix_render_superenv`, `mix_assert_deliverables` (a reference `kv.sh` under `$T` passes,
a broken one fails), `mix_bridge_evidence` (a fixture dir of logs → the table; old logs excluded;
header-only log → `exit=killed`), `mix_evidence_has`; `--dry-run` under shims. The live run is the
integration test; its result is recorded in `scripts/README.md`.

## Decisions (assumptions the operator can override)

1. **Claude is the supervisor.** It is the primary harness and the only one whose bridged-role
   path (relay agent definitions) is the documented design; `SUPER_MODEL_SUPERVISOR` cannot be
   bridged anyway. Other supervisors: `MIX_E2E_SUPERENV_EXTRA`.
2. **codex = writer, pi = judge** (not the reverse). Codex's `gpt-5.6-terra` is the plugin's own
   Codex-build default for implementer/fix-applier; pi carries `:high` thinking naturally on the
   reviewer. Swappable via `MIX_E2E_IMPLEMENTER` / `MIX_E2E_REVIEWER`.
3. **Instrument the bridge** rather than infer the harness from CLI chatter — pi and claude print
   nothing to stderr on success; a header is the only honest evidence and costs two lines.
4. **A real goal, not hello-world** — the operator asked to evaluate superagent "in building an
   actual supergoal". The kv store is the smallest goal with real branching logic and several tasks.
   Ceiling 150 min (the Pi hello-world took 61 min in 4 ticks).
5. **Version mismatch between the installed plugin and the checkout is a WARN, not a FAIL** — the
   skills exercised in-session come from the installed plugin, the scripts from the checkout; a
   report that records both versions is more useful than a refusal. Missing/disabled plugin is a
   FAIL.
6. **Per-role, not per-task, mixing** is what is tested — the plugin has no per-task routing, and
   the testbench does not pretend otherwise.
7. Same as `pi-e2e.sh`: one reused remote reset per run; the scheduler fires the ticks; python3
   for JSON; a WAITING FOR INPUT park is a FAIL.

## Error handling

- Preflight miss → exit 2, nothing created. Remote ops idempotent. Any phase FAIL → cleanup
  (stop a running tick, uninstall the timer, purge the env file), report written, exit 1.
- The evidence phase tolerates a header without trailer (`exit=killed`) and a log dir that does
  not exist (→ empty table → the assertions fail with "no bridge logs since T0", which is the
  right verdict).
- `SIGINT`/`SIGTERM` → kill the running child's tree, mark the report FAIL, cleanup, exit 130/143.
