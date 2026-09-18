# Git-free operating mode verification

**Date:** 2026-09-17
**Implementation branch:** `feat-git-free-mode`
**Implementation worktree:** `/Users/eugene/src/superagent-plugin/.claude/worktrees/git-free-mode`
**Base:** `45122c2` (`main` when the worktree was created)

## Result

`SUPER_GIT_MODE=none` now carries the Superagent planning, execution, review, repair, closeout,
supervision, and evaluation lifecycle without Superagent-managed git, GitHub, credential, worktree,
commit, PR, merge, sync, or CI operations. An absent setting still resolves to `github`.

The deterministic suites and copied-package checks passed. Real Codex 0.154.0 and Pi 0.84.4 runs
completed with both internal and external vaults. All four reached `DONE`, retained two local
receipts, passed final tests and filesystem snapshots, and produced passing command and judged
evaluation evidence. The compact results are checked in below; full transcripts remain in their
`/private/tmp/git-free-smoke-*` run directories.

## Evidence classes

The following terms are used deliberately:

- **Real deterministic execution** means the repository's shell or Python code ran in a disposable
  filesystem fixture. Fake CLIs/schedulers isolate transport, so these tests prove program behavior
  but do not prove a model followed a skill.
- **Interpreted skill check** means a fresh Codex session read the named skill tree and answered the
  independent scenarios. The validator proves the answer matched the expected contract. It does not
  prove lifecycle transport.
- **Real harness execution** means the installed authenticated CLI read a copied package, invoked the
  actual skills and nested roles, mutated a disposable ordinary project, ran tests/reviews, and left
  inspectable receipts/transcripts. No stubbed harness is counted in this class.

## Deterministic and interpreted verification

| Check | Result | Evidence kind | Evidence |
|---|---:|---|---|
| `build-{codex,cursor,pi}-skills.sh` followed by all three `--check` runs | PASS | real deterministic execution | generated trees under `codex/`, `cursor/`, and `pi/`; each check reported up to date |
| `bash scripts/coding-loop-package-test.sh` | PASS | real deterministic execution with fake transports | canonical, Codex, Cursor, and Pi copied packages ran outside the source checkout; Stage 1/2 helpers passed for all four and the generated packages passed the Stage 3 isolation checks |
| `bash scripts/git-mode-test.sh` | PASS, 0 failures | real deterministic execution | default/precedence, nested discovery, owned local bootstrap, shared external-vault contention, mixed local/GitHub status isolation, controls invoked outside the project by slug, busy-lock yield, mode mismatch, zero local git/gh calls, and unchanged bytes in a pre-existing `.git` directory |
| `python3 scripts/workspace-state-test.py` | PASS, 18 tests | real deterministic execution | ownership, inherited locks, shared-vault exclusion, dead-owner recovery, snapshot identity/copy/change/deletion/mode/symlink rules, exclusions, and tokenized cleanup |
| `bash scripts/bridge-test.sh` | PASS, 0 failures | real deterministic execution with fake CLIs | harness argv, model/effort/tool mapping, fanout, lifecycle helpers, and direct-mode regressions |
| `bash scripts/vault-external-test.sh` | PASS, 0 failures | real deterministic execution | legacy GitHub internal/external vault resolution, launch, stop/force-stop, and ignore routing |
| `bash scripts/prd-lint-test.sh` | PASS, 0 failures | real deterministic execution | local implicit root resolution plus existing lint matrix |
| `bash scripts/supereval-test.sh` | PASS, 14 cases | real deterministic execution | local snapshots, source preservation, manifest diffs, failure/timeout/setup evidence, retention/cleanup, exclusions, and zero local git calls |
| `python3 scripts/git-mode-regression.py --self-test` | PASS, 6 tests | validator self-test | malformed/missing/extra/wrong answer cases fail and the valid fixture passes |
| fresh `git-mode-regression.py` prompts against canonical, Codex, Cursor, and Pi skill trees | PASS, 10 scenarios each | interpreted skill checks | [canonical](evidence/2026-09-17-git-free-mode/git-mode-canonical-answers.json), [Codex](evidence/2026-09-17-git-free-mode/git-mode-codex-answers.json), [Cursor](evidence/2026-09-17-git-free-mode/git-mode-cursor-answers.json), [Pi](evidence/2026-09-17-git-free-mode/git-mode-pi-answers.json) |
| fresh `lifecycle-regression.py` prompt against canonical skills | PASS, 16 scenarios | interpreted skill check | [lifecycle answers](evidence/2026-09-17-git-free-mode/lifecycle-answers.json) |
| `bash -n` on every `*.sh`; `compileall` on canonical/generated Python; `git diff --check` | PASS | real syntax/static execution | working tree at report time |

The copied-package test is the offline transport/packaging matrix for all four distributions. The
fresh model probes are recorded separately because matching static scenario answers does not turn an
offline package test into real harness execution.

## Integration with current main

Before PR publication, `origin/main` had advanced to `75ebd5d` (`v0.9.0`) with the Stage 3 coding
loop and upfront plan-tree lifecycle. That base was merged into the isolated implementation branch.
Conflict resolution preserved Stage 3's literal-data registry and systemd adapter, upfront planning
selection, coding-loop phase identity, and generated helpers while applying git-free mode before any
shared git/GitHub path. `supercode` remains a GitHub-mode supervisor and now refuses local-mode launch
before invoking git or GitHub; ordinary `superagent` local lifecycle behavior is unchanged.

The reconciled tree passed these additional real deterministic suites:

- `coding-loop-state-test.py -v`: 63 tests.
- `coding-loop-diagnosis-test.py -v`: 12 tests.
- `coding-loop-driver-test.py -v`: 71 tests, including copied packages and scheduler adapters.
- `coding-loop-stage3-live-test.py -v`: 41 tests. The sandboxed run passed 38 and could not invoke
  `ps` for three process-ownership cases; the authorized process-inspection rerun passed all 41.
- `plan-tree-config-test.sh`: 0 failures; `plan-tree-e2e.py --self-test`: 61 tests.

The four real harness runs below predate this current-main reconciliation and were not repeated. They
remain direct evidence for the git-free lifecycle itself; the post-merge evidence above is
deterministic integration coverage of the shared Stage 3 and upfront-plan paths.

## Real harness execution

### Codex, internal vault: PASS

Command (initial phase, then retained recovery):

```text
python3 scripts/git-mode-smoke.py --harness codex --vault internal \
  --run-dir /private/tmp/git-free-smoke-codex-internal-r2 --timeout 1200 --max-ticks 14
python3 scripts/git-mode-smoke.py --harness codex --vault internal \
  --run-dir /private/tmp/git-free-smoke-codex-internal-r2 --timeout 3600 --max-ticks 12 --resume
```

Environment: macOS, Codex CLI 0.154.0, `gpt-5.6-sol` at medium effort, copied generated plugin,
ordinary directory with no `.git`, relative internal `vault`, and PATH sentinels for git/gh and
credential tools.

The first process was intentionally terminated by its per-phase timeout after the second leaf had
written source/test changes but before it published completion evidence. The retained loop was
`RUNNING`. The resumed fresh process recovered the ownership state, refused to invent the missing
GREEN-to-RED history, wrote a blocked closeout, obtained a 3/3 re-plan decision, published and ran a
repair successor, and reached `DONE` at iteration 8. This is real crash-recovery evidence, not a
mocked state transition.

Independent runner checks found two `completed-local` receipts, passing final tests, a stable
`snapshot:eb02a481b36effb73b775a7e493e23aea2e2c9f5d7e0466c71caa4c87a78f77e`, zero source changes
during evaluation, `C1 PASS`, `J1 PASS`, a final eval verdict of `PASS`, no project/vault `.git`,
421 inspected structured tool-call payloads, zero forbidden emitted calls, and zero non-git sentinel
calls. Key paths are in the checked-in compact result; raw prompts, JSONL transcripts, stderr,
receipts, manifests, snapshot, and eval report remain under the run directory.

An earlier preflight attempt at `/private/tmp/git-free-smoke-codex-internal` exposed a smoke-runner
classification defect: Codex startup/plugin discovery calls hit the git sentinel and the first
runner version counted them as Superagent workflow calls. The corrected runner scans structured
emitted tool calls independently and retains process-level startup probes in
`runtime-git-probes.json`. The passing run recorded 35 such Codex runtime probes (14 plugin
`ls-remote`, 15 `remote -v`, 6 `rev-parse --git-dir`), all intercepted by the sentinel. They are
real CLI/runtime behavior and are not claimed as zero host git activity; no Superagent-emitted git,
GitHub, or credential operation appeared in the structured transcripts.

The first external-vault setup attempts at `/private/tmp/git-free-smoke-codex-external` and
`/private/tmp/git-free-smoke-pi-external` stopped before lifecycle execution because the runner wrote
the vault path containing a space to `.superenv` without shell quoting. The runner now uses
`shlex.quote`; the corrected retained runs use the `-r2` directories. Those first attempts are test
harness failures and are not counted as product passes or failures.

### Pi, internal vault: PASS

Command:

```text
python3 scripts/git-mode-smoke.py --harness pi --vault internal \
  --run-dir /private/tmp/git-free-smoke-pi-internal --timeout 3600 --max-ticks 14
```

Environment: Pi 0.84.4, authenticated `openai-codex/gpt-5.6-sol`, copied generated Pi package,
ordinary directory with no `.git`, relative internal `vault`, and the same command sentinels.

The two leaves produced two `completed-local` receipts. An intermediate executor retry found leaf 1
already complete while leaf 2 still needed planning; the unattended tick reconciled that state and
continued. The C9 audit later routed a repair successor instead of accepting incomplete evidence,
then reached `DONE` at iteration 6. Final tests, the independent filesystem snapshot, `C1`, `J1`, and
the eval report all passed. Independent inspection covered 998 emitted tool-call payloads with zero
forbidden calls and zero prohibited sentinel calls. Pi itself made eight intercepted git status/diff
probes as runtime bookkeeping; they are retained separately and are not attributed to Superagent.
The compact result is [pi-internal-result.json](evidence/2026-09-17-git-free-mode/pi-internal-result.json),
and the full run remains at `/private/tmp/git-free-smoke-pi-internal`.

### Pi, external vault: PASS

Command:

```text
python3 scripts/git-mode-smoke.py --harness pi --vault external \
  --run-dir /private/tmp/git-free-smoke-pi-external-r2 --timeout 3600 --max-ticks 14
```

The physical project and the vault path containing a space were separately locked and remained
ordinary directories without `.git`. Two leaves, their local reviews/fixes/closeouts, a C9 repair
successor, and the final audit reached `DONE` at iteration 6. Final tests, snapshot capture, `C1`,
`J1`, and the eval report passed. Inspection covered 1,392 emitted tool-call payloads with zero
forbidden calls and zero prohibited sentinel calls; 13 Pi runtime git status/diff probes were
intercepted and retained separately. The compact result is
[pi-external-result.json](evidence/2026-09-17-git-free-mode/pi-external-result.json), and the full run
remains at `/private/tmp/git-free-smoke-pi-external-r2`.

### Codex, external vault: PASS

Command (initial run, then retained evaluation recovery):

```text
python3 scripts/git-mode-smoke.py --harness codex --vault external \
  --run-dir /private/tmp/git-free-smoke-codex-external-r2 --timeout 3600 --max-ticks 14
python3 scripts/git-mode-smoke.py --harness codex --vault external \
  --run-dir /private/tmp/git-free-smoke-codex-external-r2 --timeout 3600 --max-ticks 2 --resume
```

The external project/vault locks, two execution leaves, C9 repair successor, and final audit reached
`DONE` at iteration 6. The first judged evaluation correctly failed because the smoke fixture said
only “Exact greetings” without defining the two required literals or naming the assertion file. The
runner now binds both exact strings and `test_greeting.py`, and can resume post-lifecycle evidence
after a retained evaluation failure. Two sandboxed restart attempts failed before skill execution
when Codex could not initialize its in-process app-server; the authorized unsandboxed retry reused
the retained `DONE` lifecycle and passed final tests, snapshot capture, `C1`, `J1`, and the eval report.

Inspection covered 378 emitted tool-call payloads with zero forbidden calls and zero prohibited
sentinel calls. Codex made 43 intercepted startup/plugin-discovery git probes, retained separately.
The compact result is
[codex-external-result.json](evidence/2026-09-17-git-free-mode/codex-external-result.json), and the
full run remains at `/private/tmp/git-free-smoke-codex-external-r2`.

## GF-01–GF-10 traceability

| ID | Result | Command/environment | Evidence and interpretation |
|---|---|---|---|
| GF-01 | PASS | `git-mode-test.sh`; generated defaults/build checks | Real resolver tests prove env > nearest/explicit `.superenv` > default and absent mode = `github`. |
| GF-02 | PASS | `git-mode-test.sh`; all four real harness runs | Real ordinary-directory/nested init and local discovery; internal and external live fixtures produced no `.git`. External-vault evidence is documented above. |
| GF-03 | PASS | `git-mode-test.sh`; all four real smoke transcripts/sentinels | Lifecycle scripts made zero fake git/gh calls; all 3,189 inspected real emitted call payloads contained zero forbidden workflow operations. Harness runtime startup probes are separately disclosed above. |
| GF-04 | PASS | interpreted scenarios; all four real harness runs | Real planning, implementation, tests, reviews, repair, closeout, and two durable receipts in every run; the Codex internal run also proves interruption recovery. |
| GF-05 | PASS | all four real harness runs; Codex internal iterations 7–8 | Plan-exhausted ticks did not declare success; C9 reopened receipts and repair evidence, reran tests, and only then wrote `DONE`. |
| GF-06 | PASS | 18 workspace-state tests; busy lifecycle fixture; Codex interruption/resume | Real lock contention/shared-vault/dead-owner cases plus live recovery of a retained `RUNNING` tick under inherited ownership. |
| GF-07 | PASS | 14 supereval cases; all four real judged evaluations | Real `snapshot:<digest>` identity, manifests/change record/cleanup token, command evidence, read-only judged objectives, and PASS reports. |
| GF-08 | PASS | resolver/lifecycle tests and interpreted mismatch/receipt scenarios | CI-only local evidence and mode mismatches stop before prohibited operations; a local receipt cannot satisfy GitHub integration. |
| GF-09 | PASS | three build checks; four copied-package runs; four fresh interpretation probes | Canonical, Codex, Cursor, and Pi contain the setting, local contracts, and required runtime helpers; Cursor now carries the full helper set. |
| GF-10 | PASS | default-mode, bridge, external-vault, package, and 16-scenario lifecycle regressions | Existing GitHub default/direct-integration/external-vault contracts remain covered offline and by interpreted regression. No remote repository was created for local acceptance. |

## Coverage limits

- Claude Code 2.1.275 is installed but `claude auth status --json` reports `loggedIn: false`; no real
  Claude lifecycle result is claimed.
- Neither `agent` nor `cursor-agent` is installed; no real Cursor lifecycle result is claimed.
- The live smoke drives fresh CLI sessions directly and deliberately does not arm launchd/systemd or
  contact a GitHub repository. Scheduler transport remains covered by the existing fake-scheduler
  suites, not by this local lifecycle run.
- Raw live transcripts are retained in `/private/tmp` and are machine-local; the compact result and
  interpretation answers above are checked in with this report.
