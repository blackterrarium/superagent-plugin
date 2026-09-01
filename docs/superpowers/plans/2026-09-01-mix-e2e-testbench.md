# Multi-harness mixing e2e testbench — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `scripts/mix-e2e.sh` drives a real goal from an empty repo through `init → supergoal → scheduler-fired loop → DONE` with the supervisor on Claude, implementer/fix-applier on Codex and task-/re-reviewer on Pi, and asserts from `role-bridge.sh` logs that every pinned role ran on its pinned harness.

**Architecture:** Same shape as `scripts/pi-e2e.sh` (whose pure helpers it sources with `PI_E2E_LIB=1`): report sections, PASS/FAIL per phase, `e2e_run` for long children, cleanup trap. New evidence comes from a two-line header/trailer `role-bridge.sh` now writes to its own log. Pure helpers are library-sourceable (`MIX_E2E_LIB=1`) for `bridge-test.sh`.

**Tech Stack:** bash 3.2+ (macOS), python3 (JSON), gh, git, claude/codex/pi CLIs, launchd/systemd via the plugin's own scripts.

**Spec:** `docs/superpowers/specs/2026-09-01-mix-e2e-testbench-design.md`

## Global Constraints

- `role-bridge.sh` stdout stays exactly the CLI's final message; the header/trailer go to the log file only.
- The script never runs a tick itself; ticks are scheduler-fired (`ticks ≥ 2`).
- `.superenv` values with `$` are single-quoted; sourced under `set -u`.
- `mix-e2e-report.md` gitignored; artifacts under `$TMPDIR/mix-e2e-<stamp>/`.
- Defaults: interval `2m`, ceiling `150`, slug `mix-e2e-<YYYYmmdd-HHMMSS>`, implementer `codex:gpt-5.6-terra`, reviewer `pi:openai-codex/gpt-5.6-sol`.
- Bump to 0.6.5 with a CHANGELOG entry; rebuild `codex/`, `pi/`, `cursor/` (they ship copies of `role-bridge.sh`).

## File structure

- Modify `scripts/role-bridge.sh` — header line before the CLI runs, trailer after.
- Create `scripts/mix-e2e.sh` — helpers (pure) → phases → `main` guarded by `MIX_E2E_LIB`.
- Modify `scripts/bridge-test.sh` — bridge header/trailer cases; mix helper cases.
- Modify `.gitignore` (`mix-e2e-report.md`), `scripts/README.md` (section), `README.md` (one pointer), `CHANGELOG.md`, `.claude-plugin/plugin.json`.

Helper interfaces (`scripts/mix-e2e.sh`):

```
mix_render_superenv <interval> <events_log> <implementer> <reviewer> [extra]   # .superenv text
mix_assert_deliverables <repo_dir>          # 0 iff scripts/kv.sh behaves and scripts/test.sh exits 0
mix_bridge_evidence <log_dir> <since_iso>   # rows: role harness model effort exit secs file
mix_evidence_has <rows> <role> <harness> [model]   # 0 iff a matching exit=0 row exists
mix_evidence_count <rows> <role-regex> [harness]   # number of matching rows
mix_role_model <[harness:]model>            # the model half (pi keeps provider/model, drops :level)
```

### Task 1: `role-bridge.sh` header + trailer (TDD in bridge-test.sh)
- [ ] Tests: for claude/codex/pi shims the log's first line matches `^role-bridge: start=<iso> harness=<h> model=<m> effort=<e> tools=<t> role=<r> cwd=<dir>$`; last line matches `^role-bridge: end=<iso> exit=0 secs=[0-9]+ result_bytes=[0-9]+$`; fail shim → `exit=3`; empty shim → `exit=4`; stdout unchanged.
- [ ] Implement; run `bridge-test.sh`; rebuild codex/pi/cursor; `--check` clean.

### Task 2: `mix-e2e.sh` pure helpers (TDD)
- [ ] `mix_render_superenv`, `mix_role_model`, `mix_assert_deliverables` (reference kv.sh fixture), `mix_bridge_evidence` (fixture logs: 3 harnesses, one older than since, one header-only), `mix_evidence_has/count`.

### Task 3: phases 0–4 (preflight, --dry-run, provision, init, goal, arm)
- [ ] Preflight incl. plugin installed+enabled, version WARN, `pi --list-models` has `openai-codex`.
- [ ] init/supergoal via `claude -p` stdin prompts; assert relay definitions carry `--harness codex` / `--harness pi`.

### Task 4: phases 5–8 (drive, assert incl. evidence, evaluate, cleanup) + main
- [ ] Evidence assertions per spec; evaluation section; cleanup copies bridge logs.

### Task 5: docs, version, live run, record
- [ ] `scripts/README.md` section, README pointer, CHANGELOG 0.6.5, plugin.json; `claude plugin update` so the installed plugin is current; live run with `nohup`; record the result + evaluation in `scripts/README.md`; commit; PR.
