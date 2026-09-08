# Blocked Re-plan Lifecycle Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep authorized repairs reachable and prevent DONE with unresolved implementation work.
**Architecture:** Durable repair request, successor active plan, recursive completion audit.
**Tech Stack:** Markdown skill algorithms, Python 3.9 unittest, bash package builders.
**Spec:** ../specs/2026-09-07-blocked-replan-lifecycle-design.md

## Global Constraints

- Canonical skill contracts are production logic; rebuild Codex, Pi and Cursor outputs.
- Python 3.9 standard library / unittest; macOS bash 3.2 compatible verification.
- Preserve the failed mdtoc run, frozen evaluation, blocked PR and scheduler state.
- No claim of real transport acceptance from static or agent scenario tests.

## Task 1: Reproduce and define regression scenarios

Files: scripts/lifecycle-regression.py, docs/superpowers/reports/2026-09-07-lifecycle-verification.md.
- [x] Read canonical consumers and retained failure evidence.
- [x] Dispatch a fresh baseline agent: one closed-out open-PR row, adopted re-plan,
  planner none then executor none/BLOCKED. Record actual result: none, none, literal DONE;
  BLOCKED precedence ambiguous and no concrete repair eligibility transition.
- [x] Add reusable scenarios with machine-checked fields for targets, completion and recovery.
  Run `python3 scripts/lifecycle-regression.py --help`; run baseline answers through validator
  and observe failure because planning is none and terminal status is DONE.

## Task 2: Repair the shared lifecycle

Files: skills/supertraverse/SKILL.md, skills/superagent/SKILL.md,
skills/superplan/SKILL.md, skills/superrun/SKILL.md, skills/superfinish/SKILL.md,
skills/superloop/SKILL.md.
- [x] Define `repair requested`, C8 durable repair/successor publication and C9 completion audit.
- [x] Order traversal: repair selection before closed-row filtering; pending repair never executes.
- [x] Publish successor through superplan, preserve history outside active navigation, protect
  active successor from late predecessor superfinish, route execution with integration context.
- [x] Apply/recover adopted repair decisions before dispatch; commit and verify tree changes
  before changing loop state. Clear planning exhaustion on new repair.
- [x] Give blockers precedence and require C9 before DONE. Update summary/schema wording.
- [x] Run fresh-agent scenarios using `--prompt`; validate saved JSON with `--answers`.

## Task 3: Package, review and document

Files: generated codex/, pi/, cursor/; scripts/README.md; verification report.
- [x] Run all three `bash scripts/build-{codex,pi,cursor}-skills.sh` then their `--check` modes.
- [x] Run `bash scripts/coding-loop-package-test.sh`, `bash scripts/bridge-test.sh`,
  `bash scripts/vault-external-test.sh` and `bash scripts/prd-lint-test.sh`.
- [x] Run generated-package regression scenarios; request independent lifecycle review and
  resolve Important findings before final verification.
- [x] Record results, limitations and new-round mdtoc acceptance prerequisites without altering
  frozen baseline inputs. Commit only the requested change's files on the isolated branch.
