# Changelog

## 0.6.5 — 2026-09-01

- **`scripts/mix-e2e.sh` — scripted end-to-end testbench for multi-harness role mixing.** From an
  empty repository: `init` → `supergoal` → `launch.sh` arms the real scheduler → scheduler-fired
  ticks → `DONE`, with the roles split across three harness CLIs — supervisor / planner / executor
  on **Claude**, implementer + fix-applier bridged to **Codex** (`codex:gpt-5.6-terra`),
  task-reviewer + re-reviewer bridged to **Pi** (`pi:openai-codex/gpt-5.6-sol`; Pi on the build host
  is OpenAI-only). The goal is a real one (a POSIX-sh key-value store with tests, 2–3 SDD tasks) so the
  mixed roles fire several times. Besides the `pi-e2e.sh` assertions (≥2 ticks, deliverables, PRs,
  self-disarm, notify) it asserts **harness evidence**: from `role-bridge.sh`'s log header/trailer
  lines, ≥1 successful `implementer` on codex with the pinned model, ≥1 `task-reviewer` on pi, ≥1
  `executor` on claude, no pinned role on a foreign harness, no `BRIDGE-FAILED`. A report-only
  *Evaluation* section tallies ticks, minutes, PRs, bridge calls per harness (count / secs), fix
  rounds and L7 escalations. Knobs: `MIX_E2E_REPO`, `MIX_E2E_INTERVAL`, `MIX_E2E_MAX_MIN`,
  `MIX_E2E_GOAL`, `MIX_E2E_IMPLEMENTER`, `MIX_E2E_REVIEWER`, `MIX_E2E_SUPERENV_EXTRA`; `--dry-run`,
  `--keep`. Preflight also requires the superagent plugin to be installed and enabled in the local
  `claude` (the claude tick's in-session skill dispatches resolve through the installed plugin) and
  WARNs when its version differs from the checkout. Pure helpers unit-tested offline in
  `bridge-test.sh`. Design: `docs/superpowers/specs/2026-09-01-mix-e2e-testbench-design.md`.
  **Result on the build host:** run 4 — **PASS 7/7, exit 0, 73 min**: 4 scheduler-fired ticks to
  `DONE`, 4 merged PRs, 8 bridge calls all exit 0 (claude executor ×2 · codex implementer ×2 +
  fix-applier · pi task-reviewer ×2 + re-reviewer), one fix round, no strays. Runs 1–3 each caught a
  real defect (see the fix entries below); run 3 additionally exercised the L7 panel + re-plan cycle
  live on a seed-level design gap the branch reviewer found.
- **Fix (found by the testbench): the Claude relay template fought Claude Code's worktree isolation.**
  `templates/super-role-bridge-agent.md` step 1 (`mktemp "${TMPDIR:-/tmp}/…"` + heredoc) was refused in
  every relay of the live run ("too complex to verify that it stays inside the worktree"), costing each
  relay 1–3 improvised turns (the fix-applier ~10). The relay now writes `.superpowers/relay/<role>.prompt`
  inside its cwd with relative paths and removes it after the bridge returns. Re-run `superagent:init`
  to regenerate `.claude/agents/super-*.md`.
- **Observed (found by the testbench): relays run the INSTALLED plugin's `role-bridge.sh`.** The relay
  definition says `"${SUPERAGENT_BRIDGE:-<bridge-path>}"` but the relay types the baked path literally,
  so the `SUPERAGENT_BRIDGE` export from the tick does not redirect them. `mix-e2e.sh` therefore
  requires the installed bridge to carry the evidence header (preflight, exit 2 with the fix) and shows
  header-less logs as `legacy` rows.
- **Calibration (found by run 3): default loop ceiling 150 → 240 min.** Run 3's branch reviewer found a
  real seed-level design gap (an unguarded rewrite failure could silently promote a short temp file over
  the store), the L7 panel adopted a re-plan, and the loop executed a second implementation plan — a
  legitimate escalation cycle that was still 1–2 exhaustion ticks from `DONE` when the 150-min ceiling
  aborted the run. The ceiling must fit the escalation path; it costs nothing when the loop finishes early.
- **Fix (found by run 2): `grep -c … || echo 0` prints two zeros.** `grep -c` PRINTS `0` *and* exits 1
  on zero matches, so `mix_bridge_failed_count` returned `"0\n0"` and aborted the evidence phase of an
  otherwise-clean run. Regression case in `bridge-test.sh`.
- **Fix: `role-bridge.sh --harness cursor` no longer inherits stdin.** The prompt rides argv, so an open
  stdin only made the CLI (and `bridge-test.sh`'s cursor shim) wait on it forever — the parked 0.5.0
  follow-up; the bridge now passes `</dev/null`.
- **`scripts/role-bridge.sh` writes a header and a trailer into its own log.** A bridged pi or claude
  role used to leave a 0-byte log (only the CLI's stderr was captured), so nothing proved which
  harness had run a role. The log now starts with `role-bridge: start=<utc> harness=… model=… effort=…
  tools=… role=… cwd=…` and ends with `role-bridge: end=<utc> exit=<0|3|4> secs=<n> result_bytes=<n>`
  (no trailer = killed mid-run). stdout is unchanged. Offline cases in `bridge-test.sh`; the
  `codex/`, `pi/`, `cursor/` trees (which ship the bridge) are rebuilt.

## 0.6.4 — 2026-09-01

- **`scripts/pi-e2e.sh` — scripted Pi end-to-end testbench.** From an empty repository: `init` →
  `supergoal` → `launch.sh` arms the real scheduler (launchd / systemd user timer) → the scheduler
  fires every tick → `DONE`; then asserts ≥2 ticks (so at least one fired on the interval), the goal's
  deliverables, ≥3 merged / 0 open PRs, `SUPER_AUTO_DISARM_ON_DONE`, and the `done` event through
  `SUPER_NOTIFY_CMD`; cleans up via a trap; writes `pi-e2e-report.md` (gitignored). The remote
  (`PI_E2E_REPO`, default `<gh user>/superagent-pi-e2e`) is reset to an orphan commit per run and
  never deleted. Knobs: `PI_E2E_INTERVAL`, `PI_E2E_MAX_MIN`, `PI_E2E_GOAL`, `PI_E2E_SUPERENV_EXTRA`;
  `--dry-run`, `--keep`. `supergoal` runs as two turns in one persistent Pi session (its confirmation
  gate is by design; the second turn is the scripted operator's "yes"). Pure helpers unit-tested offline
  in `bridge-test.sh`. Design: `docs/superpowers/specs/2026-09-01-pi-e2e-testbench-design.md`.
  **Result on the build host:** run 6 PASS 6/6 — `DONE` in 4 launchd-fired ticks, 61 min; run 5 had
  already reached `DONE` in 5 ticks and additionally exercised the L7 panel live. This closes the
  "scheduler path never exercised on Pi" gap.
- **Fix (found by the testbench): `load_superenv` ignored the harness when choosing its default layer.**
  It always sourced `templates/superenv.default` (the Claude defaults) next to the running `_common.sh`,
  so a repo whose `.superenv` said only `SUPER_HARNESS=pi` inherited `SUPER_MODEL_SUPERVISOR=claude:opus`
  and every tick exited 11 ("the supervisor cannot be bridged"). The harness build's own template
  (`pi/`, `cursor/`, `codex/plugins/superagent/`) now layers over the Claude one — resolved from the
  process env, else the repo's `.superenv` — and the repo's `.superenv` still overrides both. Offline
  cases in `bridge-test.sh`.
- **Fix (found by the testbench): `role-bridge.sh --harness inherit` was rejected (exit 64).** A
  `SUPER_MODEL_*` of `inherit` resolves to harness `inherit` via `superagent_role_harness`; the
  supervisor is told to map that to `SUPER_HARNESS` but passed the literal through, and superplan's
  dispatch failed on both attempts (one lost tick). The bridge now resolves `inherit`/empty to
  `SUPER_HARNESS` (default `claude`) itself. Offline cases in `bridge-test.sh`.
- **Fix (found by the testbench): `launch.sh` / `stop.sh` / `force-stop.sh` rejected a plan in a repo
  reached through a symlinked path** (macOS `/var` → `/private/var`, `/tmp` → `/private/tmp`): `REPO`
  comes from `git rev-parse --show-toplevel` (physical) while the plan path was resolved with a logical
  `pwd`, so the "plan must live inside the repo checkout" check failed. All plan/loop-file resolutions
  now use `pwd -P` (`install-timer.sh` too, for consistency). Offline case in `bridge-test.sh`.

## 0.6.3 — 2026-09-01

- **Fix: external ticks could not find a CLI installed under a Node version manager.** The
  scheduler (launchd / systemd user service / cron) runs the tick with a minimal `PATH`, and the
  tick's preflight only prepended `~/.local/bin`, `/opt/homebrew/bin`, `/usr/local/bin` — so a `pi`
  (or any CLI) living under nvm/fnm/volta, e.g. `~/.nvm/versions/node/<v>/bin/pi`, failed with exit
  127 before any session started. This is why the Pi harness's scheduler path was still listed as a
  known gap. `install-timer.sh` now records the directories of every agent CLI resolvable in the
  arming shell as `SUPERAGENT_CLI_PATH` in the per-goal env file (new `_common.sh` helper
  `superagent_cli_path_dirs`; every CLI, not only the harness's, since bridged roles run foreign CLIs
  from the same tick), and `_superagent_augment_path` prepends them once. The `ensure_*_bin` messages
  name the mechanism. **Loops armed before 0.6.3 have no `SUPERAGENT_CLI_PATH` line — re-arm them
  from a normal shell to pick it up.** Tests: 5 offline cases in `bridge-test.sh`; `pi-smoke.sh` T7
  runs the preflight plus the real `pi` under `env -i PATH=/usr/bin:/bin`.

## 0.6.2 — 2026-09-01

- **`pi-smoke.sh` T6 — strict YAML frontmatter check (offline).** Every `SKILL.md` in `skills/` and
  `pi/skills/` is parsed with the `yaml` library the pi binary itself bundles (resolved from the
  binary's own `node_modules`), so a frontmatter that Claude Code's lenient parser accepts but Pi
  rejects (the 0.6.1 `argument-hint` bug) fails the smoke instead of surfacing as
  `[Skill conflicts]` at Pi load time. Verified red on the pre-0.6.1 file, green now
  (`27 frontmatter OK`); full smoke PASS 11 / FAIL 1 (P1, informational).

## 0.6.1 — 2026-09-01

- **Fix: `superagent` skill frontmatter failed strict YAML parsing on Pi.** `skills/superagent/SKILL.md`
  had an unquoted `argument-hint` containing `(or: --tick …)`; the `: ` inside a plain scalar reads as a
  nested mapping, so Pi's `yaml` parser rejected the file (`Nested mappings are not allowed in compact
  mappings at line 3, column 16`) and reported it under `[Skill conflicts]`. Claude Code's lenient parser
  masked it. The value is now quoted like every other skill's hint; the generated `pi/`, `codex/`, and
  `cursor/` trees are rebuilt.

## 0.6.0 — 2026-08-30

- **Pi harness (`SUPER_HARNESS=pi`).** The Pi CLI can drive the external loop: `superagent-tick.sh`
  fires `pi -p --approve --skill <repo>/pi/skills [--model] [--thinking] [--mode json]`
  (new generated `pi/` build, `scripts/build-pi-skills.sh`, `pi-only` markers). Hybrid dispatch:
  the supervisor runs `superplan`/`superrun` through `role-bridge.sh` and the L7 panel through
  the new `scripts/bridge-fanout.sh` (child CLI processes — the supervisor never uses a subagent
  tool); superrun's SDD roles dispatch through the `pi-subagents` `subagent` tool (`async: false`)
  with pins on `init`-generated `.pi/agents/super-<role>.md` definitions
  (`templates/super-role-pi-agent.md`, `templates/super-role-pi-bridge-agent.md`).
  `pi-subagents` is recommended, not required — new key `SUPER_PI_SUBAGENTS=recommended|required|off`;
  floor `>=0.58.0`, verified against 0.59.0.
- `role-bridge.sh` pi branch: `--tools role|planner|executor` sets (`planner` is new on every
  harness), `--approve --no-session`, `--skill` from `SUPERAGENT_PI_SKILLS`, `--thinking` when the
  model is `inherit` (the 0.5.0 "effort dropped" warning is gone).
- Pi effort domain widened to `off|minimal|low|medium|high|xhigh|max` everywhere.
- Tick exit 8 now also covers a malformed Pi supervisor model; new exports `SUPERAGENT_FANOUT`,
  `SUPERAGENT_PI_SKILLS`.
- **Update (2026-08-31): fully verified.** With `pi-subagents` 0.61.0 and superpowers installed as
  Pi packages, the smoke is PASS 10 / FAIL 1 (P1 informational): P3a, **P3c (nested foreground
  wait)**, T4 (pi→codex relay round trip) and P4b all PASS. A live loop ran to **`DONE`** in 4
  manual ticks on a throwaway repo (init → supergoal → superplan tick → superrun tick with the
  pinned `pi-subagents` implementer and two codex relay reviews, code + closeout PRs merged →
  plan-exhausted → DONE + notification). Also fixed: `TICK_TIMEOUT` now falls back to `gtimeout`
  and otherwise WARNs and runs uncapped (macOS has no `timeout`; the unconditional wrapper made
  any capped tick/bootstrap exit 127).
- Tests: `bridge-test.sh` (fan-out + pi flags), `pi-smoke.sh` (P1–P4, T1–T5). Smoke result (live
  run, 2026-08-29, pi CLI 0.84.3, `pi-subagents` NOT installed on the build host): PASS 7 / FAIL 1
  (informational) / SKIPPED 3. P1 (bad-model exit status) is FAIL-as-expected with **exit 1** — pi
  collapses a bad model and a failed turn into the same plain `1`, no distinct exit code, which is
  the datum `role-bridge.sh`'s exit-3 mapping relies on. P2 (`--skill` delivery) PASSES. P4a
  (tool-list probe, informational) PASSES; P4b is **inconclusive** (no extension tools were
  installed on the smoke host, so the probe never exercised the case it's meant to check).
  T1/T2/T3/T5 (bridge → pi, bridge-fanout ×3, tick
  file-read + hard gate, `build-pi-skills.sh --check`) all PASS. P3a/P3c (`pi-subagents` probes)
  and T4 (relay round trip) are **SKIPPED** — `pi-subagents` was not installed on this host, so the
  nested-wait behavior (P3c) is **not verified**; re-run `scripts/pi-smoke.sh` on a host with
  `pi-subagents ≥0.58.0` before promoting the pinned-subagent path further.

## 0.5.2 — 2026-08-29

- **`templates/superenv.default` now spells every `SUPER_MODEL_<ROLE>` value in the 0.5.0
  `[<harness>:]<model>` grammar** (`claude:opus`, `claude:sonnet`; the Codex build emits
  `codex:gpt-5.6-sol` / `codex:gpt-5.6-terra`, the Cursor build keeps `inherit`). Behaviour is
  unchanged — the bare tiers already resolved to `claude` — but the shipped defaults now show the
  form a mixed-harness `.superenv` uses. `SUPER_BRIDGE_RELAY_MODEL` stays a bare native model name
  (the relay always runs on `SUPER_HARNESS`; the value is written verbatim into the relay agent's
  `model:` line). `build-codex-skills.sh` / `build-cursor-skills.sh` match the prefixed values.

## 0.5.1 — 2026-08-29

- **Fix #25 — `superrun` delegate-and-wait spiral under the headless tick driver.** `superrun` is the
  `subagent-driven-development` controller and must foreground-wait on its own implementer/reviewer
  subagents; dispatched as an Agent-tool subagent (depth 1), its children ran at depth 2, where the
  synchronous wait does not hold — they backgrounded and yielded, and the tick decayed into a
  `SendMessage`-nudge spiral (~18 nudges), a two-writer worktree race (a late child amended `HEAD`
  after the checkpoint) and non-convergence. The supervisor now starts `superrun` as the **top-level
  agent of its own CLI process** via `scripts/role-bridge.sh --tools executor` from its own Bash
  tool (foreground, `timeout: 7200000`) and blocks on it as before; inside that process SDD's
  subagents are depth 1 and the wait holds. Native and bridged executors take the same path
  (`SUPER_MODEL_EXECUTOR` passes to the CLI directly — a full `claude-*` ID no longer needs the
  `super-executor` agent definition). `superplan` is unchanged.
- `role-bridge.sh`: new `--tools role|executor|<list>` (claude only; ignored elsewhere) selecting the
  `--allowedTools` set; the claude branch now lifts the print-mode background-wait ceiling for the
  child (`CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS` defaults to 0, operator value kept), mirroring the tick.
- CI park/resume: the `ci_wait.subagent` field and the in-session `SendMessage` resume are gone — a
  CI-PENDING yield ends the executor process; the resume tick starts a fresh one with the packet.
- `superrun`: refuses (BLOCKED) if it finds itself an Agent-tool subagent; falls back to
  `git worktree remove` when `ExitWorktree` is not in the process allowlist.
- Supervisor preflight: the `superrun` dispatch requires `BASH_MAX_TIMEOUT_MS ≥ 7200000` in the
  session environment (exported by `superagent-tick.sh`; an attended `cron` session must launch with
  `BASH_DEFAULT_TIMEOUT_MS=3600000 BASH_MAX_TIMEOUT_MS=7200000 claude`) — otherwise the tick resets to
  `WAITING FOR RUN` and reports the missing variable instead of guillotining a half-done leaf.

**Upgrade note.** Armed external loops pick this up on their next tick (the tick re-reads the plugin
skills); nothing to re-arm. `cron`-driver sessions must be relaunched with the two `BASH_*` variables
above.

## 0.5.0 — 2026-08-29

- **Cross-harness role mixing.** Role keys accept `[<harness>:]<model>` (`claude|codex|cursor|pi`); a
  role naming a harness other than `SUPER_HARNESS` is *bridged*: dispatched through the existing
  per-role subagent hook, executed by that harness's CLI via new `scripts/role-bridge.sh`, result
  returned verbatim. Relay definitions (`templates/super-role-bridge-agent.md`) are generated by
  `superagent:init` on Claude/Cursor; Codex spawns a relay from `templates/relay-preamble.md`.
  New key `SUPER_BRIDGE_RELAY_MODEL`. Effort keys validate in the role's harness domain (pi:
  `off|minimal|low|medium|high`). `SUPER_MODEL_SUPERVISOR` must stay native (tick exit 11).
- `SUPER_BRIDGE_RELAY_MODEL` defaults to `sonnet` on the Claude build (Codex/Cursor builds: `inherit`)
  — a live smoke run measured a `haiku` relay subagent short-circuit: it answered the bridged prompt
  itself instead of shelling out to `role-bridge.sh`, silently inventing an answer. `haiku` must never
  be used for this key.
- Tests: `scripts/bridge-test.sh` (offline shims), `scripts/bridge-smoke.sh` (live T1–T7).
- Pi as a *supervisor* harness is not included — see the spec's follow-up note.

**Upgrade note.** A repo initialised with an earlier pre-release build of this branch may carry
`SUPER_BRIDGE_RELAY_MODEL=haiku` in its `.superenv` and haiku-pinned `.claude/agents/super-*.md`
relay definitions from that init run — set `SUPER_BRIDGE_RELAY_MODEL=sonnet` in `.superenv` and
re-run `superagent:init` to regenerate the relay definitions. The Codex and Cursor builds default
the relay to `inherit` (the CLI's own default subagent model) rather than pinning a tier, since
Claude tier names don't apply there; if a bridged role on those builds ever returns a plausible
answer with no corresponding `role-bridge.sh` log file, that is the same short-circuit under a
different default — pin `SUPER_BRIDGE_RELAY_MODEL` to a mid-tier model explicitly on that build.

**Audit your role keys before upgrading the Codex and Cursor builds.** A *leaked* Claude value on
those builds — e.g. `SUPER_MODEL_PLANNER=sonnet` left behind in a hand-trimmed `.superenv` — used to
be out-of-domain: it WARNed and fell back to `inherit`. It is now a well-formed role value naming the
`claude` harness, so the role becomes **bridged** and really runs the `claude` CLI: real spend on
another provider, or (when `claude` is not installed on the host) a hard `superagent:init` ABORT on
the missing-binary check. Grep every `SUPER_MODEL_*` / `SUPER_EFFORT_*` key in the repo's `.superenv`
and set the ones you meant to be native back to `inherit` or to a native model name.

## 0.4.10 — 2026-08-28

- **`WAITING FOR CI` staleness escape (`SUPER_CI_MAX_WAIT_MIN`, default 180).** A run stuck in
  `queued`/`waiting` used to park the loop silently forever under the 0.4.9 gate. The wrapper now
  compares `ci_wait.since` (ISO-8601 UTC) against the limit whenever runs are still not `completed`:
  past it, one `ci-stale` notification (`SUPER_NOTIFY_CMD` / desktop; once per `since` value via a
  `.<loop>.ci-stale` marker next to the loop file) and the gate falls open so the session runs each
  interval and can re-park or cancel. `0` disables; an absent/unparseable `since` keeps gating.
- **`ci_wait.repo`:** the skill now records the PR base repository (`owner/name`) at parking and the
  wrapper passes it as `gh run view --repo`, so the gate engages on forks/ambiguous remotes instead of
  silently failing open. Malformed values are ignored (logged) and the old remote-derived behaviour is
  kept.
- **Shared owner-liveness helper** `superagent_lock_owner_state <lockdir>` (`alive <pid>` /
  `dead <pid>` / `malformed` / `none`) in `_common.sh`; `answer.sh`'s dead-owner reap and the tick's
  peer-shield check use it instead of two hand-rolled `kill -0` sites. Also `superagent_ci_field` and
  `superagent_epoch_from_iso` helpers.
- **`status.sh` drill-in:** the `## Pending decision` block now stops at the next `## ` heading instead
  of spilling into `## Iteration log` when `## Decisions` is absent.

## 0.4.9 — 2026-08-28

- **`WAITING FOR CI` is now a free park (`SUPER_CI_GATE=true`).** The other parked state still
  launched a full CLI session per interval whose only job was one status query. `superagent-tick.sh`
  now parses `ci_wait.runs` from the loop-file frontmatter (`superagent_ci_runs`; inline
  `runs: [id, id]` or a `- id` list) and runs `gh run view <id> --json status` for each after the gh
  preflight; any run not `completed` → one log line, exit 0, no session. Fail-open: unparseable ids
  or a `gh` error fall through to the session (the old behaviour) — the gate can never strand a loop.
  The skill now prescribes the inline-list form as canonical.
- **`answer.sh`:** releases the lock *before* kicking on the "answer already recorded" path (the
  kicked tick used to find the lock held and exit, costing an interval); reaps a lock whose `owner`
  PID is dead (superloop L3) instead of refusing forever; a malformed or absent `owner` is treated as
  a live lock and still refuses (exit 4).
- **`status.sh`:** `INPUT` column is `YES` (parked, needs you) / `ans` (answer recorded, next fire
  resumes) / `-`; JSON gains `answer_recorded`; drill-in prints the recorded answer. JSON
  `pending_input` stays `0|1` and now means *parked and unanswered*; `answer_recorded` carries the
  second bit.
- `scripts/README.md`: the `.superenv` paragraph cites `templates/superenv.default` instead of stale
  key-count/default values.

## 0.4.8 — 2026-08-28

- **A loop parked on `WAITING FOR INPUT` no longer burns a paid session per interval.** The
  wrapper had no pre-screen for the parked state, so every scheduler fire launched a full CLI session
  that read the file, found no answer, and exited — the DONE-polling waste of #18, still open for the
  parked state. Three additive driver changes (no skill-logic or scheduler change):
  - **Bash gate (`SUPER_INPUT_GATE=true`).** `superagent-tick.sh` reads the loop file before any
    preflight; `WAITING FOR INPUT` with no `answer:` under `## Pending decision` → one log line,
    exit 0, no session. Polling continues for free; resume-on-answer is unchanged.
  - **One notification per unseen park (`SUPER_NOTIFY_CMD`).** The wrapper snapshots `status` **and
    the `## Pending decision` block** before the session and fires `superagent_notify
    waiting-for-input` (body = the pending question) when the tick leaves the loop parked on a
    question the operator has not been shown: a status transition into `WAITING FOR INPUT`, **or a
    changed pending block while already parked** — the re-park case, where a tick consumes `answer:`
    and immediately parks on a *new* question, so status is `WAITING FOR INPUT` on both sides and a
    status-only guard would stay silent while the gate suppressed every later session (a silently
    stranded loop). `done` fires on the status transition alone. Your snippet runs via `bash -c` with
    `SUPERAGENT_EVENT/SLUG/TITLE/BODY` + `LOOP_FILE` in env (ntfy/Slack/Pushover…) — **single-quote
    it in `.superenv`**, which is sourced under `set -euo pipefail`; unset → `osascript` (macOS) /
    `notify-send` (Linux) when available. A failing notifier is logged (and logs no "notified" line)
    and never fails the tick. Still no sidecar state: an unchanged parked loop is silent, and a gated
    fire exits before the check.
  - **`scripts/answer.sh [--no-kick] [--replace] <slug> <answer…>`.** Records `answer: <text>`
    directly under `## Pending decision` holding the L3 lock (refuses with exit 4 while a tick is
    mid-flight, 3 if the loop isn't parked — both re-checked *under* the lock), then kicks one tick
    via the registered scheduler entry so the loop resumes in seconds. Both flags parse in **any
    position**, so `answer.sh g "Option A" --no-kick` honors the flag instead of recording it as part
    of the answer, and an unknown `--flag` is a usage error (exit 2) rather than answer text;
    `--replace` overwrites an answer already recorded in the block (without it the existing answer is
    kept and only kicked). Kick logic lifted into `_common.sh` (`superagent_kick_tick`) and shared
    with `launch.sh`. `superagent-monitor` now recommends it as the primary answer path.
  - New `_common.sh` readers `superagent_loop_status` / `superagent_pending_section` /
    `superagent_pending_answer` (answer detection is scoped to the pending section — an `answer:`
    under `## Decisions` never counts).
  - All new helpers tolerate empty arguments (`${1:-}`, never `${1:?}` — which would abort the
    calling tick); `answer.sh` passes the answer through `ENVIRON` (backslash-safe), checks for the
    heading before taking the lock, arms its release traps *before* writing the lock's `owner` file
    (a kill in that window used to strand an ownerless lock until the 90-minute steal window), and
    traps TERM/INT so a signal never leaks the lock.
  - Follow-ups (not here): a `WAITING FOR CI` bash gate; event-driven wake via launchd
    `WatchPaths` / a systemd `.path` unit.

## 0.4.7 — 2026-08-19

- **Fix #17: a headless tick could end its turn by asking the operator a question, exit 0 as
  success, and strand `status: RUNNING` + the held lock.** A dispatch interrupted mid-flight (host
  sleep, API loss) had no prescribed path in the skills: the tick prompt only forbade the
  `AskQuestion`/`AskUserQuestion` *tools*, so the agent lawfully ended the turn with a plain-text
  chat question no headless session can answer — a well-formed `success` completion that did no
  work, burned a full dispatch, and left the loop advertising `RUNNING` with no tick in flight.
  - **Tick teardown invariant (superloop L2).** A tick now has exactly four legal terminal shapes —
    advanced, parked (`WAITING FOR CI` / `WAITING FOR INPUT` + pending-decision block), clean no-op,
    or interrupted-and-restored — and in every one the persisted `status` is non-transient and the
    lock is released. Ending a tick with a question is never legal in **any** form (tool or final
    chat message); the only user-decision channel is L7 Rung 2's durable `## Pending decision` +
    `WAITING FOR INPUT` machinery.
  - **Interrupted dispatch → self-heal now, don't ask.** The prescribed response to a mid-flight
    interruption is what the next tick's crash recovery would do, applied immediately: log the
    interruption, map the transient status back to its ready state (`PLANNING → WAITING FOR PLAN`,
    `RUNNING → WAITING FOR RUN`), release the lock, end with a normal report. The next scheduled
    tick retries — retry is the standing answer; only a genuine L7 decision point parks the loop.
  - **Wrapper enforcement — `exit=0` means "advanced or parked".** After the session ends,
    `superagent-tick.sh` re-flags a `0`-exit session that left a transient `status` as a loud
    failed tick (new exit 10 + explicit `ERROR` log line), so monitoring sees the burned tick
    instead of a healthy-looking no-op. All harnesses; the L3 lock reap (0.4.5 EXIT trap) still
    runs, so the loop self-heals on the very next tick instead of waiting out the steal window.
    A held-lock no-op is exempt: when the lock's `owner` names a live PID other than this
    wrapper's, the transient status on disk is a live peer tick's normal in-flight state, and the
    overlap is logged as a no-op instead. The check is `set -e`-safe (a missing/unreadable loop
    file skips it; the `exit=` log line and DONE self-disarm always run).
  - **Tick prompts strengthened** (wrapper + superloop L2 recipes, all three harnesses): the
    unattended prompt now also forbids ending the session with a question as the final message and
    states the no-transient-status-at-exit invariant. `scripts/README.md` exit-code table updated
    (documents 9 and the new 10 — 9 existed since 0.4.5 but was missing from the table).

  Verified with a stub-CLI regression harness (stranded RUNNING/PLANNING → exit 10 + ERROR line;
  negative controls: ready/parked/input/DONE statuses, mid-session status advance, nonzero session
  rc preserved, live-peer held-lock no-op not flagged, dead lock owner still flagged, missing loop
  file survives `set -e`; prompt-invariant assertions — 20/20). Cursor and Codex builds
  regenerated.

## 0.4.6 — 2026-08-19

- **Fix #18: a DONE loop never disarmed its own timer.** `DONE` is terminal, but the external
  driver kept firing a full CLI session per interval forever — each a paid no-op (measured:
  ~$0.65/tick, ~$88/day) — while the only shutdown signal was a "disable the timer" reminder
  written to the tick log, which unattended mode guarantees nobody reads.
  - **Wrapper self-disarm.** After the session ends, `superagent-tick.sh` reads the loop file's
    `status`; on `DONE` it uninstalls its own scheduler entry via the new
    `uninstall-timer.sh <slug> --from-tick` mode, on any session exit code (`DONE` is durable). The
    loop-status file and per-goal env file are kept, so re-arming stays a one-liner
    (`install-timer.sh <slug> <LOOP_FILE>`). Gated by `SUPER_AUTO_DISARM_ON_DONE` (new
    `superenv` key, default `true`) for anyone who deliberately wants a polling loop.
  - **`--from-tick` mode.** Self-disarm from *inside* the tick needs different launchd mechanics:
    the normal drain-wait would deadlock (the in-flight tick is the caller), and `launchctl
    bootout` kills the caller's own process group (the plist ships `AbandonProcessGroup=false`). So
    `--from-tick` skips the drain, removes the plist first (no re-bootstrap at next login even if
    the bootout lands mid-flight), reaps the wrapper's own L3 lock pre-bootout (the EXIT trap can't
    run after SIGKILL), and makes the bootout the final act. On systemd it is simply
    `disable --now` on the timer — the running oneshot service is untouched.
  - **Slug discovery.** `install-timer.sh` now records `SUPERAGENT_SLUG` in the per-goal env file;
    ticks armed by older builds fall back to scanning `~/.config/superagent/*.env` for the entry
    whose `LOOP_FILE` names this loop. The `LOOP_FILE` match is required either way — the guard
    against disarming a same-slug entry that drives a different loop. No registered entry → loud
    skip note, never a guess.

  Verified with a stub-CLI regression harness (launchd + systemd disarm, negative controls:
  non-DONE / opt-out / unregistered / mismatched registry, nonzero-rc disarm, drain-wait skip,
  plist-before-bootout ordering, slug recording — 31/31). Cursor and Codex builds regenerated;
  superloop L2/`stop_driver()` and superagent/monitor skill wording updated (the reminder is now
  the fallback for user-managed schedulers such as Desktop routines).

## 0.4.5 — 2026-08-17

- **Fix #15: external ticks were guillotined at 600s and leaked the L3 lock.** Two compounding
  defects silently halted any loop whose leaf execution exceeded 10 minutes, then wedged it for up
  to a further 90:
  - **Background-wait ceiling lifted.** `claude -p` terminates a session's background tasks after
    600s by default — shorter than a typical `superrun`/`superplan` dispatch — killing the tick's
    subagents mid-flight while the tick still exited 0. The claude branch of `superagent-tick.sh`
    now exports `CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS=0` (wait indefinitely) unless the operator
    sets a value, mirroring `TICK_TIMEOUT`'s unlimited-by-default policy. Shipped in the script
    (not the per-goal env file, which `install-timer.sh` rewrites on every re-arm).
  - **Crash-safe L3 lock.** `acquire_lock()` now also records the driving PID
    (`${SUPERAGENT_TICK_PID:-$PPID}`) in `…lockd/owner`; on a held lock, a dead owner is stolen
    immediately instead of waiting out `SUPER_LOCK_STEAL_MIN` (default 90 min). The tick wrapper
    exports `SUPERAGENT_TICK_PID`, traps EXIT/TERM/INT, and reaps a leaked lock **iff** the owner
    file names its own PID — a wrapper that exited early on the held-lock path never touches a
    peer's live lock.
  - **Loud abort.** A tick whose session hit a background-wait ceiling (only possible via operator
    override now) exits 9 with an explicit `ERROR` log line instead of a silent `exit=0`, scanning
    only its own log segment so a prior tick's output can't poison the verdict.

  Verified with a stub-CLI regression harness (ceiling default + override, own-lock reap,
  peer-lock preservation, loud abort, prior-log immunity — 10/10). Cursor and Codex builds
  regenerated; superloop L3 and consumer-skill steal-window wording updated.

## 0.4.4 — 2026-08-13

- **Dispatch-role model/effort defaults: `inherit` → pinned.** The four dispatch roles now ship
  pinned in `templates/superenv.default`: `SUPER_MODEL_{SUPERVISOR,PLANNER,EXECUTOR,PANEL}=opus`
  with efforts `medium`/`high`/`medium`/`xhigh`. Rationale: `inherit` made headless and in-session
  runs behave differently (a headless tick silently fell back to the CLI default — on Codex that
  meant reasoning effort `low`); pinning makes every run take the same models. Codex build maps
  the four pins to `gpt-5.6-sol` (same efforts); Cursor build keeps everything `inherit` (Claude
  tier names are not valid Cursor model names; Cursor has no effort control). Existing repos are
  unaffected — their `.superenv` copies still carry `inherit` — but a hand-trimmed `.superenv`
  that omits these keys now falls through to non-`inherit` effort defaults, which on the Claude
  harness require the `superagent:init`-generated `.claude/agents/super-*.md` definitions:
  re-run init in that case. Also fixed a stale README cell (`SUPER_TICK_INTERVAL` 30m → 10m,
  changed in 0.4.1).

- **supergoal: root master plan must carry the planning-session payload.** supergoal runs at the
  end of a planning session, but nothing required the root plan body to preserve that session's
  output — a title + progress-report table would have passed self-review, leaving `superplan`'s
  per-step descent (whose spec-coverage review reads the seed's sections as the step's
  requirements) with nothing to plan from. Step 4 now mandates ordered sections after the table:
  Goal & success criteria, Context (required reading), Locked decisions (with rejected
  alternatives, stated as non-relitigable), per-step guidance (one subsection per table row —
  scope, constraints, dependencies/interfaces, verification), and cross-step invariants. Step 6
  self-review checks every row has its subsection and every session decision/constraint/rejected
  alternative landed in the drafted docs. Verified via scratch-drafted supergoal simulation runs
  (2 baseline + 2 with the new text); Cursor and Codex builds regenerated.

## 0.4.2 — 2026-08-13

- **Codex sandbox default `workspace-write` → `danger-full-access`.** First end-to-end codex loop
  (tick 1) parked `WAITING FOR INPUT` at the L5 sync gate: codex's `workspace-write` sandbox keeps
  the repo's top-level `.git/` read-only (`git fetch` fails on `.git/FETCH_HEAD`; no
  `allow_git_writes` knob exists as of codex-cli 0.147.0), so any git-based loop stalls on its
  first tick. `danger-full-access` is parity with the claude harness, which runs unsandboxed;
  approvals are moot either way in headless `codex exec`. `workspace-write` remains selectable via
  `SUPER_CODEX_SANDBOX` for non-git workloads. Updated in the tick script, `.superenv` templates,
  and docs (README, scripts/README, superloop/superagent skills, codex build banner).

## 0.4.1 — 2026-08-12

- **Default tick interval 30m → 10m** in the `.superenv` default templates (canonical
  `templates/superenv.default` plus the generated Codex and Cursor copies). Script-level
  fallbacks when no `.superenv` is present (`launch.sh` / `install-timer.sh`) remain 30m.

## 0.4.0 — 2026-08-12

Experimental Cursor support (stage 1 — packaging + smoke test; not yet validated on a Cursor host):

- **Build-time strip.** Canonical skills now carry conditional markers (`cc-only` blocks/lines
  dropped in the Cursor build; `cursor-only` blocks HTML-commented in the canonical files and
  activated by the build). `scripts/build-cursor-skills.sh` derives the committed `cursor/` package
  from them: external driver only (in-session cron driver, `CronCreate`/`Monitor`/`AskUserQuestion`
  machinery stripped; superloop L4 and superagent Step 0.5 become documented no-ops), harness
  substitutions (`${CLAUDE_PLUGIN_ROOT}` → `${SUPER_PLUGIN_ROOT}`, `.claude/agents/` →
  `.cursor/agents/`, `claude -p` → `agent -p`, `ANTHROPIC_API_KEY` → `CURSOR_API_KEY`), a
  generated-file banner with tool-mapping notes on every skill, and a Cursor-specialized
  `superenv.default` (model values = Cursor model names or `inherit`). `--check` mode diffs the
  committed tree for CI/pre-release staleness.
- **Packaging.** Root `.cursor-plugin/marketplace.json` points at the self-contained `cursor/`
  plugin directory (own `.cursor-plugin/plugin.json`); also loadable via `agent --plugin-dir`.
- **Harness guard.** `superagent:init` now opens with a belt-and-suspenders harness check in both
  builds (wrong-build detection via `CLAUDE_PLUGIN_ROOT`; warns against double-loading through
  Cursor's third-party compat setting).
- **Smoke test.** `scripts/cursor-smoke.sh` (run on a machine with the Cursor CLI) exercises
  headless print mode, model listing, plugin skill discovery, a generated `cursor-smoke-probe`
  skill (plugin-root/relative-path resolution, strip verification), and the `superagent` hard gate —
  writing everything to `cursor-smoke-report.md` for reporting back.
- **Smoke-validated** (runs 1–2, Linux, agent 2026.08.11): headless `agent -p`, `--plugin-dir`
  loading, plugin-root resolution and relative template reads, the file-read tick entry
  (hard gate fires), and superpowers availability under Cursor. Two facts encoded into the
  generated banner: skill names are unprefixed on Cursor, and `disable-model-invocation` skills
  are invisible to model-driven lookup (the tick's file-read entry is therefore mandatory there).
- **Harness-aware driver scripts.** `SUPER_HARNESS=claude|cursor` (new `.superenv` key, flipped to
  `cursor` in the generated template; `--harness` flag on `launch.sh`/`install-timer.sh`, pinned
  into the per-goal registry env) selects which CLI a tick fires: `claude -p …` as before, or
  `agent -p --trust --force --plugin-dir <repo>/cursor` with `CURSOR_API_KEY`/stored-login auth
  and Cursor model names (`inherit` → the CLI's `auto`). `_common.sh` gains
  `superagent_harness` / `ensure_cursor_bin` / `ensure_cli_bin`; `superagent-tick.sh` and
  `bootstrap.sh` branch per harness.
- **Known gap** (recorded in `cursor/README.md`): no end-to-end multi-tick loop run on Cursor yet.

Experimental Codex support (stage 1 — packaging + smoke test; **smoke-validated 8/8 on
2026-08-12**, codex CLI 0.147.0 on macOS: marketplace manifest moved to
`.agents/plugins/marketplace.json` with `source.source="local"` + `AVAILABLE`/`ON_INSTALL` policy
enums per the CLI's real schema; templates moved inside `plugins/superagent/` because
`codex plugin add` copies only `source.path` into the install cache; a root-level
`.agents/plugins/marketplace.json` now makes the repo itself installable as a marketplace;
`spawn_agent` confirmed available in plain `codex exec`; README reframed as a
Claude Code + Cursor + Codex plugin with per-harness install instructions),
plus per-role reasoning effort for every harness:

- **`SUPER_HARNESS=codex` driver.** `superagent-tick.sh` gains a third harness branch alongside
  `claude`/`cursor`: fires `codex exec <prompt>` per tick against the generated Codex
  plugin-marketplace build (skills load via the *installed* plugin — `codex plugin marketplace add
  <repo>/codex && codex plugin add superagent@superagent` — not `--plugin-dir`). Auth:
  `OPENAI_API_KEY` in the target repo's `.env`, else the CLI's own stored `codex login`.
  `_common.sh` gains `ensure_codex_bin`; `superagent_harness` now accepts `claude|cursor|codex`;
  `--harness codex` works on `launch.sh`/`install-timer.sh`.
- **`SUPER_CODEX_SANDBOX`.** New `.superenv` knob (codex harness only): `workspace-write` (default
  — `--sandbox workspace-write -c sandbox_workspace_write.network_access=true`) or
  `danger-full-access` (`--dangerously-bypass-approvals-and-sandbox`). An out-of-domain value now
  aborts the tick with a new exit code, 8, rather than silently picking a posture.
- **`SUPER_EFFORT_*` keys.** Ten new per-role reasoning-effort keys (mirroring the `SUPER_MODEL_*`
  role table) resolved the same three-layer way (env > `.superenv` > plugin default). Domain is
  harness-native: claude `low|medium|high|xhigh|max`, codex `none|minimal|low|medium|high|xhigh`
  (no `max`); the Cursor CLI has no effort control (any non-`inherit` value WARNs and falls back to
  `inherit`). Every shipped build defaults the four dispatch-only roles
  (supervisor/planner/executor/panel) to `inherit` and the SDD worker roles to a nonzero effort
  (`medium` implementer/fix-applier, `high` reviewers/fix-planner, `xhigh` branch-reviewer).
- **`--effort` on claude ticks.** `superagent-tick.sh` now passes `--effort <value>` to `claude -p`
  whenever `SUPER_EFFORT_SUPERVISOR` (or `TICK_EFFORT`) resolves non-`inherit`. The driver never
  sets `CLAUDE_CODE_EFFORT_LEVEL` itself (it outranks both `--effort` and per-role agent-definition
  effort pins) and warns if the scheduler environment already carries it.
- **`.superenv` validation pass.** `superagent:init` Step 2 now lints the resolved configuration
  (unknown `SUPER_*`/`TICK_*` keys, enum/boolean/numeric domains, and model/effort key domains per
  harness) and reports one WARN + effective-fallback row per finding — report-only, never rewrites
  the user's `.superenv`.
- **Codex build + smoke harness.** `scripts/build-codex-skills.sh` derives a generated Codex
  plugin-marketplace tree (`codex/`) from the canonical skills, reusing the Cursor build's
  conditional-marker mechanism plus a new `codex-only` marker (content inert as an HTML comment in
  the canonical files, activated only in this build); `--check` mode diffs a fresh rebuild against
  the committed tree and exits 1 if stale. `scripts/codex-smoke.sh` runs T1–T6 against a live Codex
  CLI (headless exec, marketplace + plugin install, skill enumeration, a generated
  `codex-smoke-probe` skill, `spawn_agent` availability, the real tick file-read entry + hard gate,
  and effort-flag pass-through), always exits 0, and writes `codex-smoke-report.md`.
- **Known gap** (recorded in `codex/README.md`): no end-to-end multi-tick loop run on Codex yet;
  `spawn_agent` availability in plain `codex exec` sessions is unverified (smoke T4b).

## 0.3.0 — 2026-08-11

`SUPER_MODEL_*` keys now accept full model IDs (`claude-<family>-<version>`, e.g. `claude-fable-5`;
no date stamp needed) alongside the tier names and `inherit`. The Agent tool's `model:` parameter is
tier-enum-only (verified empirically on this build — a full ID fails schema validation), so for the
nine subagent role keys the pin rides a per-role agent definition (`.claude/agents/super-<role>.md`,
`model:` frontmatter — verified to accept undated full IDs via a headless smoke test) that a new
`superagent:init` Step 3 generates, refreshes, and removes as derived artifacts. Dispatch rules
updated in `superagent` (canonical **Model resolution** block under Subagent dispatch), `superrun`
(SDD model policy), and `superloop` (L7 panel). `SUPER_MODEL_SUPERVISOR` needs no definition — the
tick already passes it verbatim to `claude --model`.

## 0.2.0 — 2026-08-11

launchd (macOS) support for the external driver: every lifecycle script auto-dispatches by OS
(systemd user timers on Linux, launchd LaunchAgents on Darwin), with a per-goal plist rendered
from `scripts/launchd/com.superagent.tick.plist.template` and the same `~/.config/superagent/<slug>.env`
registry on both schedulers. Auth fallbacks: the tick no longer hard-requires `ANTHROPIC_API_KEY`
(falls through to the claude CLI's stored login) and `GH_TOKEN` loading falls back to `gh auth token`
(OS-keyring hosts). Also fixes three latent `set -e`/`pipefail` crashes in `status.sh`/`_common.sh`
probe paths, and adds `/opt/homebrew/bin` to the scheduler-PATH augmentation.

Smoke-validated 2026-08-11 on macOS (external/launchd mode): install / idempotent re-install /
status / stop dry-run / graceful drain / force-stop with stale lock on a throwaway slug, plus an
end-to-end migration of a live loop off a hand-rolled plist. External (systemd) driver mode still
NOT smoke-tested on Linux.

## 0.1.0 — 2026-08-06

Initial extraction from network-compose at 5f234bae: 12 ported skills, external driver
scripts, `.superenv` config contract, new `superagent:init` bootstrap skill.

Smoke-validated 2026-08-06 on macOS (attended/cron mode): init idempotency, supergoal, full loop to
two-signal DONE in 4 ticks (superplan → superrun/SDD → exhaustion signals) on a no-remote
SUPER_PROTECTED_MAIN=false scratch repo; direct-commit and direct-merge landing paths exercised.
External (systemd) driver mode NOT yet smoke-tested — validate on a Linux host before first
unattended use.
