# Coding Loop Stage 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a restartable outer coding loop that diagnoses failed acceptance and drives repairs, with separate live acceptance on Claude, Codex and Pi.

**Architecture:** Add `supercode` as the second consumer of the existing superloop chassis. Keep model work in skills, isolate deterministic project state/evidence handling in small helpers, and reuse the existing scheduler and inner implementation loop. Integrate each task through its own reviewed change; release only after all three harnesses pass.

**Tech Stack:** Bash 3.2-compatible scheduler scripts, Markdown skills, Git/GitHub, Python 3.9+ standard-library helpers and unittest. Python is a preflight requirement for the new project supervisor; legacy standalone goal execution gains no Python dependency.

**Spec:** `docs/superpowers/specs/2026-09-09-coding-loop-stage3-design.md`, approved by the author on 2026-09-09. Read it in full alongside this plan; its S3-AC1–S3-AC12 rows are binding.

## Global Constraints

- Require live acceptance on **Claude, Codex and Pi**.
- No parallel project rounds, shared inner loop, automatic specification changes, attended outer driver or statistical reliability study is included.
- Cursor receives generated compatibility checks, but is not a required live acceptance target.
- A supervisor must be native to the selected harness; foreign worker roles use existing bridges.
- Paths inside the primary checkout are repo-relative; external vault paths are absolute.
- The project field never masquerades as `master_plan`.
- External-vault reports commit directly to that vault under A7; internal-vault reports use the existing PR workflow.
- A missing required assertion is a delivery defect even when product behavior and commands pass.
- Specification defects always require author input, never an automatic change to prd.md, evaluation.md or binding requirements.
- `SUPER_CODE_MAX_ITERATIONS` limits created project rounds, not ticks or transport attempts.
- All three must pass before claiming Stage 3 live acceptance complete.
- No existing private production/toy state or historical cohort is used.
- Preserve the unrelated local cachebuster, untracked handoffs, smoke report and html-docs. Execute in an isolated worktree; never bulk-stage them.
- No production code is supplied by this planning session. Code blocks below are implementation/test contracts, not executed changes.

---

## Delivery order and source map

Tasks 1–8 build and deterministically verify the feature. Task 9 prepares the concrete live run
manifest, obtains its approval, executes the required acceptance and releases. That manifest
approval is already required by the approved spec; do not substitute the old fixture's approval.
Task 9 can be INCOMPLETE without falsely marking earlier implementation tasks unbuilt.

| File | Responsibility |
|---|---|
| `scripts/_coding_loop_state.py` (new) | Strict state parsing, project identity, atomic compare-and-set updates and phase/operation records |
| `scripts/_coding_loop_evidence.py` (new) | Agreement fingerprint, committed artifact/ledger reconciliation and verdict validation |
| `scripts/coding-loop-state-test.py` (new) | Isolated filesystem/Git tests for those two helpers |
| `scripts/coding-loop-driver-test.py` (new) | Fake CLI/scheduler integration tests for real launch/tick/control scripts |
| `scripts/coding-loop-diagnosis-test.py` (new) | Diagnosis format checks and separate read-only interpretation probes |
| `skills/superdiagnose/SKILL.md` (new) | One failed round → source-grounded diagnosis and disposition |
| `skills/supercode/SKILL.md` (new) | One outer tick and verified state advancement |
| `skills/supercode-external/SKILL.md` (new) | Project launch/resume wrapper |
| `templates/coding-loop-diagnosis.md` (new) | Exact report headings and fields shared by skill and validator |
| `scripts/launch.sh`, `install-timer.sh`, `superagent-tick.sh` | Supervisor selection, project registration and BUILDING gate |
| `scripts/status.sh`, `stop.sh`, `force-stop.sh` | Project identity, outer/inner visibility and existing lifecycle commands |
| `scripts/_common.sh` | Small shared shell identity/path wrappers only |
| `skills/superloop/SKILL.md` | Consumer-specific input/location and recovery contract |
| `skills/supermeta/SKILL.md`, `supergoal/SKILL.md`, `supereval/SKILL.md` | Optional operation targeting and recovery of already integrated work |
| `skills/superagent-monitor/SKILL.md`, `superagent-stop/SKILL.md`, `superagent-force-stop/SKILL.md` | Document project-aware reuse and independent child control |
| `scripts/coding-loop-stage3-live.py` (new) | Manifest validation, isolated live execution, receipts and cleanup |
| `scripts/coding-loop-stage3-live-test.py` (new) | Fake-process tests of budget/identity/protocol enforcement |
| `scripts/build-{codex,cursor,pi}-skills.sh`, `coding-loop-package-test.sh` | Generate new skills and package their required helper dependencies |
| `templates/superenv.default`, `skills/init/SKILL.md` | Activate existing Stage 3 configuration and document prerequisites |
| `.claude-plugin/plugin.json`, generated manifests, `README.md`, `scripts/README.md` | Release version and user-facing behavior |

Do not refactor unrelated scheduler internals. Existing `lifecycle-regression.py` validates
model answers about skills; it does not execute scheduler code. Keep that distinction when
adding new tests. New fake-driver tests must invoke actual changed scripts, not a duplicate
state machine implemented only in tests.

## Task 1: Strict project state and durable phase identity

**Files:** Create `_coding_loop_state.py`, `coding-loop-state-test.py` under `scripts/`.
**Owns:** S3-AC2 and the identity/state foundation of S3-AC4/S3-AC6.
**Depends on:** Approved spec only.

**Interfaces:** Python module loaded from the scripts directory. These are signatures;
implementation behavior is specified in the steps below:

```text
StateError extends ValueError
read_state(path: Path) -> dict
project_identity(repo: Path, vault: Path, project: Path) -> dict
replace_state(path: Path, expected: dict, updated: dict) -> None
recover_ready(status: str) -> str
```

`project_identity` returns physical `repo`, `vault`, `project` paths and the canonical stored
project locator. `replace_state` compares the current frontmatter with `expected` and refuses
stale writes; preserve the Markdown body, file permissions and unrelated frontmatter fields.
Write a same-directory temporary file and replace atomically while the caller holds the
existing L3 lock. Do not add a second incompatible lock implementation.

Expose CLI `python3 scripts/_coding_loop_state.py read STATE` → JSON, and
`python3 scripts/_coding_loop_state.py replace STATE --expected EXPECTED.json --updated UPDATED.json` → exit 0 on update,
2 for invalid data or stale state. No eval/source/shell interpretation of state data.

- [ ] Add unittest cases using `TemporaryDirectory`, local Git repositories and linked
  worktrees. Cover internal vault, separately initialized external vault, project symlink
  escaping its vault, duplicate identity keys, malformed round, unknown supervisor and stale
  compare-and-set. A positive fixture must preserve Pending decision text byte-for-byte.

```python
def test_stale_state_does_not_overwrite_decision(self):
    original = read_state(self.state_path)
    updated = dict(original, status="WAITING FOR BUILD")
    self.state_path.write_text(self.state_path.read_text() + "\noperator note\n")
    # A body-only update is preserved; state frontmatter still matches.
    replace_state(self.state_path, original, updated)
    self.assertIn("operator note", self.state_path.read_text())
    with self.assertRaises(StateError):
        replace_state(self.state_path, original, updated)
```

- [ ] Run `python3 scripts/coding-loop-state-test.py -v`; confirm the new behavior is absent
  before implementation. Use actual unittest setup to create `self.state_path` with valid
  frontmatter, round 1 and WAITING FOR META-PLAN.
- [ ] Implement strict parsing for the existing frontmatter subset: flat fields and the new
  operation mapping, no general YAML execution. Reject duplicate keys, missing required project
  identity, nonpositive/noninteger round and invalid phase/status combinations.
- [ ] Define `operation` fields: `id`, `phase`, `round`, `agreement_revision`, `code_commit`,
  `meta_plan`, `goal_folder`, `report`, `source_vault_commit`. `id` is generated once per phase
  with `uuid.uuid4().hex` and preserved across retries. Empty inapplicable fields are explicit;
  a required source/path cannot be empty. Code SHA is captured only for evaluation/diagnosis.
- [ ] Implement recovery mapping below; other status values return unchanged, and unknown
  states are rejected during parsing.

```python
RECOVER_READY = {
    "META-PLANNING": "WAITING FOR META-PLAN",
    "EVALUATING": "WAITING FOR EVAL",
    "DIAGNOSING": "WAITING FOR DIAGNOSIS",
}
```

- [ ] Run the test command to PASS. Stage only these files and commit
  `feat(coding-loop): add strict project state and phase identity`.

## Task 2: Agreement and committed-evidence validation

**Files:** Create `scripts/_coding_loop_evidence.py`; extend `coding-loop-state-test.py`.
**Owns:** S3-AC4/S3-AC6 and the completion preconditions for S3-AC5.
**Consumes:** Task 1 state and operation fields.
**Produces:**

```text
agreement_fingerprint(project: Path, binding_manifest: list) -> str
reconcile_operation(repo: Path, vault: Path, operation: dict) -> dict
validate_evaluation(report: Path, evaluation: Path, expected: dict) -> dict
```

Binding manifest entries contain `locator`, `source_revision`, `sha256` and the resolved
text file path. Hash a canonical JSON array of labeled content digests sorted by locator.
Include the complete evaluation/knowledge-base bytes and all PRD bytes except the Iteration
ledger section. Reject duplicate/missing bindings. Remote binding sources require captured
text and source provenance; an unresolved pointer is unavailable context, not an empty file.
The fingerprint must not include the moving vault HEAD; store that separately as provenance.

`reconcile_operation` returns JSON with `outcome` equal to `ABSENT`, `INTEGRATED` or `CONFLICT`,
and verified artifact paths/commits or a reason. It must inspect Git integration and matching
operation identity, not select the newest timestamp. Expose CLI subcommands `fingerprint`,
`reconcile` and `validate-evaluation` using JSON input files for structured arguments.

- [ ] Write failing tests for: ledger-only update preserves fingerprint; requirement/evaluation/
  binding change alters it; missing binding refuses; wrong round/code/agreement refuses; report
  committed on an unmerged branch is not integrated; duplicate matching reports conflict;
  a tracked integrated matching result is reusable; an untracked result is not success.

```python
def test_missing_judgment_is_not_pass(self):
    result = validate_evaluation(self.report_with_only_commands,
                                 self.evaluation_with_j1,
                                 self.expected_identity)
    self.assertEqual(result["verdict"], "FAIL")
    self.assertIn("J1", result["missing_ids"])
```

- [ ] Run `python3 scripts/coding-loop-state-test.py -v` to observe those failures.
- [ ] Parse exact C/J IDs from evaluation tables, rejecting duplicate IDs or invalid result
  values. Check required J/AC table presence and report identity. Never regrade a J row in
  Python; this validator checks completeness/provenance and applies the declared verdict rule.
  Command-only legacy projects remain valid when their explicit contract has no J rows.
- [ ] Require integrated ledger/report agreement and the selected SHA to remain resolvable.
  Internal artifacts must be tracked on synced main; external artifacts must be committed in
  the vault's own synchronized repository. Dirty/unmerged output triggers reconciliation or
  a parked conflict; do not discard/stash it automatically.
- [ ] Run tests to PASS; commit only the two helper/test paths as
  `feat(coding-loop): validate agreement and round evidence`.

## Task 3: Diagnosis skill and fail-closed report contract

**Files:** Create `skills/superdiagnose/SKILL.md`, `templates/coding-loop-diagnosis.md`,
`scripts/coding-loop-diagnosis-test.py`; extend `_coding_loop_evidence.py`.
**Owns:** S3-AC5/S3-AC6. **Consumes:** Task 2 identity and report validation.
**Produces:** `superdiagnose PROJECT --round N --eval-report PATH [--operation PATH]` and
`validate_diagnosis(path: Path, expected: dict) -> dict` in the evidence helper.

- [ ] Add deterministic report validation cases with actual Markdown fixtures: omitted failing
  check, absent source revision, mixed author/repair causes, unsupported classification, and
  wrong selected report. Validate structured fields independently of model prose.

```python
def test_mixed_spec_and_code_causes_require_author(self):
    result = validate_diagnosis(self.mixed_report, self.expected_identity)
    self.assertEqual(result["disposition"], "AUTHOR INPUT")
    self.assertFalse(result["may_start_next_round"])
```

- [ ] Run `python3 scripts/coding-loop-diagnosis-test.py -v` and confirm failures.
- [ ] Write the exact template fields: Date, Status FINAL, Round, Operation, Eval report,
  Evaluated commit, Agreement revision; sections `Inputs and limitations`, `Problems`,
  `Repair guidance`, `Disposition`. Problem table columns are Problem, C/J IDs, AC IDs,
  Evidence, Cause, Confidence, Classification. Accepted classes are `implementation defect`,
  `plan gap`, `PRD/evaluation defect`, `execution/evidence failure`. Disposition is REPAIR or
  AUTHOR INPUT; any of the latter two classes forces AUTHOR INPUT. Every failed/missing check
  must be accounted for. Absence of a reliable classification also forces AUTHOR INPUT.
- [ ] Write the skill as a single DIAGNOSER worker, not a worker that dispatches itself. Resolve
  full sources before diagnosis, inspect the selected code and round artifacts, distinguish
  weak assertion evidence from product behavior, keep suggestions nonbinding, and forbid
  product/spec repair. Preserve legacy explicit acceptance semantics.
- [ ] Specify external-vault direct commit/internal-vault PR discipline, exact report targeting
  and reuse of an already integrated matching operation. Return report path, commit and
  disposition. Unavailable inputs return an explicit evidence-failure outcome, never REPAIR.
- [ ] Add `--prompt` and `--answers FILE` modes to the test program, separate from unittest.
  Interpretation probes cover green existence-only assertions, true product defect, plan
  omission, contradictory spec and unavailable evaluator. Prompts omit expected answers;
  saved results must cite the skill rule. These modes are future live diagnostics, not proof
  from string matching that the model follows the skill.
- [ ] Run deterministic tests to PASS; commit `feat(coding-loop): add evidence-grounded diagnosis`.

## Task 4: Idempotent worker operations across meta, goal and evaluation

**Files:** Modify `skills/supermeta/SKILL.md`, `skills/supergoal/SKILL.md`,
`skills/supereval/SKILL.md`, `_coding_loop_evidence.py`, `coding-loop-state-test.py`.
**Owns:** S3-AC4/S3-AC6. **Consumes:** Tasks 1–3 operation and validation contracts.
**Produces:** optional `--operation PATH` on all three skills, retaining manual defaults.

- [ ] Write failure-boundary tests using real Git commits: meta moved but not committed;
  goal committed before ledger update; report committed before cursor update; identical
  operation replay; conflicting goal identity; partial output on an open PR. Assert exact
  counts of rounds, goals, reports and ledger rows after reconciliation.

```python
def test_integrated_goal_is_reused_after_cursor_crash(self):
    result = reconcile_operation(self.repo, self.vault, self.meta_operation)
    self.assertEqual(result["outcome"], "INTEGRATED")
    self.assertEqual(result["goal_folder"], self.committed_goal)
    self.assertEqual(self.count_goal_folders(), 1)
```

- [ ] Run state tests to observe missing reconciliation behavior.
- [ ] Under operation mode, freeze round, timestamp/output names and intended goal folder
  before PLANNER dispatch. Pass goal identity and source operation into supergoal; it must
  adopt only that identity, reuse verified existing scaffolding and never generate another
  timestamped goal on retry. Continue applying real source approval and scoped autoconfirm.
- [ ] Add an Operation metadata line only in operation mode. Manual invocation still derives
  the next round and normal output names. supermeta's existing round/source/AC propagation
  remains verbatim. A diagnosis for a later round must be validated REPAIR and match the
  previous failed report; missing repair context cannot be labeled “first round.”
- [ ] For supereval, operation mode uses the recorded selected SHA and exact report target;
  retain one EVALUATOR dispatch and command-result preservation. Extend validator metadata
  recognition without changing existing manual reports' required layout. Verify report and
  ledger commits before publishing phase completion. Commit or recover existing pending
  work through normal A7 rather than duplicate it.
- [ ] Run state, lint and runner regression tests:

```bash
python3 scripts/coding-loop-state-test.py -v
bash scripts/prd-lint-test.sh
bash scripts/supereval-test.sh
```

- [ ] Commit `feat(coding-loop): make round workers restartable` with only task-owned paths.

## Task 5: Project-aware launch, registration and parked gate

**Files:** Modify `scripts/launch.sh`, `install-timer.sh`, `superagent-tick.sh`, `_common.sh`;
create `scripts/coding-loop-driver-test.py`; extend `_coding_loop_state.py`.
**Owns:** S3-AC1/S3-AC2/S3-AC3 and lock-related S3-AC4/S3-AC7.
**Consumes:** Tasks 1–2; legacy scheduler helpers.
**Produces:** `launch.sh INPUT --supervisor superagent|supercode`; default superagent.
Registration stores `SUPERAGENT_SUPERVISOR`; state stores `supervisor`. Resolve absent values
as superagent and reject conflicting explicit identities. Installer accepts/forwards the
same flag; timer service/template behavior otherwise remains unchanged.

- [ ] Build fake executables in a temporary PATH for harness CLIs, gh, launchctl and systemctl.
  Log argv to JSONL files without real credentials; fake authenticated status only within
  these offline tests. Each scheduler adapter is tested independently. No test changes HOME
  or accesses host registrations; set XDG_CONFIG_HOME and adapter-specific task directories.
  If existing launchd path helpers lack an isolation seam, add an explicit test path override
  whose default remains the real existing path.
- [ ] Add tests executing real scripts: default goal behavior, invalid supervisor, conflicting
  identities, spaces in project paths, external vault, linked worktree, duplicate slug,
  idempotent same-project launch, no Python on legacy path, missing Python on project path,
  and all inner-status gate outcomes.

```python
def test_building_does_not_start_model(self):
    self.write_outer(status="BUILDING", inner=self.running_inner)
    before = self.model_invocations()
    self.invoke_tick()
    self.assertEqual(self.model_invocations(), before)
    self.assertEqual(self.outer_status(), "BUILDING")
```

The driver-test class defines `write_outer`, `model_invocations`, `invoke_tick` and
`outer_status` as fixture helpers over actual files/scripts. The fake model log must be
written by the invoked fake CLI, not synthesized by the test assertion.

- [ ] Run `python3 scripts/coding-loop-driver-test.py -v` and observe failures.
- [ ] Branch launcher input handling by validated supervisor. Project mode resolves physical
  roots, checks READY/lint/own-vault, validates max rounds, rejects registration collisions,
  initializes round 1 and WAITING FOR META-PLAN only for an empty project ledger. For an
  existing ledger reconcile its current round and artifacts; never reset it to round 1.
- [ ] Implement a Python `building_gate(state: dict, inner: dict, registration: dict) -> dict`
  returning `action` SKIP/EVALUATE/INPUT, `reason`, and verified identities. Shell obtains
  authoritative inner registration/status, invokes the pure decision helper, then acquires
  L3 lock and re-reads before any update. Do not source arbitrary state as shell. Check both
  registered REPO and expected inner master plan/goal and round. Active/queued/pending inner
  work skips; verified inner DONE permits EVALUATE; missing/malformed/mismatched identities
  park INPUT; disarmed unfinished work stays visible and never auto-rearms.
- [ ] Preserve default tick path and use selected skill path for each harness. Extend
  transient exit=10 detection to META-PLANNING/EVALUATING/DIAGNOSING with live-peer protection.
  Read-only parked gates must run before auth/model startup when no external query is needed.
- [ ] Run driver/state tests to PASS plus `bash -n` on the four changed shell files; commit
  `feat(coding-loop): launch project supervisors and gate inner builds`.

## Task 6: Outer supervisor and lifecycle controls

**Files:** Create `skills/supercode/SKILL.md`, `skills/supercode-external/SKILL.md`;
modify `skills/superloop/SKILL.md`, `scripts/status.sh`, `stop.sh`, `force-stop.sh`,
`_coding_loop_state.py`, `coding-loop-driver-test.py`, three monitor/stop skill docs.
**Owns:** S3-AC4/S3-AC6/S3-AC7 and completion of S3-AC1–S3-AC3.
**Consumes:** All preceding interfaces.

- [ ] Add actual script tests for outer slug/project resolution, independently stopping the
  outer while the inner runs, stopping a selected inner only, force recovery phase mapping,
  pending answers, lock contention, final-round PASS and refusal to create round max+1.
  JSON monitor output must retain legacy fields and add `supervisor`, `project`, `round`,
  `inner_slug`, `inner_status`, `last_verdict`, `pending_owner`.
- [ ] Run driver tests to observe missing behavior.
- [ ] Write the supervisor algorithm with exactly this tick order:

```text
resolve consumer identity and physical roots
acquire existing L3 lock; reload state
consume/validate any operator answer; preserve unadopted agreement changes
apply sync and acceptance-context gates
reconcile operation outputs; recover transient to ready only after reconciliation
switch status:
  WAITING FOR META-PLAN -> reserve operation -> META-PLANNING -> one META_PLANNER
  WAITING FOR BUILD -> record expected inner identity -> idempotent inner launch
  BUILDING -> use gate outcome only; no model work for a waiting inner
  WAITING FOR EVAL -> freeze SHA -> EVALUATING -> supereval with one EVALUATOR
  WAITING FOR DIAGNOSIS -> DIAGNOSING -> one DIAGNOSER
verify returned artifacts are integrated and identities still match
advance one phase or park with reason; append receipt and release lock
```

- [ ] Define phase results precisely: integrated meta/goal/ledger → WAITING FOR BUILD;
  verified registration → BUILDING; verified evaluation PASS → DONE; FAIL → WAITING FOR
  DIAGNOSIS; REPAIR diagnosis and round below limit → round+1 WAITING FOR META-PLAN;
  other diagnosis or exhausted limit → WAITING FOR INPUT. A raised limit resumes only after
  explicit recorded answer. Changed agreement needs author adoption with its new fingerprint,
  then a new planning round; never reuse an old PASS against new criteria.
- [ ] Generalize only superloop's consumer input/location and recovery seams; retain its
  plan-tree consumer defaults. Shared L7 may resolve routine operation failures but cannot
  approve specification changes. Use installed harness markers for META_PLANNER/DIAGNOSER
  dispatch; do not recursively invoke the same worker role.
- [ ] Add project-aware monitor/stop/force-stop interfaces as in the approved spec. Outer stop
  must print remaining child registration and exact child stop command. Never cascade unless
  a user explicitly invokes both operations. Resolve custom slugs via registered identity,
  not a guessed basename. Unknown/mismatched target refuses mutation.
- [ ] Run driver/state tests, `bash -n` for changed shell files and the existing offline
  regressions affected by shared paths (`bash scripts/vault-external-test.sh`). Commit
  `feat(coding-loop): supervise repair rounds and expose lifecycle controls`.

## Task 7: Package integration and deterministic full-loop acceptance

**Files:** Modify three build scripts, `scripts/coding-loop-package-test.sh`,
`templates/superenv.default`, `skills/init/SKILL.md`, `README.md`, `scripts/README.md`;
extend driver/state tests; regenerate `codex/`, `cursor/`, `pi/`.
**Owns:** S3-AC12 and combined deterministic S3-AC1–S3-AC7.

- [ ] Extend copied-package tests to import/invoke both new Python helpers and diagnosis
  template from the copied package with no source-checkout fallback. Assert all three new
  skills exist, native markers resolve correctly and no supervisor prompt hardcodes the
  wrong harness/consumer. Extend copying lists for every generated package that references
  a helper. Scheduler scripts remain source-repository infrastructure as currently documented.
- [ ] Run `bash scripts/coding-loop-package-test.sh` to confirm missing packaging fails.
- [ ] Regenerate from canonical sources; never hand-edit installed cache/generated skills.
  Document Python 3.9 project-only preflight, active SUPER_CODE_MAX_ITERATIONS semantics,
  native supervisor restriction, independent child stop behavior and author-only resume.
  Keep version 0.8.1 until the release gate; describe Stage 3 as under acceptance.
- [ ] Add complete fake-driver scenarios: real tick + fake worker commits + registration
  events traverse FAIL/diagnosis/repair/PASS; assert no second goal/report on replay. Inject
  failure before/after phase commits, before/after registration, stale lock-owner death,
  live-peer overlap and stale pre-lock inner state. Assert no silent DONE or lost input.
  These are deterministic transport tests, not live model or scheduler acceptance.
- [ ] Run once after final changes:

```bash
python3 scripts/coding-loop-state-test.py -v
python3 scripts/coding-loop-diagnosis-test.py -v
python3 scripts/coding-loop-driver-test.py -v
bash scripts/prd-lint-test.sh
bash scripts/supereval-test.sh
bash scripts/vault-external-test.sh
bash scripts/coding-loop-package-test.sh
bash scripts/build-codex-skills.sh --check
bash scripts/build-cursor-skills.sh --check
bash scripts/build-pi-skills.sh --check
git diff --check
```

- [ ] Inspect exact staged paths and commit `feat(coding-loop): package and verify Stage 3`.
  Run builds in the isolated clean worktree so the primary cachebuster is neither overwritten
  nor misreported as generated parity failure.

## Task 8: Live acceptance harness with bounded execution and honest evidence

**Files:** Create `scripts/coding-loop-stage3-live.py`,
`scripts/coding-loop-stage3-live-test.py`; document CLI in `scripts/README.md`.
**Owns:** Execution infrastructure for S3-AC8–S3-AC11; this task alone earns no live PASS.
**Produces:**

```text
python3 scripts/coding-loop-stage3-live.py prepare --manifest FILE
python3 scripts/coding-loop-stage3-live.py run --manifest FILE --harness claude|codex|pi
python3 scripts/coding-loop-stage3-live.py collect --manifest FILE --harness claude|codex|pi
python3 scripts/coding-loop-stage3-live.py cleanup --manifest FILE --harness claude|codex|pi
```

- [ ] Write fake-process tests for missing approval, manifest hash mismatch, unlisted root or
  remote, wrong harness, missing runtime receipts, dispatched role limit, elapsed timeout,
  exceeded retries, first evaluation unexpectedly PASS, changed agreement, controller-written
  repair, wrong SHA, and cleanup failure. Assert statuses distinguish PASS, FAIL, INVALID and
  INCOMPLETE; none of the latter three count as acceptance.

```python
def test_unexpected_first_pass_is_invalid(self):
    result = self.collect_with_reports(first="PASS", second=None)
    self.assertEqual(result["status"], "INVALID")
    self.assertFalse(result["acceptance_passed"])
```

- [ ] Run `python3 scripts/coding-loop-stage3-live-test.py -v` and confirm failures.
- [ ] Validate manifest schema with required fields: protocol version, immutable agreement
  paths/hashes, actual approval receipt/hash, selected baseline SHA, first-failure mechanism,
  code/vault roots and remotes per harness, outer/inner slug prefixes, supervisor/role model
  and effort pins, max rounds, max dispatches, per-dispatch/total seconds, retries, evidence
  directory and cleanup ownership. Forbid secret values in the manifest; use auth references.
- [ ] Use Python subprocess argv arrays; never interpolate manifest content into shell code.
  Scope all file/registration/process mutations to declared identities. Preflight installed
  package versions, CLI availability, auth, GNU timeout/gtimeout and real scheduler before
  arming. A missing timeout fails a bounded run rather than quietly making it unlimited.
- [ ] The harness records event/runtime receipts and actual state transitions, waits on
  process completion or bounded scheduler observation without repeated paid model calls,
  enforces total deadline independently of supervisor progress, and stops only its owned
  outer/inner registrations on exhaustion. A root event listener supplies user updates.
- [ ] Collect full revision-specific command and judge results, failed report, diagnosis,
  planned repair, worker dispatch receipts, reviewed/merged code and final report/ledger.
  Record actual model/effort and usage only when exposed. Scrub credentials/private runtime
  content before archiving; retain failed attempts and protocol deviations.
- [ ] Keep two fixture modes distinct: deterministic fake tests may synthesize worker outputs;
  live runs may not. A live first-failure protocol must be selected and approved in Task 9.
  No hidden mutation between rounds and no reuse of synthetic author approval.
- [ ] Run harness tests to PASS and commit `test(coding-loop): add bounded live acceptance driver`.

## Task 9: Concrete live protocol, three-harness acceptance and release

**Files:** Create `docs/superpowers/specs/2026-09-09-coding-loop-stage3-live-protocol.md`,
run manifests under its report evidence directory, and
`docs/superpowers/reports/2026-09-09-coding-loop-stage3.md`; modify release manifests and
user docs only after acceptance. Use actual execution date in later evidence filenames.
**Owns:** S3-AC8/S3-AC9/S3-AC10/S3-AC11 and final S3-AC12 gate.
**Consumes:** Tasks 1–8 integrated and offline checks passing.

- [ ] Build a concrete disposable Python JSON-preservation project and agreement. Require
  ValueError on malformed JSON, unchanged preexisting destination bytes and an executed
  real-function test with before/after exact equality. Reject existence-only assertions;
  standard library only. Define full source paths, IDs, approval and fixed baseline hash.
- [ ] Present the first-failure mechanism for explicit review. Recommended protocol: adopt a
  disclosed preexisting round-one baseline at WAITING FOR EVAL, with a real recorded ledger
  entry, source/plan provenance and no claimed successful Stage 3 implementation or fabricated
  closeout. The baseline intentionally overwrites the destination before parsing. The real
  first supereval must FAIL; diagnosis and round-two planning/build/review/evaluation then run
  unattended. This exercises every outer phase, with planning/build exercised in the repair
  round; it does not claim the first defective baseline was produced by the new planner.
  Adoption must go through the launcher's existing-ledger reconciliation, not hidden cursor
  editing by the harness. If this cannot be represented truthfully by those interfaces,
  revise the protocol before approval; never fabricate an inner DONE record.
- [ ] Verify the fixture's failing behavior locally before any model run; record the exact
  failing command result as preflight evidence, not as the future supereval verdict. Build
  identical independent copies for Claude, Codex and Pi with distinct remotes and scheduler
  identities. Declare integration policy explicitly; normal reviewed GitHub integration is
  the default. A local-only exception would need separate approval and would limit the claim.
- [ ] Resolve current available models and role prerequisites for all three harnesses, record
  explicit native pins and run limits in complete manifests. Derive a reasonable finite
  budget from the number of actual required worker phases, including review roles; do not
  carry the prior seven-dispatch fixture's budget over to a larger scheduler test. Present
  manifests, any fixture adoption limitation, and total maximum spend/time exposure for
  approval. Do not arm any scheduler until actual approval is recorded against these bytes.
- [ ] Execute the approved manifests sequentially by harness, retaining every attempt. Native
  live acceptance is required on all three. A missing harness/auth/model or exceeded limit
  leaves its row INCOMPLETE; do not start unlimited retries or claim Stage 3 complete.
- [ ] For each harness verify real first FAIL, diagnosis with repair disposition, newly
  implemented/reviewed/integrated repair, second PASS, unchanged agreement, exact source
  revisions, no inter-round human orchestration and final timer/child cleanup. Collect
  evidence before deleting temporary worktrees or disposable scheduler artifacts.
- [ ] Write a per-harness matrix and map evidence to S3-AC1–S3-AC12. Distinguish deterministic
  tests, live native role evidence, scheduler OS and integration transport. Document that
  bounded acceptance is not a statistical reliability claim. A harness is PASS only when
  all its applicable rows and cleanup are verified.
- [ ] Only after all three live rows PASS, update canonical version to 0.9.0, regenerate
  package manifests, update README and the umbrella stage links/status. Rerun package and
  build-parity checks because release metadata changed. Review and merge release/report PR;
  inspect merged source and remote main. Preserve any unrelated installed cachebuster.

## Plan self-review and completion criteria

| Spec requirement | Task coverage |
|---|---|
| S3-AC1 legacy/default identity and lifecycle | 5, 6, 7 |
| S3-AC2 roots and idempotent project launch | 1, 5 |
| S3-AC3 parked BUILDING behavior | 5, 6, 7 |
| S3-AC4 recovery without duplicate artifacts | 1, 2, 4, 5, 6, 7 |
| S3-AC5 diagnosis distinctions and source scope | 2, 3, 4 |
| S3-AC6 fail-closed completion | 2, 3, 4, 6, 7 |
| S3-AC7 controls, locks and limits | 5, 6, 7, 8 |
| S3-AC8 Claude live acceptance | 8 infrastructure; 9 actual evidence |
| S3-AC9 Codex live acceptance | 8 infrastructure; 9 actual evidence |
| S3-AC10 Pi live acceptance | 8 infrastructure; 9 actual evidence |
| S3-AC11 preservation and cleanup | 8, 9 |
| S3-AC12 package parity | 7, 9 |

Self-review: dependency order and shared API names checked; no acceptance row is satisfied by
an implementer claim or a fake test alone. A proposed live protocol and its eventual author
approval are separate deliverables, not fabricated runtime inputs. First-round baseline
adoption must remain explicit in the acceptance report. Every task carries this Global
Constraints section and the full approved spec into implementation/review packets.
