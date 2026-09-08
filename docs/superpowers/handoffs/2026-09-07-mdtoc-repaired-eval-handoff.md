# Repaired mdtoc lifecycle — fresh-session evaluation handoff

**Date:** 2026-09-07 · **Status:** repair merged locally; new live evaluation NOT started
**Start in:** `/Users/eugene/src/superagent-plugin`

## Task for the fresh session

Run a new **Codex** full-stack operator evaluation using the lifecycle repair at commit
`1852780`. Verify real `supermeta` → launchd/superagent ticks → GitHub code PR merge →
`supereval` → scheduler disarm. Also exercise the formerly broken **blocked closeout → adopted
re-plan → durable repair request → successor → execution/integration** path. If the ordinary
round never enters that path, report its coverage honestly and run a separate controlled
repair scenario before declaring lifecycle acceptance complete.

The user requested this handoff after authorizing and completing the local merge. This session
has not installed the repaired plugin, pushed the plugin checkout, armed a scheduler, opened or
modified a toy PR, or started a new paid model/operator evaluation. The next session's task is to
perform the new round; resolve required permissions through the normal tool mechanisms.

Suggested opening message:

> Continue from docs/superpowers/handoffs/2026-09-07-mdtoc-repaired-eval-handoff.md.
> Run the new Codex full-stack evaluation with the repaired plugin, preserve the old FAIL,
> and verify both delivery and blocked-repair recovery with durable evidence.

## Read first, in order

1. This handoff.
2. [Repair verification report](../reports/2026-09-07-lifecycle-verification.md) — implementation,
   tests, limitations, and required mdtoc/check corrections.
3. [Failure RCA handoff](2026-09-07-mdtoc-failure-rca-handoff.md) — original causal trace and evidence.
4. [Original operator recipe](2026-09-07-mdtoc-operator-round.md) — use its product brief and
   historical command/fixture descriptions only. Its original bootstrap steps, Claude settings,
   live checkpoints, estimates, and weak acceptance table are NOT current instructions.
5. The repaired canonical `skills/supertraverse/SKILL.md` C8/C9 and consumers `superagent`,
   `superplan`, `superrun`, `superfinish`; execute using the corresponding installed Codex build.

## Current state and preserved baseline

Rechecked in the handoff-writing session unless labeled historical:

| Item | State / path |
|---|---|
| Plugin checkout | `/Users/eugene/src/superagent-plugin`, local `main` at `1852780` |
| Repair branch | `fix-blocked-replan-lifecycle`, merged by fast-forward into local main |
| Repair worktree | `/private/tmp/superagent-lifecycle-fix`, retained; source checkout is the durable starting point |
| Plugin remote | Repair has NOT been pushed in this session; recheck before any publish/install from GitHub |
| Package version | Source/generated manifests still say `0.8.1`; no release/version bump was made |
| Generated packages | Codex, Pi, Cursor rebuilt from canonical repair; all `--check` tests passed |
| Toy code repo | `/Users/eugene/src/mdtoc-loop-test`, clean main `06b3f17` (bootstrap only) |
| Toy remote | Historical: `https://github.com/blackterrarium/mdtoc-loop-test`, private, main branch |
| External vault | `/Users/eugene/superagent-vaults/mdtoc-loop-test`, clean own main `43d3de4` |
| Old project | `projects/2026-09-07-21_30-mdtoc` under that vault |
| Old goal | `2026-09-07-21_37-mdtoc-r1` under that vault |
| Old root | `master-plans/2026-09-07-21_37-mdtoc-r1.md` under the old goal |
| Old leaf | `plans/2026-09-07-21_46-complete-mdtoc-cli.md` under the old goal |
| Old loop | `loop-status/2026-09-07-mdtoc-r1.md` under the old goal; retained false DONE |
| Old code PR | Historical last check: PR #1 OPEN/BLOCKED, `https://github.com/blackterrarium/mdtoc-loop-test/pull/1` |
| Old implementation worktree | `/Users/eugene/src/mdtoc-loop-test-worktrees/mdtoc-r1-complete-cli`; historical HEAD `db1d502` |
| Old scheduler | Historical last check: disarmed; registry `~/.config/superagent/mdtoc-r1.env`, label `com.superagent.tick.mdtoc-r1` |
| Installed Codex package | Historical path `~/.codex/plugins/cache/superagent/superagent/0.8.1`; still assumed OLD until content verification proves otherwise |

Old evaluator: `<vault>/projects/2026-09-07-21_30-mdtoc/eval-reports/2026-09-07-23_09-r1.md`.
Its verdict remains **FAIL**: C1/C2/C3/C5/C6/J1 failed, C4/C7 were false positives. No code PR
merged, although all four wrapper ticks exited 0 and the loop self-disarmed. Preserve the old
plan/finding/closeout, Decisions/iteration log, PR and evaluation. Do not reset/delete them,
merge PR #1 as a shortcut, rewrite the old acceptance inputs, or relabel the run PASS.

Existing unrelated untracked plugin paths: `codex-smoke-report.md`, `html-docs/`, and historical
files in `docs/superpowers/handoffs/`. Stage new evidence explicitly; never sweep these into a commit.

## What the repair does and what tests proved

- C8 makes adopted re-plan a tracked repair request, marks its row `repair requested`, preserves
  predecessor evidence and publishes a new active successor plan on the same step.
- Fresh ticks reconcile decisions, partial publication, repeated-repair chains and dispositions.
- Old closeouts cannot complete a pending repair or overwrite its successor.
- BLOCKED overrides `none`; DONE requires C9's recursive integration/disposition audit.
- Stale closed ancestors hiding unfinished work cause actionable BLOCKED, not an empty-queue spin.

Baseline agent probes failed 7/12 cases. Revised canonical and generated Codex probes passed
16/16 each. Independent review found two additional recovery gaps, both fixed and re-reviewed.
Package helpers, bridge, external-vault and PRD-lint tests passed. These are skill simulations and
helper tests, **not** actual scheduled repair publication, native harness coverage on Pi/Claude,
or a GitHub merge acceptance result. Revalidating saved JSON is not a new model test.

## Phase 1 — preflight and load the repaired package

1. Recheck source/main, toy repo/worktree/vault state, old PR, scheduler registry and active loops.
   Read-only shell starting points:

   ```sh
   git -C /Users/eugene/src/superagent-plugin log -1 --oneline
   git -C /Users/eugene/src/superagent-plugin status --short
   git -C /Users/eugene/src/superagent-plugin merge-base --is-ancestor 1852780 main
   git -C /Users/eugene/src/mdtoc-loop-test status -sb
   git -C /Users/eugene/superagent-vaults/mdtoc-loop-test status -sb
   /Users/eugene/src/superagent-plugin/scripts/status.sh --json
   gh pr view 1 --repo blackterrarium/mdtoc-loop-test --json state,mergedAt,headRefName,headRefOid
   ```

   Recheck CLI availability/authentication. Historical host: macOS, bash 3.2, Python 3.9,
   `unittest` available, no pytest or timeout/gtimeout. Historical Codex CLI was 0.153.4.
   `gh` keychain authentication worked as blackterrarium outside the sandbox despite a
   sandbox-only auth failure; do not replace credentials based on that failure alone.

2. Verify generated files with all three builders' `--check` commands. Install/refresh the
   **local repaired Codex package**, following `codex/README.md` and current local CLI help.
   The local marketplace source is `/Users/eugene/src/superagent-plugin/codex`. Installing from
   GitHub alone can retrieve the old code because the repair is only local. Resolve cache
   refresh using the supported CLI flow; do not hand-edit generated files or blindly copy
   canonical Claude skills into the Codex cache. If changing a cachebuster/version is needed,
   record it explicitly as evaluation setup, separate from the tested source SHA.

3. Verify the installed runtime bytes, not just `version: 0.8.1`. Compare installed/generated
   SKILL.md for **superagent, supertraverse, superplan, superrun, superfinish, superloop**, and
   record installed path plus checksums and source SHA. C8/C9 must exist in installed traversal;
   supervisor must require C9 before DONE. Start a fresh session after install if necessary.
   Verify role-dispatched skills resolve to this same package. The tick wrapper reads the
   supervisor from source `codex/`, but delegated skills use the installed plugin: mixed copies
   would invalidate the test.

4. External-driver scripts come from `/Users/eugene/src/superagent-plugin/scripts`.
   Use repaired Codex `templates/superenv.default` model/effort defaults and
   `SUPER_GOAL_ROOT=/Users/eugene/superagent-vaults/mdtoc-loop-test`. Inspect existing `.superenv`
   first; init already ran. Re-run init only when needed and idempotently. No `.claude/agents`
   generation on Codex. Keep the plugin's dogfood vault (`.../superagent-plugin`) out of this run.
   Record any config changes; preserve unrelated keys. No weakening reviews, CI gates or merge
   protection to obtain a PASS.

## Phase 2 — author a new project with corrected acceptance inputs

Create a **new timestamped project folder**, e.g. `<STAMP>-mdtoc-lifecycle-repair`, in the same
external vault. A new project makes the strengthened acceptance contract distinct from the
frozen failed round. Use `superprd` with the original operator recipe's mdtoc product brief,
fixtures, Python-standard-library/unittest constraints, and these explicit corrections:

- Proper fence closing (matching character, adequate run length, whitespace-only suffix).
- ATX headings allow 0–3 leading spaces and strip valid optional closing hashes; test four-space
  indentation exclusion and resulting labels/slugs.
- Same-directory temporary write and atomic replace; injected late write/replace failures preserve
  original bytes and clean up temporary files. Explicitly decide metadata/symlink handling in plan.
- Keep all original functional requirements: marker-delimited replacement, stdout mode,
  idempotence, duplicate slug suffixes, missing-argument/file and missing-marker behavior, README.
- Harden C4/C7 and test existence/completeness as described below; include the new parser/write
  regressions in the test suite and link them to measurable PRD criteria.

Before accepting the new evaluation contract:

1. Add an existence/compile check for `mdtoc.py`. Require tests to run at least one test (zero
   tests must fail). Use `unittest` discovery with an explicit test-count assertion if needed.
2. C4 must check script existence, ensure the requested input does not exist, capture process
   exit/stdout/stderr, and require exit 2 plus the application's usage/missing-input diagnostic.
   A missing Python script must fail this check. Validate the negative control on bootstrap main.
3. C7 must read and parse `mdtoc.py` with Python AST, inspect Import/ImportFrom module roots against
   an explicitly reviewed stdlib allowlist, and fail on missing file or syntax error. Include
   tempfile if the implementation uses it. Do not retain the grep pipeline whose final exit 1
   masked read failure. Check a deliberately disallowed import as another negative control.
4. Check CLI no-argument/missing-marker cases for both exit and expected diagnostic. Scope/README
   judgments remain separate from implementation completeness. Use the new round's actual
   baseline main SHA for J2; explicitly allow only required init `.superenv`/`.gitignore` changes
   alongside mdtoc.py, README, tests and fixtures. No stray `.superpowers/sdd` reports tracked.
5. Use temporary paths unique to the run rather than shared `/tmp/mdtoc-once.md`. Escape `|` as
   `\|` inside Markdown evaluation cells. Run `prd-lint.sh` and actual check parsing; review the
   rendered commands. Freeze the new inputs before implementation, record their commit/hash.

A fresh PRD reviewer must review the new contract. Record negative-control outcomes and review.
Do not allow an evaluator/check failure to be silently redefined after observing output. If the
contract genuinely needs correction later, record an amendment and its effect on comparability.

## Phase 3 — new full-stack operator round

From the toy repository using the new project's absolute path:

1. Run `supermeta <new-project-dir>` with the repaired package. Record meta-plan path/commit,
   actual planner role dispatch, new goal path, root path and opened ledger row. Confirm the
   plan explicitly authorizes corrected parser and atomic-write behavior; do not reuse the
   old exact-code plan as the new implementation instructions.
2. Use `superagent-external <new-root-plan> --interval 5m`. Choose/verify a unique scheduler
   slug, loop file and log path, e.g. `mdtoc-lifecycle-<timestamp>`. Derive paths from actual
   skill/launch output; do not reuse `mdtoc-r1`. Check current script help if supplying `--slug`
   directly. Record scheduler label/registry and source wrapper path.
3. Monitor the new slug using superagent-monitor / scripts/status.sh. Let launchd own ticks;
   do not manually execute the implementation or change tree rows to speed the run. Save each
   delegated Final Report, bridge/runtime role receipt, decision, commit, PR and state transition.
4. If WAITING FOR INPUT occurs, answer via the supported monitor/answer mechanism and record the
   question/answer as operator intervention. Diagnose a suspected hung tick using live process,
   lock and progress evidence; elapsed time alone is not proof of a hang. Use force-stop only
   on a verified hung tick, recording why and recovery outcome.
5. At reported DONE, independently verify **main contains the implementation**, the new code PR
   is MERGED, its merge commit is on main, and closeout/repair dispositions reconcile. An empty
   queue, wrapper exit 0, docs-only merge or DONE string does not satisfy this check.
6. Run `supereval <new-project-dir>` on synchronized code main, record evaluated SHA, full command
   and judged tables, evaluator dispatch evidence, report commit and completed ledger row.
   Check actual timer inactive, tick inactive and no lock after the final wrapper exits.

If the new loop falsely reports DONE or is terminally blocked, preserve that state and run an
independent evaluation on main as failure evidence where the evaluation workflow permits.
Do not report success or repair the evidence in place to obtain one.

## Phase 4 — ensure the repaired path was actually exercised

If Phase 3 naturally produces a blocked closed-out leaf and adopted re-plan, use its receipts
for this phase. Otherwise label Phase 3 **delivery-path acceptance only** and run a separate,
explicitly labeled controlled lifecycle scenario in a new goal/run/branch/PR identity.

The controlled fixture must start with a real new blocked code PR and a tracked closed-out leaf
on its own plan tree. Reuse the old defect pattern as fixture input if useful, but copy evidence
into the new goal and use a new branch/PR; do not mutate or merge old PR #1. Scope the repair to
an actual test/review failure (the observed fence/ATX/write conflict is suitable). Record all
fixture provisioning separately from autonomous ticks. The fixture can start at the failed
boundary; it does not claim to re-test supermeta, which Phase 3 covers.

Leave resolution of that new blocked obligation to the repaired supervisor. It must receive the
BLOCKED result, adopt a re-plan through its real decision ladder, and apply C8 itself. Do not
pre-create `repair requested`, hand-author its successor, or patch the loop to force a PASS.
If the panel chooses another valid disposition, record it; that attempt has not yet demonstrated
re-plan recovery. A transparent supported user decision to re-plan can exercise the resumed-answer
path, but must be labeled **assisted** rather than an autonomous panel success.

Required evidence across separate actual scheduled ticks:

| Boundary | Required observation |
|---|---|
| Blocked attempt | Code PR open/unmerged; tracked closeout; row closed for normal descent; exact blocker |
| Adopted repair | Panel votes or supported user answer; tracked C8 decision record; same step `repair requested`; old attempt preserved |
| Publication ordering | Repair/tree commit verified before ready-state loop write; exhaustion cleared |
| Fresh tick | Next planner reads persisted state with no conversation handoff and selects the repair |
| Successor | New plan file, same immediate parent, active Plan replacement, predecessor/closeout history, explicit PR disposition |
| Execution | Actual successor execution and review/test gates; no blind rerun of predecessor |
| Integration | New/reused fixture PR merged as authorized; predecessor disposition verified; main contains corrected behavior |
| Terminal | C9 evidence, evaluator on main PASS, scheduler disarmed; no unresolved active PR hidden by closeout |

If the ordinary product was already delivered in Phase 3, choose a separately scoped controlled
repair so its baseline and acceptance contract remain meaningful. Do not downgrade or overwrite
main merely to recreate the old failure. The failed code stays on the new fixture branch until
corrected and reviewed. Record the exact fixture design and frozen checks before launch.

## Results to write and success rubric

Write a timestamped portable operator report under this plugin checkout's
`docs/superpowers/reports/` and preserve durable raw evidence in the external vault/new run folder.
Update `stage2-round-report.md` only as a supplemental local chronology. The portable report must
be sufficient without machine-specific Claude memory or temporary logs.

Include source SHA, installed path/checksums/version, CLI version, config pins, code/vault baseline
SHAs, project/goal/root/loop paths, scheduler slug/label, UTC start/end, tick count, wrapper and
role receipts, every relevant PR/merge SHA, decisions/interventions, code SHA evaluated, full C/J
results and final timer/tick/lock state. Copy needed temporary logs into the durable evidence area.

Report distinct verdicts:

- **Product/full-stack delivery:** PASS only with actual code integration, independent evaluator
  PASS on main and real scheduler disarm.
- **Blocked-replan recovery:** PASS only with the required real transition evidence above;
  otherwise NOT EXERCISED, ASSISTED (with outcome), BLOCKED or FAIL, as appropriate.
- **Prior baseline:** remains FAIL; link to it. State that new acceptance inputs were strengthened.
- **Other harnesses / timeout:** no Claude/Pi native acceptance claim from a Codex run. If
  timeout/gtimeout remains absent, timeout enforcement remains unverified.

Do not infer either PASS from the other, from static probes, or from a successful wrapper exit.
At completion leave new repos, PR history, vault records and disarmed registry available for review.
