# Git-free Operating Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make GitHub recommended rather than required, with `SUPER_GIT_MODE=none` preserving the Superagent lifecycle without git operations.

**Architecture:** Add one shared mode/project resolver, mode-aware skill contracts, owned workspace locks, and filesystem snapshot evidence. Keep GitHub execution as the backward-compatible default; generate all harness variants from canonical sources.

**Tech Stack:** Markdown skills, Bash 3.2, Python 3.9 standard library, existing shell test shims and package builders.

**Spec:** [Git-free operating mode](../specs/2026-09-17-git-free-mode-design.md). GF-01–GF-10 and the behavioral sections are binding. Read both documents before implementation.

## Global constraints

- Planning only in the current session; do not implement from this document without an execution request.
- `SUPER_GIT_MODE=github` is the default; accepted values are exactly `github` and `none`.
- Preserve environment > `.superenv` > packaged-default precedence, Bash 3.2, and Python 3.9.
- No Superagent-managed git/gh/GitHub API or token lookup in `none`, including read-only probes.
- No worktrees, automatic rollback, automatic mode migration, or weakening acceptance/review gates.
- Preserve top-level executor isolation and inherited harness/model/effort choices.
- Canonical `skills/`, `templates/`, and `scripts/` are authoritative; regenerate distributed files.
- Preserve existing user changes. README, default templates, builders, and the Codex manifest are
  already modified; upfront-planning documents and historical reports are also present.
- At execution, isolate changes and deliberately carry relevant existing template/builder edits;
  do not reset the worktree or overwrite the Codex cachebuster. Stage explicit task-owned files.
- No dependency on unmerged Stage 3 or upfront-planning code. If those land first, reconcile their
  new persistence/dispatch paths with this mode and record the changed baseline.

## Delivery sequence and file ownership

| Task | Deliverable | Depends on | Acceptance |
|---|---|---|---|
| 1 | Effective mode and git-free project discovery | none | GF-01/02/08/10 |
| 2 | Workspace ownership and reproducible snapshots | 1 | GF-06/07 |
| 3 | Init, lifecycle scripts, and harness transport | 1–2 | GF-02/03/06/08 |
| 4 | Local authoring, execution, repair, completion | 1–3 | GF-04/05/08 |
| 5 | Snapshot evaluation and coding-loop artifacts | 2/4 | GF-07/08 |
| 6 | Generated packages, documentation, acceptance | 1–5 | GF-01–10 |

| File(s) | Responsibility |
|---|---|
| `scripts/_common.sh` | Shared context/mode validation and conditional GitHub authentication |
| `scripts/workspace-state.py` (new) | Owned locks, snapshots, manifests, content comparison, safe cleanup |
| `scripts/git-mode-test.sh` (new) | Offline resolver, script, lock integration, and forbidden-command tests |
| `scripts/workspace-state-test.py` (new) | Snapshot and lock behavior tests using subprocesses/temp directories |
| `scripts/git-mode-regression.py` (new) | Skill interpretation scenarios and exact answer validation |
| `scripts/git-mode-smoke.py` (new) | Real harness lifecycle fixture and independent artifact/evidence verification |
| `templates/superenv.default`, `templates/vault-root.md` | Public setting and local-vault explanation |
| `skills/init/SKILL.md` | Mode selection, non-repository setup, local vault and runtime state |
| `skills/superloop/SKILL.md` | Shared mode, project ownership, persistence, mode-mismatch, L5/L6 rules |
| All other canonical `skills/*/SKILL.md` | Shared config lookup and applicable local behavior |
| `scripts/bootstrap.sh`, `launch.sh`, `install-timer.sh`, `superagent-tick.sh` | Resolve context before auth, export it, mode-aware startup/tick |
| `scripts/status.sh`, `stop.sh`, `force-stop.sh`, `answer.sh`, `console-watch.sh` | Per-loop mode and ownership; no implicit GitHub probes |
| `scripts/role-bridge.sh`, `templates/relay-preamble.md` | Carry explicit workspace/mode/lock context into nested execution |
| `scripts/prd-lint.sh`, `supereval.sh`, `supereval-test.sh` | Local project discovery and evaluation source abstraction |
| `scripts/lifecycle-regression.py`, `vault-external-test.sh`, `bridge-test.sh` | Existing behavior regression coverage |
| `scripts/build-codex-skills.sh`, `build-cursor-skills.sh`, `build-pi-skills.sh` | Ship helpers and mode-correct compatibility headers |
| `scripts/coding-loop-package-test.sh` | Run new tests against standalone distributable packages |
| `README.md`, `scripts/README.md`, generated harness READMEs | GitHub recommended/local setup and operational limits |

## Task 1: Resolve mode and project without requiring git

**Files:** `_common.sh`, defaults, new `git-mode-test.sh`.

**Interfaces:** Add these functions to `_common.sh`; messages go to stderr.

```bash
# Validate effective config; success 0, configuration error 2.
superagent_validate_git_mode
# Set/export REPO (physical path) and loaded SUPER_* values in the current shell.
# purpose is run|init. Explicit REPO takes precedence over discovery.
superagent_load_context START_DIR PURPOSE
# Return 0 iff validated mode is github; do not discover/load configuration here.
superagent_uses_git
```

- [x] Add failing shell cases for default GitHub, environment precedence, invalid/empty mode,
  `none` plus CI evidence, nearest config, explicit root, symlink paths, spaces, nested directories,
  local init without config, local run without root/config, and GitHub linked-worktree primary config.
  Use real temporary git repos only to construct GitHub fixtures before enabling sentinels.
- [x] Define the forbidden-command fixture with log-writing `git` and `gh` executables returning
  97. This must fail if a caller tries a command and swallows its status. Representative assertion:

```bash
SUPER_GIT_MODE=none SUPER_TEST_EVIDENCE=local REPO="$fixture" \
  bash -c '. "$1/scripts/_common.sh"; superagent_load_context "$PWD" run;
           test "$SUPER_GIT_MODE" = none' _ "$ROOT"
test ! -s "$forbidden_log"
```

- [x] Implement resolver ordering from the spec. Do not call `git rev-parse` in a default-valued
  shell expansion before loading mode. Use an ancestor loop on physical directories for config
  discovery, then permit git fallback only for the GitHub branch. Keep primary-worktree config
  behavior in that branch. Loading candidate config cannot permanently shadow environment values
  when reloading primary config; snapshot caller overrides separately from loader-produced values.
- [x] Add validation before side effects and the public default with explanatory comments:

```bash
case "${SUPER_GIT_MODE-}" in
  github|none) ;;
  *) echo 'superagent: SUPER_GIT_MODE must be github|none' >&2; return 2 ;;
esac
if [ "$SUPER_GIT_MODE" = none ] && [ "${SUPER_TEST_EVIDENCE:-local}" = ci ]; then
  echo 'superagent: SUPER_GIT_MODE=none requires local test evidence' >&2
  return 2
fi
```

- [x] Gate `ensure_gh_auth` before `_superagent_load_gh_token`; audit direct token-helper callers.
  Keep GitHub auth failure behavior intact. Run `bash scripts/git-mode-test.sh` and
  `bash scripts/vault-external-test.sh`; record baseline failure then passing results. Commit this
  unit with explicit paths when executing the plan.

## Task 2: Lock shared workspaces and capture filesystem evidence

**Files:** New `workspace-state.py`, `workspace-state-test.py`; integrate helpers through `_common.sh`.

**Interfaces:** Python CLI with JSON stdout, diagnostics stderr, exits 0 success, 2 invalid input,
3 busy lock, 4 changed/inconsistent source. No git invocation or third-party modules.

```text
workspace-state.py run --root PATH [--root PATH] -- COMMAND [ARG...]
workspace-state.py acquire --root PATH --owner-pid PID --token TOKEN --operation TEXT
workspace-state.py release --root PATH --token TOKEN
workspace-state.py snapshot --root PATH --vault PATH --out-parent PATH
workspace-state.py compare --before MANIFEST --after MANIFEST
workspace-state.py cleanup --workspace PATH --token TOKEN
```

`run` canonicalizes/sorts roots, acquires all locks, supervises a process group, exports
`SUPER_WORKSPACE_TOKEN` and `SUPER_WORKSPACE_OWNER_PID`, and releases owned locks after children
exit. It forwards termination and returns the child status. Nested callers must validate token,
root membership, and live owner before borrowing ownership. Direct interactive skill execution
uses a demonstrably live session owner or executes the mutating operation through `run`; never
use a PID from a short-lived shell that exits before the work.

`snapshot` returns `workspace`, `manifest`, `source_id`, and `token`. Manifest schema is
`schema: 1`, physical `source_root`, `excluded_paths`, and sorted `entries`; each entry has `path`,
`kind`, `mode`, and `sha256` or `target`. The source digest covers canonical entries, not absolute
temporary paths or timestamps. `compare` returns `added`, `modified`, and `deleted` path lists.

- [x] Add executable unittest cases, including two real concurrent processes, before helper code:

```python
def test_local_snapshot_identity(self):
    first = self.snapshot()
    second = self.snapshot()
    self.assertEqual(first['source_id'], second['source_id'])
    (self.project / 'app.txt').write_text('changed\n')
    self.assertNotEqual(first['source_id'], self.snapshot()['source_id'])

def test_live_owner_cannot_be_stolen(self):
    with self.writer() as owner:
        peer = self.run_writer(check=False)
        self.assertEqual(peer.returncode, 3)
        self.assertTrue(owner.is_alive())
```

Define `snapshot()`, `writer()`, and `run_writer()` as test helpers invoking the CLI with
`subprocess`, temporary project/vault directories, and sentinel executables. Cover inherited
ownership, foreign-token release, reversed shared-vault acquisition order, dead owner with live
child, owner termination, partial lock acquisition cleanup, and ambiguous owner metadata.
- [x] Implement locks using atomic `mkdir`, token-bearing owner records, and the spec's fixed
  lock order. Never reap a live/ambiguous writer using only the existing age threshold. Keep lock
  contention separate from task failure, and do not let `force-stop` release a peer's lock.
- [x] Implement snapshot walking/copying with `pathlib`, `shutil`, `stat`, `hashlib`, and `json`.
  Follow the spec's exclusion and symlink policy; reject unsafe destinations nested under source
  or vault. Compare source manifests before/after and captured bytes. On error preserve diagnostics
  and remove only helper-owned partial output. Add a deterministic test hook via injected Python
  copy callback in unit tests to simulate source mutation; no production sleep/race tests.
- [x] Test additions/deletions, executable-bit changes, stable ordering, secret exclusions,
  internal vault/runtime exclusion, external symlink rejection, non-ASCII/spaced paths, setup
  modifying only the snapshot, invalid cleanup tokens, and refusal to clean source/home/root.
- [x] Run `python3 scripts/workspace-state-test.py` and the shell suite. Commit the verified unit.

## Task 3: Local initialization and scheduler lifecycle

**Files:** Lifecycle scripts and init skill listed in the ownership table; relay template/bridge.
**Consumes:** Task 1 context functions and Task 2 ownership interface.
**Produces:** Registered `project_root`/`git_mode`, inherited mode/ownership, git-free control plane.

- [x] Extend shell tests with fake harnesses and fake launchctl/systemctl; use isolated registry
  directories. Exercise bootstrap, launch dry-run and launch, tick, status JSON/text, answer,
  stop, force-stop inspection/application, and shared-vault contention without real scheduler writes.
- [x] Replace eager git root expressions with shared context resolution in all entry points;
  load registered root for slug-based lifecycle operations. Refactor `status.sh`'s host-wide
  GitHub probe into per-row behavior: local rows show `gh_auth: disabled`; all-local inventory
  never loads a token. Mixed inventories may query GitHub solely for GitHub rows.
- [x] Add init's GitHub/local selection, normal-directory vault setup, and runtime directory.
  Skip gitignore/exclude setup in `none`. Update every canonical skill's configuration lookup to
  call the shared resolver; no leftover unconditional `git-common-dir` recipe on a local path.
- [x] Load/compare recorded mode before auth and CI gates. An old unmarked loop is GitHub.
  Mismatches park/report per the spec without querying pending PRs. Do not reinterpret old CI
  packets as local success. Retain mode/root through fresh ticks and external-vault registration.
  Store recorded mode separately from the effective `SUPER_GIT_MODE` environment override: an
  automatically persisted default must not hide subsequent `.superenv` changes. Explicit caller
  environment overrides retain their documented precedence. For host-wide status, resolve each
  row in a subshell so one project's loaded values cannot become another project's overrides.
- [x] Wrap mutating local tick/bootstrap work with Task 2 ownership; preserve L3 as the inner
  lock and inherited ownership across role bridges. Ensure idle input/DONE polls and control
  commands can run without taking a writer lock. Busy writers yield without state advancement.
- [x] Add Codex's existing bridge-supported `--skip-git-repo-check` to local supervisor invocation;
  preserve sandbox/model flags. Assert real argv from fake harness logs, not matching prose.
  Carry mode, physical root, and validated lock identity explicitly in relay context.
- [x] Update force-stop to omit worktree enumeration in local mode and release only proven-dead
  owned project/vault locks after terminating the supervised process group. Preserve logs/state.
- [x] Run shell tests, vault tests, and `bash scripts/bridge-test.sh`. Inspect forbidden-command
  logs and synthetic GitHub API/token-access logs; require zero local-mode accesses. Commit unit.

## Task 4: Local skill execution and evidence-backed completion

**Files:** `skills/superloop/SKILL.md`, superauthor, supergoal, superplan, superrun, superfinish,
supertraverse, superagent, superprd, supermeta; new `git-mode-regression.py`.
**Consumes:** Mode/root and ownership contracts; snapshot comparison.
**Produces:** Local publication, `completed-local` receipts, mode-aware C4/C7/C8/C9 and L5/L6.

- [x] Create scenario CLI patterned after `lifecycle-regression.py`: `--prompt`, `--answers FILE`,
  `--self-test`, `--skills PATH`, `--cases NAME...`. Validate exact selected case membership and
  nonempty evidence/reason strings. Self-tests verify malformed/missing/incorrect answers fail.
  Run interpretation checks on actual skill files; validator self-tests alone prove no behavior.

| Case | Required result |
|---|---|
| local complete leaf with passing evidence, reviews, no open obligations | `done: true` |
| status says completed-local but report or required test evidence missing | `done: false` |
| ancestor locally complete but active descendant failed | `done: false` |
| local implemented leaf whose review failed | `done: false` |
| delayed closeout belongs to predecessor | `overwrite_successor: false` |
| local repair persisted before crash, replay on fresh tick | no duplicate successor/reset |
| unmarked legacy goal and effective none | mode mismatch; no git/GitHub operations |
| local goal and effective github | mode mismatch; no merge claim |
| GitHub mode sees only completed-local receipt | not integrated |
| local instruction invokes SDD worktree/commit/finishing defaults | suppress git stages; retain review/test gates |

- [x] Add shared local clauses to superloop and link them from each consumer. Author mode/root
  markers in new root plans; standalone planning checks root identity before publication. A7 local
  writes/reopens explicit artifacts, reports paths, and performs no commit. Override duplicated
  recipes in superplan/superfinish as well as supergoal/superprd/supermeta callers.
- [x] In superrun branch before worktree entry. Specify local overrides to SDD and review prompts:

```text
Git mode: none. Work in the recorded project under inherited workspace ownership.
Do not invoke worktree, commit, PR, merge, or finishing-branch operations.
Use before/after manifests and file content diffs for review context.
Retain task reviews, final review, local tests, and acceptance verification.
Publish local closeout only after those gates pass.
```

- [x] Capture a before baseline, execute/review locally, and capture resulting evidence. Build
  closeout receipts with every field in the spec. Verify report files before publishing parent
  rows; a crash before parent update is resumable using leaf identity and receipt validation.
  Never automatically restore a baseline over the project or discard unrelated user changes.
- [x] Implement local status descent/rollup, durable repair replay, and final C9 checks. Replace
  tracked/merged proof with local receipt checks only in local branches. Preserve unresolved
  acceptance and repair blockers and existing GitHub/direct-merge proof rules.
- [x] Run new scenarios against canonical instructions, existing lifecycle scenarios unchanged,
  then repeat local cases against generated variants in Task 6. Record interpreter answers and
  exact validation commands. Commit the skill-contract unit after evidence review.

## Task 5: Evaluate snapshots and preserve coding-loop evidence

**Files:** `scripts/supereval.sh`, `supereval-test.sh`, `prd-lint.sh`; skills supereval, superprd,
supermeta, supercoverage; new local evaluation cases in git-mode tests.
**Consumes:** Snapshot API and local durable receipts.
**Produces:** Local snapshot evaluation, source identity in reports/ledger, safe workspace cleanup.

- [x] Add failing runner tests for local evaluation without `--commit`, rejection of GitHub-only
  flags, setup/command failure and timeout, judged-only workspace retention, and command writes
  leaving original source unchanged. Assert input manifests and output evidence, not only exit 0.
- [x] Parse mode before requiring `--commit`. Implement a workspace-kind branch:

```text
github: existing detached worktree / commit identity / git cleanup
none: owned filesystem snapshot / snapshot identity / token-checked cleanup
```

Keep existing GitHub CLI/report compatibility. Add `--keep-workspace` for local runs. For local
results emit `source: snapshot:<digest>`, `workspace: <path>`, `manifest: <path>`, and setup result;
never put a snapshot digest into a field claiming it is a git commit.
- [x] Update supereval's skill-side workspace extraction, evaluator packet, cleanup, and ledger
  writing to consume this branch. Freeze evaluation and acceptance inputs before command execution;
  both command and judged checks use the same captured source. Preserve runner exit code and
  acceptance-context failure semantics. Record post-command writes separately from source identity.
- [x] Update PRD lint's implicit root resolution. Audit ledger readers/templates in superprd,
  supermeta, supereval and builders for commit-only assumptions; introduce the `Source` label for
  new ledgers while accepting the old commit column when reading GitHub projects.
- [x] Test missing/excluded inputs explicitly fail, no git commands even on cleanup/error paths,
  deleted source files appear in comparisons, and generated snapshot outputs do not recursively
  enter the next snapshot. Run `bash scripts/supereval-test.sh`, `bash scripts/prd-lint-test.sh`,
  Python helper tests, and local shell cases. Commit the verified evaluation unit.

## Task 6: Package, document, and verify the complete workflow

**Files:** Builders, generated trees, package test, READMEs, new smoke runner; execution report
`docs/superpowers/reports/2026-09-17-git-free-mode-verification.md` created during implementation.
**Consumes:** All prior contracts; GF-01–GF-10.

- [x] Copy new runtime helpers into each distribution that consumes them. Amend compatibility
  headers that currently require `git worktree`; describe the local exception. Include Cursor in
  copied-package helper tests and verify no dependency on the source checkout's paths.
  Cursor currently ships only `role-bridge.sh`; explicitly add `_common.sh`, `_evalspec.sh`,
  `prd-lint.sh`, `supereval.sh`, and `workspace-state.py` there. Codex/Pi already copy the first
  four of those helpers and need the new Python helper. Test copied packages with the canonical
  checkout inaccessible, including shared context resolution from their generated skills.
- [x] Document GitHub as recommended, local setup in an ordinary folder, the one-key opt-in,
  external vault behavior, in-place editing/lock behavior, snapshot limitations, CI conflicts,
  mode mismatch recovery, and reports without PRs. Do not change this checkout's `.superenv`.
- [x] Regenerate in the isolated implementation checkout and check repeatability:

```bash
bash scripts/build-codex-skills.sh
bash scripts/build-cursor-skills.sh
bash scripts/build-pi-skills.sh
bash scripts/build-codex-skills.sh --check
bash scripts/build-cursor-skills.sh --check
bash scripts/build-pi-skills.sh --check
bash scripts/coding-loop-package-test.sh
bash scripts/git-mode-test.sh
python3 scripts/workspace-state-test.py
bash scripts/bridge-test.sh
bash scripts/vault-external-test.sh
bash scripts/prd-lint-test.sh
bash scripts/supereval-test.sh
```

Document pre-existing baseline failures separately, including local manifest cachebusters; do not
mask a new failure as pre-existing. Use `bash -n` on edited shell files and compile Python files
with bytecode output directed to a temporary directory.
- [x] Implement `git-mode-smoke.py --harness NAME --vault internal|external --run-dir PATH` using
  the subprocess/evidence conventions of `coding-loop-harness-smoke.py`. Its fixture is a normal
  directory with a two-leaf plan: create a small function and local test, then extend behavior.
  Seed a failing implementation/review case to exercise repair. Run init, plan, successive ticks,
  closeout, fresh-session resume, and snapshot command plus judged evaluation. Require independent
  inspection of real artifacts, execution/review receipts, local final test results, DONE audit,
  no `.git` created, and zero forbidden operations. A stubbed harness cannot prove skill execution.
- [x] Instrument git/gh commands, GitHub API requests in emitted tool calls, and credential-access
  paths. PATH sentinels alone are insufficient to catch absolute commands or HTTP alternatives.
  Preserve runtime transcripts and inspect actual executed calls; distinguish application/model
  networking from prohibited workflow operations. Fixtures themselves use no git requirements.
- [x] Run offline transport/packaging checks for all four harnesses. Run real lifecycle acceptance
  with each installed/authenticated supported harness and both vault modes; report any unavailable
  harness as an explicit coverage gap rather than a pass. Also run local mode inside a disposable
  existing git repo and verify git metadata bytes are unchanged. Existing GitHub regression suites
  must still pass; do not create remote repos merely to run this local acceptance fixture.
- [x] Complete GF-01–GF-10 traceability in the report: command, environment, result, evidence path,
  interpretation versus real execution, and remaining limits. Review the generated diff and
  commit only feature-owned paths. No release/version bump or external publication is implied.

## Planning self-review

- GF-01/02 map to Tasks 1 and 3; GF-03 to 3; GF-04/05 to 4; GF-06 to 2/3;
  GF-07 to 2/5; GF-08 to 1/3/4/5; GF-09 to 6; GF-10 to 1/4/6.
- Configuration discovery precedes git/auth; status, force-stop, and Codex startup are included.
- Both duplicated persistence recipes and downstream SDD assumptions receive explicit overrides.
- Root/loop mode markers prevent silent migration; local completion cannot masquerade as merge proof.
- Lock ownership spans nested executors and shared vaults; snapshot evidence handles mutation,
  deletions, executable modes, exclusions, and cleanup without Git.
- Tests distinguish shell transport, interpreted skill contracts, and real lifecycle execution.
- This plan does not execute itself or supersede the separate upfront-plan-tree initiative.
