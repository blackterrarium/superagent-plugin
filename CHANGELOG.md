# Changelog

## 0.4.8 — 2026-08-28

- **A loop parked on `WAITING FOR INPUT` no longer burns a paid session per interval.** The
  wrapper had no pre-screen for the parked state, so every scheduler fire launched a full CLI session
  that read the file, found no answer, and exited — the DONE-polling waste of #18, still open for the
  parked state. Three additive driver changes (no skill-logic or scheduler change):
  - **Bash gate (`SUPER_INPUT_GATE=true`).** `superagent-tick.sh` reads the loop file before any
    preflight; `WAITING FOR INPUT` with no `answer:` under `## Pending decision` → one log line,
    exit 0, no session. Polling continues for free; resume-on-answer is unchanged.
  - **One notification on the transition (`SUPER_NOTIFY_CMD`).** The wrapper snapshots `status`
    before the session and fires `superagent_notify` when the tick parks the loop
    (`waiting-for-input`, body = the pending question) or finishes it (`done`). Your snippet runs via
    `bash -c` with `SUPERAGENT_EVENT/SLUG/TITLE/BODY` + `LOOP_FILE` in env (ntfy/Slack/Pushover…);
    unset → `osascript` (macOS) / `notify-send` (Linux) when available. A failing notifier is logged
    and never fails the tick. Transition detection = fires once, no sidecar state.
  - **`scripts/answer.sh [--no-kick] <slug> <answer…>`.** Records `answer: <text>` directly under
    `## Pending decision` holding the L3 lock (refuses with exit 4 while a tick is mid-flight, 3 if
    the loop isn't parked), then kicks one tick via the registered scheduler entry so the loop resumes
    in seconds. Kick logic lifted into `_common.sh` (`superagent_kick_tick`) and shared with
    `launch.sh`. `superagent-monitor` now recommends it as the primary answer path.
  - New `_common.sh` readers `superagent_loop_status` / `superagent_pending_section` /
    `superagent_pending_answer` (answer detection is scoped to the pending section — an `answer:`
    under `## Decisions` never counts).
  - All new helpers tolerate empty arguments (`${1:-}`, never `${1:?}` — which would abort the
    calling tick); `answer.sh` passes the answer through `ENVIRON` (backslash-safe), checks for the
    heading before taking the lock, and traps TERM/INT so a signal never leaks the lock.
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
