# Codex mdtoc full-stack restart — 2026-09-08

Status: PHASE 3 EVALUATED — FAIL (J3 missing required tilde-fence regression cases).
Phases 1–2 and the six-tick scheduled delivery/evaluation workflow ran; the scheduler is disarmed.
The whole request is not complete: Phase 4 is NOT EXERCISED, awaiting approval of the bounded
controlled-fixture design under the brainstorming skill. Prior baseline remains FAIL.

## Phase 1 preflight

- Source main: `790a86b3825d3d142c8d6d9b538c5f942b8a10ce`; repair `1852780` is an ancestor. Local main is two commits ahead of origin/main. No plugin push performed.
- Existing uncommitted manifest cachebuster: `0.8.1+codex.20260908005203`. Preserved as evaluation setup, not a source repair or release. Existing unrelated untracked files preserved.
- Installed/runtime package: `/Users/eugene/.codex/plugins/cache/superagent/superagent/0.8.1+codex.20260908005203`. Current session skill catalog and `codex plugin list` both select it, enabled from the local superagent marketplace rooted at this checkout. No reinstall needed.
- Codex CLI `0.153.4`; logged in using ChatGPT. Python 3.9, bash 3.2, gh available. No timeout/gtimeout; timeout enforcement unverified.
- GitHub keychain auth works outside sandbox. Baseline PR #1 is OPEN, mergedAt null, head `db1d502d8ea38d7a7446aa89f22cdcbd66e99adc`, branch `mdtoc-r1-complete-cli`.
- Toy clean main: `06b3f17a07f5dfefa259fefe24e0a1ec5f98f8d0`, `/Users/eugene/src/mdtoc-loop-test`.
- External vault clean main: `43d3de4631ca5fa7a0711ccfe68c367389e2a9fd`, `/Users/eugene/superagent-vaults/mdtoc-loop-test`.
- Old worktree retained at `/Users/eugene/src/mdtoc-loop-test-worktrees/mdtoc-r1-complete-cli`, head `db1d502`.
- Registry `mdtoc-r1`: retained DONE iteration 4; timer inactive, tick inactive, lock absent, no pending input. Other listed loops also inactive. No scheduler changes in Phase 1.
- Toy `.superenv` differs from repaired generated defaults only in `SUPER_GOAL_ROOT`, correctly pointing at its external vault. No config changes or init rerun needed. Supervisor/executor `gpt-5.6-sol` medium; planner/reviewer/evaluator `gpt-5.6-sol` high; panel/branch reviewer `gpt-5.6-sol` xhigh; implementer/fix-applier `gpt-5.6-terra` medium. Sandbox configuration is the existing `danger-full-access` default; CI/review/merge gates unchanged.
- Pi and Cursor builders `--check`: PASS. Codex working-copy `--check`: exit 1 solely for pre-existing cachebuster version and JSON formatting; no generated runtime-content differences. Codex `--check` on a clean `git archive` of source SHA above: PASS. This exception is recorded, not suppressed by editing the user's manifest.
- Six installed/generated skill files compared with `cmp`: exact match. Installed traversal contains C8/C9 and supervisor invokes C9 before DONE. External wrapper uses this checkout's `scripts/` and generated Codex supervisor.

| Skill | SHA-256 (generated and installed) |
|---|---|
| superagent | c0a7cbb053ad8d2d52d950146cd7ab94d8c482dd4f7b9a020b3c0c5e21d50428 |
| supertraverse | 0254ecc9d7a822c1c2d4c4bacd02d05e53354c444a04824f10dcabd74e594b3c |
| superplan | 14eb541dfb23f808c06a3bd6a81de7402709fa11f6f2934ece11c7393678ebe5 |
| superrun | 8be5857df431248b8135e53bffc61f2119cadfbc9dce66d709b17e56e852fef0 |
| superfinish | 4f8d00d766e8da78a24b3e3f4dabcefd2e38304de62290c50bbedbbd720291fe |
| superloop | f48f73b99a418bf8b2185e929541f8f1f1377c460863a15a7347dfa96223f254 |

## Phase 2 acceptance preparation

Draft project identity: `projects/2026-09-08-01_12-mdtoc-lifecycle-repair`.
Scratch: `/private/tmp/superprd-mdtoc-lifecycle-20260908.2Dd37d`.
Initial installed `prd-lint.sh --json`: PASS, no WARN or FAIL.
All nine commands C0–C8 inspected through installed `_evalspec.sh`; shell syntax valid.
Negative controls: all C0–C8 exit 1 on bootstrap-only main, including hardened C4 and C7.
C1 empty test directory exits 1 (`zero tests`). C7 disallowed `requests` import and syntax error
each exit 1; allowed `tempfile`/`pathlib` control exits 0. Zero unexpected outcomes.
Raw log in scratch `negative-controls.log`; preserve in durable evidence before launch.
Fresh PRD_REVIEWER dispatched as `/root/prd_reviewer`, `gpt-5.6-sol` high, isolated context.
Reviewer received only the three draft file paths and the two standard sufficiency questions,
then read their full bytes; this is a transport deviation from superprd's inline-verbatim prompt.

After two re-reviews, the reviewer reported no remaining material contradictions or blocking
ambiguities. Clarifications bound supported Markdown/byte behavior and make evaluation evidence
and failure injection operationally specified. Final review is preserved verbatim in the project.
The user's full-restart instruction supplied authority for scoped publication; no additional
superprd confirmation pause was taken.

Frozen project contract commit: `dee57b8e88f57616a89fbfd6010ef629e4f9a907`.
Evidence commit: `81f600f` (operator-evidence: preflight, review, lint and negative controls).
No lint WARN/FAIL; all control outcomes expected. Entire installed package also compared with
generated package using `diff -qr`: no differences, including role skills beyond the six hashes.

| Frozen file | SHA-256 |
|---|---|
| prd.md (before routine ledger updates) | 48b5b52c3d0b6535b0de845d3161632b116ab148264c0c572ed7bad0938e67cf |
| knowledge-base.md | 5045e610245d5bf33a5ec1ffbc61bb5a7e563d320b1ce7b642393b118b2df337 |
| evaluation.md | b3aae788d03e92aba020910cf747a8fe783ada2b00530214584c6de5be5905cc |

## Phase 3 supermeta

Installed supermeta invoked from the operator context against the new READY project.
Input lint PASS. Meta-plan transcribes every SC/C/J row and contract note unchanged, plus the
full objective, constraints and decisions. Knowledge sources: code README and fetched
https://github.com/Flet/github-slugger (explicit PRD subset remains authoritative).
Draft self-review completed; published pending ledger commit at
`projects/2026-09-08-01_12-mdtoc-lifecycle-repair/meta-plans/2026-09-08-01_24-r1.md`.
Native PLANNER dispatch `/root/root_planner`, gpt-5.6-sol/high, isolated context,
supergoal --autoconfirm with SUPER_GOAL_AUTOCONFIRM=true scoped to this child only.
No persistent config change. Planner returned goal/root with no findings; goal commit `9486752`.
Root: `2026-09-08-01_27-mdtoc-lifecycle-repair-r1/master-plans/2026-09-08-01_27-mdtoc-lifecycle-repair-r1.md`
under the external vault. It has two steps: complete functional tool/tests, then README/final audit.
Root explicitly authorizes repaired parser/write behavior and requires metadata/symlink policy in
the implementation plan before execution. Supermeta ledger/meta-plan commit: `000eead`.

## Phase 3 scheduled execution

Launch UTC: `2026-09-08T01:36:40Z`; first wrapper start `2026-09-08T01:36:41Z`.
Slug: `mdtoc-lifecycle-20260908-0124`; label: `com.superagent.tick.mdtoc-lifecycle-20260908-0124`.
Interval 5m (300 seconds), no per-tick timeout, streaming output, existing .superenv unchanged.
Registry: `/Users/eugene/.config/superagent/mdtoc-lifecycle-20260908-0124.env`.
Loop: `<goal>/loop-status/2026-09-07-mdtoc-lifecycle-20260908-0124.md` (local date prefix).
Wrapper log: `/tmp/superagent-2026-09-07-mdtoc-lifecycle-20260908-0124.log`.
Launchd log: `/tmp/superagent-launchd-mdtoc-lifecycle-20260908-0124.log`.
Initial status: timer active, tick active, WAITING FOR PLAN iteration 0; gh auth ok:blackterrarium.
Actual first wrapper receipt: harness codex, model gpt-5.6-sol, effort medium,
sandbox danger-full-access, stored CLI login. Thread `01a07ea9-05aa-7cc2-b367-858cefe4dd04`.
First supervisor read uses this checkout's generated repaired Codex SKILL.md.
Launch happened through `superagent-external`/launch.sh; launchd owns implementation ticks.

| Tick | Wrapper UTC start → end | Verified result |
|---|---|---|
| 1 | 01:36:41 → 02:05:20 | exit 0; implementation plan committed as 028f5cf; WAITING FOR RUN, iteration 1 |
| 2 | 02:10:21 → 03:01:44 | exit 0; PR #2 merged and closeout committed; WAITING FOR PLAN, iteration 2 |
| 3 | 03:06:45 → 03:19:45 | exit 0; Step 2 plan committed 1124ecb; WAITING FOR RUN, iteration 3 |
| 4 | 03:24:45 → 03:46:39 | exit 0; PR #3 merged and closeout committed; WAITING FOR PLAN, iteration 4 |
| 5 | 03:51:40 → 03:57:15 | exit 0; planner returned none; WAITING FOR RUN, iteration 5, exhaustion true |
| 6 | 04:02:16 → 04:08:00 | exit 0; no execution target; C9 complete; DONE iteration 6; self-disarm |

Tick 1 native planner receipt: dispatched 01:39:21Z as `tick_superplan`, gpt-5.6-sol/high,
child thread `01a07eab-75b0-7180-8aae-9e2306ff9ac3`. Plan:
`<goal>/plans/2026-09-08-02_00-build-bounded-mdtoc-cli.md`.
Its policy/finding commit `028f5cf950893800a9aff973e8d2fddfb74c1654` predates execution
(commit time 02:02:27Z; ready-state log 02:04:14Z). It specifies all corrected parser/write
behavior and final-symlink following with target POSIX mode preservation. Native planner
and supervisor transcripts, wrapper log and after-tick1 loop snapshot are preserved at
`<goal>/loop-status/operator-evidence/` (ignored during live ticks to keep vault sync clean).
This is ordinary plan publication, not blocked-replan recovery coverage.

Tick 2 executor receipt:
`role-bridge: start=20260908T021405Z harness=codex model=gpt-5.6-sol effort=medium tools=executor role=executor cwd=/Users/eugene/src/mdtoc-loop-test`.
Live log: `/private/var/folders/qn/7bff6lmd5g32dd779w3n1cv80000gn/T/superagent-bridge/executor-20260908T021405Z-82633.log`.
New worktree: `/Users/eugene/src/mdtoc-loop-test-worktrees/mdtoc-lifecycle-repair-r1-step1`;
branch `mdtoc-lifecycle-repair-r1-step1`. Executor preflight reports no plan conflicts and has
entered the delegated task loop. No operator implementation, manual tick, answer or force-stop.

Tick 2 executor ended `2026-09-08T02:58:34Z`, exit 0. Code PR #2 independently verified
MERGED at `02:53:50Z`, merge SHA `22763e18179232283a12c8d068a30aa162075572`, now on code main.
Closeout commit `777dbe3` records Step 1 completed-and-merged; Step 2 remains incomplete.
Executor reports 23 tests and frozen C0–C8 green, task reviews and whole-branch review clean.
Task commits: `3825c1f` parser, `3706a2b` CLI/fixtures, `dddd23a` read-error nonmutation test fix.
The executor disclosed and accepted a Minor process-evidence gap: the second parser-matrix
RED chronology was not preserved. RED-before-GREEN ordering for that tranche cannot be
proven beyond the initial missing-module RED. This is an autonomous executor ruling, not
an operator waiver; independent product evaluation remains outstanding. No CI is configured;
the existing local-evidence setting was used without changing review or integration gates.
Completed executor log and native session receipt are copied into ignored durable run evidence.

Tick 3 supervisor thread: `01a07efb-7c45-7a33-b71b-0ce8bd1195df`. Native `tick_superplan`
dispatch at `03:08:56.149Z`, isolated context, `gpt-5.6-sol`/high. No operator action between ticks.
Planner child `01a07efd-79da-7913-b307-a11e74874797` published
`<goal>/plans/2026-09-08-03_10-document-mdtoc-contract-and-close-acceptance.md` as `1124ecb`.
The ready-state transition was observed at `03:18:28Z`; wrapper exit at `03:19:45Z`.

Tick 4 supervisor: `01a07f0b-f85b-7f60-99dd-d4551fd9895a`. Actual executor receipt:
`role-bridge: start=20260908T032652Z harness=codex model=gpt-5.6-sol effort=medium tools=executor role=executor cwd=/Users/eugene/src/mdtoc-loop-test`.
Executor CLI session `01a07f0d-e5dc-7dd3-b92c-41dc0a92d2e5`, Codex 0.153.4,
existing danger-full-access setting. Log basename `executor-20260908T032652Z-24763.log`
under the same temporary superagent-bridge directory as Tick 2.
Executor ended `03:44:42Z`, exit 0. Task commit `7e72409` on isolated `docs-mdtoc-readme`;
task reviewer `sol`/high and whole-branch reviewer `sol`/xhigh dispatched at `03:33:09Z`
and `03:36:51Z`, respectively. PR #3 verified MERGED at `03:40:04Z`, merge SHA
`aaf0a84e144058a53ba8996db6289127764db2ba`, now on main. Closeout commit `db7d715`.
No new findings reported. Evaluation and knowledge-base hashes rechecked unchanged.

Tick 5 supervisor `01a07f24-9ac4-7df0-b2f4-1000e8e67108` used a native `planner_relay`
dispatch at `03:54:28.549Z` (`gpt-5.6-terra`/high, isolated), then actual role receipt
`role-bridge: start=20260908T035436Z harness=codex model=gpt-5.6-sol effort=high tools=planner role=planner cwd=/Users/eugene/src/mdtoc-loop-test`.
Actual planner CLI session `01a07f27-49d9-72a2-96d1-428a806dd4a8`; planner bridge log
`planner-20260908T035436Z-18866.log`. Earlier planners were dispatched natively; the
actual planner pin remains sol/high in both paths.
Planner ended `03:56:18Z`, exit 0, report: “No available task to plan — every step is
completed or already has a plan”. The supervisor set planning exhaustion and WAITING FOR RUN,
not DONE. No code/vault deliverable change was made by this exhausted planning pass.

Tick 6 supervisor `01a07f2e-4fc4-76e3-a085-3b51c54676e6`; executor bridge started
`04:04:54Z`, actual Codex `gpt-5.6-sol`/medium, session `01a07f30-b8f6-7793-ae4a-d4290483620b`.
Executor ended `04:06:29Z`, exit 0, with no execution target and explicit C9 complete:
both PRs MERGED, both merge SHAs on synchronized main, both closeouts tracked in clean vault
`db7d715`, no unresolved obligation in this goal. Historical PR #1 remains outside this goal.
Watcher observed DONE at `04:07:29Z`; wrapper exited and began self-disarm at `04:08:00Z`.
Independent status enumeration subsequently verified timer inactive, tick inactive, lock absent,
no pending input, DONE iteration 6. No operator answer, manual tick, force-stop, code edit,
plan-tree edit or scheduler intervention occurred during this delivery loop.
All six wrapper/skill reports and associated runtime receipts are preserved in the new project's
`operator-evidence/runtime/`, copied only after disarm; no active vault sync was dirtied.

## Independent product evaluation — FINAL FAIL

Installed supereval input lint: PASS, no WARN/FAIL. Code main fetched and verified exactly equal
to origin/main (`0 0`); both code and vault tracked trees clean, vault has no remote.
Evaluated SHA: `aaf0a84e144058a53ba8996db6289127764db2ba`. Packaged supereval runner exit 0:
C0–C8 all PASS. Output `/private/tmp/supereval-mdtoc-lifecycle-r1.m5IyLn/results.md`;
kept detached worktree `/var/folders/qn/7bff6lmd5g32dd779w3n1cv80000gn/T/tmp.bm0jJx24ma`.
Runner warns no timeout/gtimeout; checks ran uncapped. No acceptance amendment was made.
PRD diff from frozen commit contains only supermeta's ledger row; KB/evaluation hashes unchanged.
Exactly one read-only native EVALUATOR `/root/delivery_evaluator`, sol/high, isolated context.
Prompt contains J1–J3 verbatim plus explicit evidence-path bindings and the frozen Contract-notes
location. This expands the skill's minimal prompt transport to resolve J3's external evidence
pointers; criteria, minimum cases, baseline and ordering requirements are unchanged.

The evaluator initially returned J1–J3 PASS. Before aggregation, the operator asked the same
evaluator to map the frozen minimum-case requirement for **both** fence characters separately.
The evaluator corrected J3 to FAIL: backticks have shorter/mismatched/suffixed/valid closers,
but the tilde test only has an opener and valid closer. Missing assertions are a shorter tilde
closer, a mismatched backtick closer while in a tilde fence, and a non-whitespace-suffixed tilde
closer. Evidence: evaluated `tests/test_transform.py:95` through its test body, especially line 99.
This is missing required regression evidence, not an observed runtime parser failure. No test,
source, criterion or expected result was changed to obtain a verdict. Both evaluator responses
and the clarification are preserved. The whole-branch execution audit's earlier J3 YES is not
substituted for this independent final result.

| Id | Final result | Evidence / reason |
|---|---|---|
| C0 | PASS | Script exists and compiles; exit 0 |
| C1 | PASS | Nonzero unittest discovery and successful suite; exit 0 |
| C2 | PASS | Stdout nonmutation and byte idempotence; exit 0 |
| C3 | PASS | Duplicate links; exit 0 |
| C4 | PASS | Hardened missing-input diagnostic; exit 0 |
| C5 | PASS | No-argument usage/exit; exit 0 |
| C6 | PASS | Marker error/diagnostic/nonmutation; exit 0 |
| C7 | PASS | AST stdlib allowlist; exit 0 |
| C8 | PASS | Bounded parser subprocess fixture; exit 0 |
| J1 | PASS | README CLI, markers, slugs, duplicates and metadata/symlink policy |
| J2 | PASS | Only allowed README/source/fixture/test paths since bootstrap |
| J3 | FAIL | Three required invalid tilde-closer cases are not asserted |

Final report: `<project>/eval-reports/2026-09-08-04_13-r1.md`, committed with the completed
FAIL ledger row as vault commit `3cc0a04`. Runtime/evaluator evidence and a report EOF-whitespace
correction are committed as `07854c7`; vault is clean. Only the temporary detached evaluator
worktree was removed after grading; the real repos and historical worktree remain available.

## Distinct verdicts and remaining work

- **Product/full-stack delivery: FAIL.** Actual PR integration, six scheduled ticks and automatic
  disarm succeeded, but independent evaluation fails J3. A DONE string and green C checks do not
  override that missing acceptance evidence.
- **Blocked-replan recovery: NOT EXERCISED.** No blocked closeout, adopted C8 repair request,
  successor publication or successor execution occurred in this delivery run. Ordinary planning
  and task-review fixes do not count as that coverage.
- **Prior baseline: FAIL, unchanged.** Verified old PR #1 OPEN/unmerged at original head
  `db1d502d8ea38d7a7446aa89f22cdcbd66e99adc`; old worktree clean at that SHA; protected old
  project/goal diff from vault baseline `43d3de4` is empty.
- **Other harnesses / timeout: unverified.** This was a Codex run only. No timeout/gtimeout exists.

### Phase 4 design checkpoint — not provisioned

The brainstorming skill classifies the separate fixture as a bounded change and requires
explicit design approval before implementation. An approval question was presented while the
independent evaluator ran; no answer has yet been received. This gate pauses Phase 4 only,
not the completed and honestly graded Phase 3 workflow. No new fixture goal/branch/PR exists.

Proposed design: create a fresh branch/worktree/PR from the delivered main, add a regression
combining fence state across the omitted TOC region with a non-whitespace-suffixed would-be
closer, and prove it passes before introducing the old prefix-only fence-close defect on that
branch only. Keep the new regression through repair so integration has meaningful test coverage.
Freeze a separate, explicitly operator-fixture acceptance project. Record the real failing PR
and a tracked blocked predecessor closeout in its own goal; do not author `repair requested`
or a successor. Start a unique five-minute scheduler and require the real panel/C8/fresh planner/
successor execution/integration/C9/supereval/disarm chain. Main and historical PR #1 are never
downgraded for setup. A supported operator answer, if later needed, must be labeled assisted.
The Phase 3 FAIL is preserved regardless of any later scenario's outcome; adding its missing
tilde cases is not silently folded into this separate fixture scope.

## Preserved baseline

[Prior failure RCA](../handoffs/2026-09-07-mdtoc-failure-rca-handoff.md).
Old evaluation: external vault `projects/2026-09-07-21_30-mdtoc/eval-reports/2026-09-07-23_09-r1.md`.
Old PR: https://github.com/blackterrarium/mdtoc-loop-test/pull/1. Never merge or rewrite as part of this restart.
