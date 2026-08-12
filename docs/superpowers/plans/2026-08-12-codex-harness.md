# Codex Harness Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `SUPER_HARNESS=codex` (OpenAI Codex CLI headless mode) as a third harness beside `claude|cursor`, with per-role reasoning-effort configuration (`SUPER_EFFORT_*`) across harnesses and a `.superenv` validation pass in `superagent:init`.

**Architecture:** Follows the proven Cursor-port pattern: harness dispatch in `scripts/_common.sh`, a harness branch in `scripts/superagent-tick.sh`, and a generated build directory (`codex/`, laid out as a Codex plugin marketplace) produced by a new `scripts/build-codex-skills.sh` from conditional markers in the canonical skills. Reasoning effort rides the tick invocation for the supervisor and the generated per-role agent definitions (claude) / `spawn_agent` parameters (codex) for roles.

**Tech Stack:** Bash (strict mode), markdown skills with HTML-comment build markers, Codex CLI (`codex exec`), no test framework — verification is stub-binary argv assertions, build `--check` modes, and a manual smoke script.

**Spec:** `docs/superpowers/specs/2026-08-12-codex-harness-design.md` (read it before starting any task).

## Global Constraints

- All work on the existing `codex-harness` branch; commit per task; PR to `main` at the end. Never commit directly to `main`.
- `set -euo pipefail` in every executable script; sourced helpers must stay `set`-clean (no `set -e` side effects).
- `cursor/` and `codex/` are GENERATED directories — never hand-edit; always edit canonical sources and re-run the build script, then commit the regenerated output.
- `scripts/build-cursor-skills.sh --check` must pass after every task that touches canonical skills (CI treats stale generated trees as failures).
- Marker grammar (canonical skills): `<!-- cc-only:start -->…<!-- cc-only:end -->` (Claude Code build only), `<line> <!-- cc-only -->` (single line), `<!-- cursor-only:start` … `cursor-only:end -->` (activated in cursor build), `<!-- codex-only:start` … `codex-only:end -->` (activated in codex build). Each derived build drops the other builds' blocks entirely.
- Effort value domains (exact): claude `low|medium|high|xhigh|max`; codex `none|minimal|low|medium|high|xhigh`; cursor: unsupported (non-`inherit` → warn, treat as `inherit`). `inherit` = pass nothing.
- The driver never sets `CLAUDE_CODE_EFFORT_LEVEL` (it overrides both `--effort` and per-role frontmatter); it warns when the variable is already present.
- Tick exit codes: 4 = gh unauth, 5 = missing CLI binary, 6 = bad harness, 7 = missing generated build, 8 = bad `SUPER_CODEX_SANDBOX`.
- Codex sandbox mapping (exact): `workspace-write` → `--sandbox workspace-write -c sandbox_workspace_write.network_access=true`; `danger-full-access` → `--dangerously-bypass-approvals-and-sandbox`.

---

### Task 1: `_common.sh` — accept the codex harness, find the codex binary

**Files:**
- Modify: `scripts/_common.sh:83-110` (harness dispatch block)

**Interfaces:**
- Produces: `superagent_harness()` echoes `claude|cursor|codex`; `ensure_codex_bin()` (exit nonzero + message when `codex` not on PATH); `ensure_cli_bin()` dispatches all three.
- Consumed by: `superagent-tick.sh`, `launch.sh`, `install-timer.sh` (Tasks 2–3).

- [ ] **Step 1: Write the failing test** (throwaway script in the scratchpad, not committed)

```bash
cat > /tmp/t_common.sh <<'EOF'
#!/usr/bin/env bash
set -u
. "$(git rev-parse --show-toplevel)/scripts/_common.sh"
fail=0
[[ "$(SUPER_HARNESS=codex superagent_harness)" == "codex" ]] || { echo "FAIL: harness codex rejected"; fail=1; }
SUPER_HARNESS=bogus superagent_harness 2>/dev/null && { echo "FAIL: bogus accepted"; fail=1; }
# stub codex binary on PATH
STUB="$(mktemp -d)"; printf '#!/bin/sh\nexit 0\n' >"$STUB/codex"; chmod +x "$STUB/codex"
( PATH="$STUB:$PATH" SUPER_HARNESS=codex ensure_cli_bin ) || { echo "FAIL: ensure_cli_bin codex with stub"; fail=1; }
( PATH="/usr/bin:/bin" SUPER_HARNESS=codex ensure_cli_bin 2>/dev/null ) && { echo "FAIL: missing codex not fatal"; fail=1; }
rm -rf "$STUB"; [[ $fail == 0 ]] && echo OK
EOF
bash /tmp/t_common.sh
```

- [ ] **Step 2: Run it to verify it fails**

Expected: `superagent: bad SUPER_HARNESS 'codex' (want claude|cursor)` and `FAIL: harness codex rejected`.

- [ ] **Step 3: Implement**

In `scripts/_common.sh`, change the harness dispatch block:

```bash
# ---------------------------------------------------------------------------
# Harness dispatch — which agent CLI the external driver fires per tick.
#   SUPER_HARNESS=claude (default) -> the Claude CLI (`claude`)
#   SUPER_HARNESS=cursor           -> the Cursor CLI (`agent`, older `cursor-agent`)
#   SUPER_HARNESS=codex            -> the OpenAI Codex CLI (`codex`)
# Resolution: process env > <repo>/.superenv > plugin default (via load_superenv).
# ---------------------------------------------------------------------------

superagent_harness() {
  local h="${SUPER_HARNESS:-claude}"
  case "$h" in
    claude|cursor|codex) echo "$h" ;;
    *) echo "superagent: bad SUPER_HARNESS '$h' (want claude|cursor|codex)" >&2; return 1 ;;
  esac
}
```

After `ensure_cursor_bin()`, add:

```bash
# Fatal check: ensure the OpenAI Codex CLI binary (`codex`) is findable.
ensure_codex_bin() {
  _superagent_augment_path
  if ! command -v codex >/dev/null 2>&1; then
    echo "superagent: Codex CLI not found on PATH (tried: codex; checked incl. ~/.local/bin, /usr/local/bin). Install it (npm install -g @openai/codex, or brew install codex) or add its directory to PATH in the scheduler env; aborting." >&2
    return 1
  fi
  return 0
}
```

Replace `ensure_cli_bin()`:

```bash
# Fatal check for whichever CLI the resolved harness needs.
ensure_cli_bin() {
  local h; h="$(superagent_harness)" || return 1
  case "$h" in
    cursor) ensure_cursor_bin ;;
    codex)  ensure_codex_bin ;;
    *)      ensure_claude_bin ;;
  esac
}
```

- [ ] **Step 4: Run the test to verify it passes** — `bash /tmp/t_common.sh` → `OK`.

- [ ] **Step 5: Commit**

```bash
git add scripts/_common.sh
git commit -m "feat: _common.sh accepts SUPER_HARNESS=codex and locates the codex binary"
```

---

### Task 2: `superagent-tick.sh` — codex branch, sandbox knob, effort for all harnesses

**Files:**
- Modify: `scripts/superagent-tick.sh:64-146` (harness branches, prompt, invocation)
- Modify: `templates/superenv.default` (add `SUPER_CODEX_SANDBOX` under the Harness section)

**Interfaces:**
- Consumes: `superagent_harness`/`ensure_cli_bin` from Task 1; `SUPER_EFFORT_SUPERVISOR`, `SUPER_CODEX_SANDBOX`, `TICK_MODEL`, `TICK_EFFORT` env keys.
- Produces: tick argv contracts asserted by the stub test below; exit 7 (missing codex build), exit 8 (bad sandbox value).

- [ ] **Step 1: Write the failing stub-argv test**

```bash
cat > /tmp/t_tick.sh <<'EOF'
#!/usr/bin/env bash
set -u
ROOT="$(git rev-parse --show-toplevel)"
STUB="$(mktemp -d)"; LOOP="$(mktemp)"; LOG="$(mktemp)"
# stub codex + gh that record argv and succeed
printf '#!/bin/sh\necho "CODEX_ARGV:$@"\nexit 0\n' >"$STUB/codex"
printf '#!/bin/sh\nexit 0\n' >"$STUB/gh"
chmod +x "$STUB"/*
# minimal fake codex build so the exit-7 gate passes
mkdir -p "$ROOT/codex/plugins/superagent/skills/superagent"
touch "$ROOT/codex/plugins/superagent/skills/superagent/SKILL.md"
fail=0
run() { PATH="$STUB:$PATH" GH_TOKEN=x LOOP_FILE="$LOOP" LOG_FILE="$LOG" REPO="$ROOT" \
        TICK_OUTPUT_FORMAT=text SUPER_HARNESS=codex "$@" bash "$ROOT/scripts/superagent-tick.sh"; }
: >"$LOG"; run env SUPER_MODEL_SUPERVISOR=gpt-5.1-codex SUPER_EFFORT_SUPERVISOR=high || { echo "FAIL: tick rc"; fail=1; }
grep -q "CODEX_ARGV:exec " "$LOG" || { echo "FAIL: codex exec not invoked"; fail=1; }
grep -q -- "-m gpt-5.1-codex" "$LOG" || { echo "FAIL: model flag"; fail=1; }
grep -q -- "model_reasoning_effort=high" "$LOG" || { echo "FAIL: effort override"; fail=1; }
grep -q -- "--sandbox workspace-write" "$LOG" || { echo "FAIL: default sandbox"; fail=1; }
grep -q -- "sandbox_workspace_write.network_access=true" "$LOG" || { echo "FAIL: network access"; fail=1; }
: >"$LOG"; run env SUPER_CODEX_SANDBOX=danger-full-access || { echo "FAIL: yolo rc"; fail=1; }
grep -q -- "--dangerously-bypass-approvals-and-sandbox" "$LOG" || { echo "FAIL: yolo flag"; fail=1; }
run env SUPER_CODEX_SANDBOX=bogus 2>/dev/null; [[ $? == 8 ]] || { echo "FAIL: bad sandbox not exit 8"; fail=1; }
rm -rf "$STUB" "$LOOP" "$LOG" "$ROOT/codex"; [[ $fail == 0 ]] && echo OK
EOF
bash /tmp/t_tick.sh
```

- [ ] **Step 2: Run it to verify it fails** — expected: `FAIL: codex exec not invoked` (Task 1 already made the harness value legal, but the tick has no codex arm yet, so it falls into the claude `else` branch — the log never contains `CODEX_ARGV:`).

- [ ] **Step 3: Implement the tick changes**

3a. In the `SKILLS_ROOT`/model resolution block (`scripts/superagent-tick.sh:64-86`), insert a codex arm between the cursor arm and the claude `else`:

```bash
elif [[ "$HARNESS" == codex ]]; then
  # Codex build of the plugin: a Codex plugin-marketplace tree under <plugin-repo>/codex
  # (generated by scripts/build-codex-skills.sh). Skills load via the INSTALLED plugin
  # (codex plugin marketplace add <repo>/codex && codex plugin add superagent@superagent);
  # the tick itself only needs the SKILL.md file path for its file-read prompt.
  SKILLS_ROOT="$PLUGIN_ROOT/codex"
  if [[ ! -f "$SKILLS_ROOT/plugins/superagent/skills/superagent/SKILL.md" ]]; then
    echo "superagent-tick: Codex build missing at $SKILLS_ROOT (run scripts/build-codex-skills.sh)" >&2
    exit 7
  fi
  # Model: TICK_MODEL > SUPER_MODEL_SUPERVISOR; values are Codex model names.
  # "inherit" -> empty -> omit -m (the CLI's config.toml default applies).
  TICK_MODEL="${TICK_MODEL:-${SUPER_MODEL_SUPERVISOR:-inherit}}"
  [[ "$TICK_MODEL" == "inherit" ]] && TICK_MODEL=""
```

3b. Immediately after the harness model block, add supervisor-effort resolution (all harnesses):

```bash
# Supervisor reasoning effort: TICK_EFFORT > SUPER_EFFORT_SUPERVISOR > inherit.
# Harness-native names (claude: low..max; codex: none..xhigh); inherit -> pass nothing.
# Cursor has no effort control: warn and drop.
TICK_EFFORT="${TICK_EFFORT:-${SUPER_EFFORT_SUPERVISOR:-inherit}}"
[[ "$TICK_EFFORT" == "inherit" ]] && TICK_EFFORT=""
if [[ "$HARNESS" == cursor && -n "$TICK_EFFORT" ]]; then
  echo "superagent-tick: warning — reasoning effort is not supported on the Cursor CLI; ignoring '$TICK_EFFORT'" >&2
  TICK_EFFORT=""
fi
# CLAUDE_CODE_EFFORT_LEVEL outranks both --effort and per-role frontmatter pins —
# never set it here, and flag it when the scheduler env already carries it.
if [[ "$HARNESS" == claude && -n "${CLAUDE_CODE_EFFORT_LEVEL:-}" ]]; then
  echo "superagent-tick: warning — CLAUDE_CODE_EFFORT_LEVEL='$CLAUDE_CODE_EFFORT_LEVEL' is set; it overrides --effort AND per-role effort pins" >&2
fi
# Codex sandbox posture (codex harness only): workspace-write (default) | danger-full-access.
if [[ "$HARNESS" == codex ]]; then
  SUPER_CODEX_SANDBOX="${SUPER_CODEX_SANDBOX:-workspace-write}"
  case "$SUPER_CODEX_SANDBOX" in
    workspace-write|danger-full-access) ;;
    *) echo "superagent-tick: bad SUPER_CODEX_SANDBOX '$SUPER_CODEX_SANDBOX' (want workspace-write|danger-full-access)" >&2; exit 8 ;;
  esac
fi
```

3c. Prompt: extend the existing `if/else` (`scripts/superagent-tick.sh:97-101`) to three arms; the codex wording matches cursor's (no `AskUserQuestion` tool exists there):

```bash
if [[ "$HARNESS" == claude ]]; then
  PROMPT="Read ${SKILLS_ROOT}/skills/superagent/SKILL.md and execute exactly ONE --tick on loop file ${LOOP_FILE}, in unattended/non-interactive mode: NEVER call AskQuestion/AskUserQuestion; if a decision needs the user, write the ## Pending decision block, set status to WAITING FOR INPUT, and exit per the skill. Then stop."
else
  # cursor + codex: chat questions are impossible in these headless modes; generic wording.
  SUPERVISOR_SKILL="$SKILLS_ROOT/skills/superagent/SKILL.md"
  [[ "$HARNESS" == codex ]] && SUPERVISOR_SKILL="$SKILLS_ROOT/plugins/superagent/skills/superagent/SKILL.md"
  PROMPT="Read ${SUPERVISOR_SKILL} and execute exactly ONE --tick on loop file ${LOOP_FILE}, in unattended/non-interactive mode: NEVER ask the user a question in chat; if a decision needs the user, write the ## Pending decision block, set status to WAITING FOR INPUT, and exit per the skill. Then stop."
fi
```

3d. Auth note block (`scripts/superagent-tick.sh:118-122`): add a codex arm:

```bash
elif [[ "$HARNESS" == codex && -z "${OPENAI_API_KEY:-}" ]]; then
  echo "    note: OPENAI_API_KEY not set (no $REPO/.env entry); relying on the Codex CLI's own stored login" >>"$LOG_FILE"
```

3e. Invocation: add a codex arm before the claude arms (`scripts/superagent-tick.sh:124-146`), and append `--effort` to both claude arms:

```bash
rc=0
if [[ "$HARNESS" == codex ]]; then
  codex_args=(exec "$PROMPT")
  if [[ "$SUPER_CODEX_SANDBOX" == workspace-write ]]; then
    codex_args+=(--sandbox workspace-write -c sandbox_workspace_write.network_access=true)
  else
    codex_args+=(--dangerously-bypass-approvals-and-sandbox)
  fi
  [[ -n "$TICK_MODEL" ]]  && codex_args+=(-m "$TICK_MODEL")
  [[ -n "$TICK_EFFORT" ]] && codex_args+=(-c "model_reasoning_effort=$TICK_EFFORT")
  [[ "$TICK_OUTPUT_FORMAT" == stream ]] && codex_args+=(--json)
  ( cd "$REPO" && "${TIMEOUT_CMD[@]+"${TIMEOUT_CMD[@]}"}" codex "${codex_args[@]}" ) \
    >>"$LOG_FILE" 2>&1 || rc=$?
elif [[ "$HARNESS" == cursor ]]; then
  ... (existing cursor arm, unchanged) ...
else
  claude_args=(-p "$PROMPT" --model "$TICK_MODEL" --allowedTools "Read,Edit,Write,Bash,Task,Skill")
  [[ -n "$TICK_EFFORT" ]] && claude_args+=(--effort "$TICK_EFFORT")
  [[ "$TICK_OUTPUT_FORMAT" == stream ]] && claude_args+=(--output-format stream-json --verbose)
  ( cd "$REPO" && "${TIMEOUT_CMD[@]+"${TIMEOUT_CMD[@]}"}" claude "${claude_args[@]}" ) \
    >>"$LOG_FILE" 2>&1 || rc=$?
fi
```

(This folds the two claude arms into one array-built arm — behavior identical, plus optional `--effort`.)

3f. Log framing line (`scripts/superagent-tick.sh:105`): add `effort=${TICK_EFFORT:-default}` after `model=…`, and `sandbox=${SUPER_CODEX_SANDBOX:-n/a}` when harness=codex.

3g. `templates/superenv.default`: in the `── Harness ──` section, after `SUPER_HARNESS=claude`:

```bash
SUPER_CODEX_SANDBOX=workspace-write     # codex harness only: workspace-write (repo+/tmp writable, network on) | danger-full-access
```

Also update the `SUPER_HARNESS` comment to `# claude | cursor | codex — which agent CLI the external driver fires per tick`.

- [ ] **Step 4: Run the stub test** — `bash /tmp/t_tick.sh` → `OK`. Also regression-check the claude arm: rerun with a stub `claude` binary and `SUPER_HARNESS=claude SUPER_EFFORT_SUPERVISOR=xhigh`, assert log contains `--effort xhigh`; and with `SUPER_EFFORT_SUPERVISOR=inherit`, assert it does not contain `--effort`.

- [ ] **Step 5: Run `scripts/build-cursor-skills.sh --check`** — expected: still up to date (this task touched no canonical skills; `templates/superenv.default` IS canonical input to the cursor build, so if the check fails, re-run `scripts/build-cursor-skills.sh` and commit the regenerated `cursor/templates/superenv.default` with this task).

- [ ] **Step 6: Commit**

```bash
git add scripts/superagent-tick.sh templates/superenv.default cursor/
git commit -m "feat: codex tick branch (sandbox knob, model/effort) + --effort on claude ticks"
```

---

### Task 3: `launch.sh` / `install-timer.sh` accept `--harness codex`

**Files:**
- Modify: `scripts/launch.sh:27,50,54`
- Modify: `scripts/install-timer.sh:26,48`

**Interfaces:**
- Consumes: Task 1's `superagent_harness`.
- Produces: `--harness codex` reaches the scheduler unit env as `SUPER_HARNESS=codex`.

- [ ] **Step 1: Verify current failure** — `bash scripts/launch.sh /nonexistent/PLAN.md --harness codex --dry-run; echo rc=$?` → expected `bad --harness 'codex' (want claude|cursor)`, rc=2.

- [ ] **Step 2: Implement** — in both files:
  - usage strings: `[--harness claude|cursor]` → `[--harness claude|cursor|codex]`
  - validation cases: `case "$HARNESS" in claude|cursor) ;;` → `case "$HARNESS" in claude|cursor|codex) ;;` and the error text `(want claude|cursor)` → `(want claude|cursor|codex)`
  - `scripts/launch.sh:52-54` model-shown chain: add `elif [[ "$HARNESS" == codex ]]; then MODEL_SHOWN="config default"` before the cursor arm's pattern (mirror the existing style).

- [ ] **Step 3: Verify** — rerun Step 1's command: it must now fail on the missing PLAN.md (or reach `--dry-run` output showing `harness: codex`), NOT on the harness validation.

- [ ] **Step 4: Commit**

```bash
git add scripts/launch.sh scripts/install-timer.sh
git commit -m "feat: launch/install-timer accept --harness codex"
```

---

### Task 4: Per-role effort in the role-agent template, init generation rules, and dispatch policy

**Files:**
- Modify: `templates/super-role-agent.md`
- Modify: `skills/init/SKILL.md` (role-key resolution section, `:100-159`)
- Modify: `skills/superrun/SKILL.md:117-129` (Model policy)
- Modify: `skills/superloop/SKILL.md:581-588` (L7 panel dispatch)

**Interfaces:**
- Consumes: `SUPER_EFFORT_*` keys (already in `templates/superenv.default`).
- Produces: generated `.claude/agents/super-<role>.md` files may carry `effort:`; dispatch rule "definition exists → `subagent_type: super-<role>`" used by superrun/superloop.

- [ ] **Step 1: Update `templates/super-role-agent.md`**

```markdown
---
name: super-<role>
description: superagent <role> role agent — pins this role's model and/or reasoning effort as configured in .superenv (<KEY>). Generated by superagent:init; do not edit by hand.
model: <model-id>
effort: <effort>
---

<!-- generated-by: superagent:init (from .superenv <KEY>) — re-run superagent:init after changing the key; do not edit by hand -->

You are the superagent `<role>` role agent. You exist only to pin your role's model
and/or reasoning effort: the dispatching skill's prompt carries every instruction for
the task. Execute that prompt exactly as given, as a general-purpose agent would.
```

- [ ] **Step 2: Update `skills/init/SKILL.md` role-key resolution**

2a. Extend the role table header text: the table maps a role to BOTH its keys — change the intro to "Resolve each role's model key (`SUPER_MODEL_<ROLE>`) and effort key (`SUPER_EFFORT_<ROLE>`) per the resolution order above:" and add a column:

```markdown
| Model key | Effort key | Generated definition |
|---|---|---|
| SUPER_MODEL_PLANNER | SUPER_EFFORT_PLANNER | `.claude/agents/super-planner.md` |
| SUPER_MODEL_EXECUTOR | SUPER_EFFORT_EXECUTOR | `.claude/agents/super-executor.md` |
| SUPER_MODEL_PANEL | SUPER_EFFORT_PANEL | `.claude/agents/super-panel.md` |
| SUPER_MODEL_IMPLEMENTER | SUPER_EFFORT_IMPLEMENTER | `.claude/agents/super-implementer.md` |
| SUPER_MODEL_FIX_APPLIER | SUPER_EFFORT_FIX_APPLIER | `.claude/agents/super-fix-applier.md` |
| SUPER_MODEL_TASK_REVIEWER | SUPER_EFFORT_TASK_REVIEWER | `.claude/agents/super-task-reviewer.md` |
| SUPER_MODEL_RE_REVIEWER | SUPER_EFFORT_RE_REVIEWER | `.claude/agents/super-re-reviewer.md` |
| SUPER_MODEL_BRANCH_REVIEWER | SUPER_EFFORT_BRANCH_REVIEWER | `.claude/agents/super-branch-reviewer.md` |
| SUPER_MODEL_FIX_PLANNER | SUPER_EFFORT_FIX_PLANNER | `.claude/agents/super-fix-planner.md` |
```

2b. Replace the cc-only generation-rule list (`skills/init/SKILL.md:128-140`) with:

```markdown
<!-- cc-only:start -->
- **Generate when:** the model value is a **full model ID** (`^claude-`), OR the
  effort value is non-`inherit` (a tier-name model alone rides the Task call's
  `model:` parameter and needs no file). Render
  `${CLAUDE_PLUGIN_ROOT}/templates/super-role-agent.md` to the listed path (create
  `.claude/agents/` if needed), substituting `<role>` (the path's `super-` suffix,
  e.g. `planner`), `<KEY>` (both keys, comma-separated, when both pin), and:
  - the `model:` line — keep it only when the model value is non-`inherit`
    (tier names AND full IDs are both valid frontmatter `model:` values; an
    effort-only definition drops the line entirely);
  - the `effort:` line — keep it only when the effort value is non-`inherit`
    (claude domain: `low|medium|high|xhigh|max`).
  These files are **derived artifacts owned by init** — the
  `generated-by: superagent:init` marker line says so — and rewriting one whose
  pins drifted from `.superenv` is the point of this step, not an overwrite
  violation. Never touch a file at these paths that lacks the marker: report it
  as `conflict` and leave it.
- **Neither key requires a file, but the listed path exists with the marker:**
  delete it (a stale derived artifact) and report `removed (stale)`.
- **Neither key requires a file, no file present:** nothing to do.
<!-- cc-only:end -->
```

2c. In the cursor-only block (`skills/init/SKILL.md:141-154`), the generation trigger stays model-only; append one line inside the block: `Effort keys are not supported on Cursor: any non-inherit SUPER_EFFORT_* value → WARN and treat as inherit (never render an effort: line).`

- [ ] **Step 3: Update `skills/superrun/SKILL.md` Model policy** — after the full-model-ID sentence ending "never silently substitute a cheaper tier." (line 129), append to the same numbered item:

```markdown
   **Effort policy:** each role also has a `SUPER_EFFORT_<ROLE>` key (same names as the
   model keys). `inherit` = no override. A non-`inherit` effort can only ride the
   generated per-role agent definition (the Task tool has no effort parameter) — dispatch
   that role with `subagent_type: super-<role>` and omit `model:` (the definition carries
   both pins). A missing definition for a non-`inherit` effort key is the same hard error
   as the full-ID case: fail loudly and instruct a `superagent:init` re-run.
```

- [ ] **Step 4: Update `skills/superloop/SKILL.md` L7 panel dispatch** — in the Rung 1 sentence (`:582-588`), extend the full-model-ID condition: replace "if `SUPER_MODEL_PANEL` is a **full model ID** (`^claude-`, e.g. `claude-fable-5`) the Agent tool's tier-enum `model:` parameter rejects it — dispatch with `subagent_type: super-panel` instead" with "if `SUPER_MODEL_PANEL` is a **full model ID** (`^claude-`, e.g. `claude-fable-5`) **or `SUPER_EFFORT_PANEL` is non-`inherit`** (the Agent tool has no effort parameter; the pin rides the definition) — dispatch with `subagent_type: super-panel` instead" (rest of the sentence unchanged).

- [ ] **Step 5: Rebuild cursor and verify** — `scripts/build-cursor-skills.sh && scripts/build-cursor-skills.sh --check`; then `grep -rn "effort" cursor/skills/superrun/SKILL.md | head` — the effort-policy text must appear (it is canonical, not cc-only); `grep -c "cc-only" cursor/skills/init/SKILL.md` must print 0.

- [ ] **Step 6: Commit**

```bash
git add templates/super-role-agent.md skills/init/SKILL.md skills/superrun/SKILL.md skills/superloop/SKILL.md cursor/
git commit -m "feat: per-role reasoning-effort pins — template effort line, init generation rules, superrun/superloop dispatch policy"
```

---

### Task 5: `superagent:init` `.superenv` validation pass

**Files:**
- Modify: `skills/init/SKILL.md` (insert a new numbered step in the checklist right after the `.superenv` creation/read step, before role-key resolution)

**Interfaces:**
- Consumes: the key resolution helper already defined in the skill (`:41-42`).
- Produces: a per-key validation report table; resolved-with-fallback values feed the role-key resolution step.

- [ ] **Step 1: Insert the validation step** (canonical text; the per-build value domains use markers):

```markdown
### .superenv validation (lint — WARN + fallback, never abort)

Validate the RESOLVED configuration (env > repo `.superenv` > plugin default) before
using it. For each finding emit one WARN row in the summary; the effective value used
by later steps is the fallback shown. Never rewrite the user's `.superenv` — this is
report-only.

1. **Unknown keys:** every `SUPER_*`/`TICK_*` key present in the repo `.superenv` must
   also exist in `${CLAUDE_PLUGIN_ROOT}/templates/superenv.default`. Unknown → WARN
   "probable typo (ignored)".
2. **Enums** (out-of-domain → WARN, fall back to the template default):
   `SUPER_HARNESS` ∈ claude|cursor|codex; `SUPER_CODEX_SANDBOX` ∈
   workspace-write|danger-full-access; `SUPER_TEST_EVIDENCE` ∈ local|ci;
   `SUPER_MERGE_METHOD` ∈ squash|merge|rebase; `SUPER_BRANCH_STYLE` ∈ flat|slashed;
   `SUPER_PANEL_AGENT_TYPE` ∈ general-purpose|Explore;
   `SUPER_REVIEW_CONFIDENCE_FILTER` ∈ controller.
3. **Booleans** (∈ true|false, else WARN + template default): `SUPER_PROTECTED_MAIN`,
   `SUPER_ADMIN_MERGE`, `SUPER_CI_ONE_FLAG_PER_PUSH`, `SUPER_SKIP_FINISHING_HANDOFF`,
   `SUPER_GH_DISABLE_SANDBOX`.
4. **Numerics** (positive integer, else WARN + template default):
   `SUPER_HEAVY_STEP_LIMIT`, `SUPER_LOCK_STEAL_MIN`, `SUPER_CI_RUNNERS`.
   `SUPER_TICK_INTERVAL` must parse as an interval span (e.g. `600`, `90s`, `30m`, `2h`).
5. **Model keys** (each `SUPER_MODEL_*`):
<!-- cc-only:start -->
   valid = a tier name (`sonnet|opus|haiku|fable`), `inherit`, or a full Claude model
   ID (`^claude-`). Anything else → WARN, treat as `inherit` (catches typos like
   `sonet` before they become an agent definition that fails at spawn time).
<!-- cc-only:end -->
<!-- cursor-only:start
   valid = a Cursor model name (`agent --list-models`) or `inherit`. Claude tier names
   and `claude-*` IDs not in that list → WARN, treat as `inherit`.
cursor-only:end -->
<!-- codex-only:start
   valid = a Codex model name or `inherit`. A Claude tier name
   (`sonnet|opus|haiku|fable`) or Claude model ID (`^claude-`) → WARN, treat as
   `inherit` (a hand-trimmed `.superenv` can let the claude-flavored plugin default
   leak through).
codex-only:end -->
6. **Effort keys** (each `SUPER_EFFORT_*`):
<!-- cc-only:start -->
   valid = `low|medium|high|xhigh|max|inherit`; else WARN, treat as `inherit`.
<!-- cc-only:end -->
<!-- cursor-only:start
   effort is not supported on Cursor: anything but `inherit` → WARN, treat as `inherit`.
cursor-only:end -->
<!-- codex-only:start
   valid = `none|minimal|low|medium|high|xhigh|inherit`; else WARN (note: claude's
   `max` is NOT a Codex effort), treat as `inherit`.
codex-only:end -->
```

- [ ] **Step 2: Renumber/cross-reference** — the role-key resolution step must say it consumes "the validated values from the validation step above".

- [ ] **Step 3: Rebuild + verify markers** — `scripts/build-cursor-skills.sh && scripts/build-cursor-skills.sh --check`. NOTE: until Task 6 teaches the cursor build to DROP `codex-only` blocks, the codex-only text will leak into `cursor/skills/init/SKILL.md` as inert comment lines — acceptable for this commit ONLY if Task 6 lands in the same PR; verify after Task 6 that `grep -c "codex-only" cursor/skills/init/SKILL.md` is 0.

- [ ] **Step 4: Commit**

```bash
git add skills/init/SKILL.md cursor/
git commit -m "feat: superagent:init .superenv validation pass (unknown keys, enums, numerics, per-build model/effort domains)"
```

---

### Task 6: Teach `build-cursor-skills.sh` about `codex-only` markers and effort keys

**Files:**
- Modify: `scripts/build-cursor-skills.sh:44-56` (filter_markers), `:158-182` (superenv specialization)

**Interfaces:**
- Produces: cursor build drops `codex-only` blocks entirely; `cursor/templates/superenv.default` carries all-`inherit` effort keys with a Cursor-appropriate comment.

- [ ] **Step 1: Extend `filter_markers`** — add codex-only DROP rules (wrapper AND content):

```awk
/^[[:space:]]*<!-- codex-only:start[[:space:]]*$/ { cdrop=1; next }
/^[[:space:]]*codex-only:end -->[[:space:]]*$/    { cdrop=0; next }
cdrop                     { next }
```

(Place these BEFORE the cursor-only activation rules; add `cdrop` to the existing `drop { next }` logic as its own line as shown.)

- [ ] **Step 2: Specialize the effort block in the cursor superenv template** — extend the existing awk/sed stage: rewrite the effort header comment (the lines from `# ── Reasoning effort per agent role` through the `# NOTE (claude):` comment) to:

```
# ── Reasoning effort per agent role (NOT SUPPORTED on Cursor) ─────
# The Cursor CLI has no reasoning-effort control. Keys are kept for cross-harness
# .superenv portability; any non-inherit value is warned and treated as inherit.
```

and reset the six non-inherit defaults:

```bash
-e 's/^SUPER_EFFORT_IMPLEMENTER=medium/SUPER_EFFORT_IMPLEMENTER=inherit/' \
-e 's/^SUPER_EFFORT_FIX_APPLIER=medium/SUPER_EFFORT_FIX_APPLIER=inherit/' \
-e 's/^SUPER_EFFORT_TASK_REVIEWER=high/SUPER_EFFORT_TASK_REVIEWER=inherit/' \
-e 's/^SUPER_EFFORT_RE_REVIEWER=high/SUPER_EFFORT_RE_REVIEWER=inherit/' \
-e 's/^SUPER_EFFORT_BRANCH_REVIEWER=xhigh/SUPER_EFFORT_BRANCH_REVIEWER=inherit/' \
-e 's/^SUPER_EFFORT_FIX_PLANNER=high/SUPER_EFFORT_FIX_PLANNER=inherit/' \
```

Also drop the `SUPER_CODEX_SANDBOX` line from the cursor template (`-e '/^SUPER_CODEX_SANDBOX=/d'` plus its comment if on the same line).

- [ ] **Step 3: Rebuild and assert**

```bash
scripts/build-cursor-skills.sh && scripts/build-cursor-skills.sh --check
grep -c "codex-only" cursor/skills/init/SKILL.md          # expect 0
grep -c "SUPER_EFFORT_BRANCH_REVIEWER=inherit" cursor/templates/superenv.default  # expect 1
grep -c "SUPER_CODEX_SANDBOX" cursor/templates/superenv.default                   # expect 0
```

- [ ] **Step 4: Commit**

```bash
git add scripts/build-cursor-skills.sh cursor/
git commit -m "feat: cursor build drops codex-only markers; effort keys neutralized in cursor superenv"
```

---

### Task 7: `scripts/build-codex-skills.sh` — generate the `codex/` marketplace tree

**Files:**
- Create: `scripts/build-codex-skills.sh` (executable)
- Create (generated, committed): `codex/marketplace.json`, `codex/plugins/superagent/.codex-plugin/plugin.json`, `codex/plugins/superagent/skills/*/SKILL.md`, `codex/plugins/superagent/skills/codex-smoke-probe/SKILL.md`, `codex/templates/superenv.default`, `codex/templates/super-role-agent.md`, `codex/templates/vault-root.md`, `codex/README.md`

**Interfaces:**
- Consumes: canonical `skills/`, `templates/`, marker grammar (Global Constraints), version from `.claude-plugin/plugin.json`.
- Produces: the tree `superagent-tick.sh` checks (`codex/plugins/superagent/skills/superagent/SKILL.md`) and the marketplace `codex plugin marketplace add <repo>/codex` installs; `--check` mode.

Model the script on `scripts/build-cursor-skills.sh` (same structure: filter → substitute → banner → emit/check). Differences, in full:

- [ ] **Step 1: Write the script.** Header comment mirrors the cursor one (codex-only markers activated; cursor-only AND cc-only dropped). Key sections:

filter (drops cc-only + cursor-only blocks entirely, activates codex-only):

```awk
/<!-- cc-only:start -->/  { drop=1; next }
/<!-- cc-only:end -->/    { drop=0; next }
drop                      { next }
/<!-- cc-only -->/        { next }
/^[[:space:]]*<!-- cursor-only:start[[:space:]]*$/ { udrop=1; next }
/^[[:space:]]*cursor-only:end -->[[:space:]]*$/    { udrop=0; next }
udrop                     { next }
/^[[:space:]]*<!-- codex-only:start[[:space:]]*$/ { next }
/^[[:space:]]*codex-only:end -->[[:space:]]*$/    { next }
{ print }
```

substitutions:

```bash
sed \
  -e 's/\${CLAUDE_PLUGIN_ROOT}/\${SUPER_PLUGIN_ROOT}/g' \
  -e 's/claude -p/codex exec/g' \
  -e 's/claude --model/codex exec -m/g' \
  -e 's/ANTHROPIC_API_KEY/OPENAI_API_KEY/g' \
  -e 's/Claude CLI/Codex CLI/g' \
  -e 's/^driver: cron  .*/driver: external                  # the only driver in this build (external scheduler — fresh context per tick)/' \
  -e 's/^cron_id:  .*# CronCreate job id.*/cron_id:                          # unused in this build (Claude Code in-session driver only); leave empty/'
```

banner (inserted after each SKILL.md frontmatter, mirroring the cursor banner's insert_banner function verbatim):

```markdown
<!-- GENERATED FILE — Codex build. Do not edit by hand: edit the canonical skill under skills/
     in the plugin repository and re-run scripts/build-codex-skills.sh. -->

> **Codex build notes.**
> - Only the **external** driver exists in this build. Claude Code's in-session cron driver and its
>   `CronCreate` / `CronList` / `CronDelete` and `Monitor` tools do **not** exist on Codex — treat
>   any residual mention of them as inapplicable and NEVER attempt those tool calls.
> - Tool mapping: "Agent tool" / "spawn a subagent" = the `spawn_agent` tool (multi-agent v2 —
>   wait for the child's result). Role pins from `.superenv` map to its parameters:
>   `SUPER_MODEL_<ROLE>` → `model`, `SUPER_EFFORT_<ROLE>` → `reasoning_effort`
>   (`inherit` = omit the parameter). There are NO `.claude/agents/` definition files in this
>   build — where a skill says "dispatch via subagent_type: super-<role>", pass the role's
>   resolved model/effort as spawn parameters instead. "Skill tool" = reference the skill by
>   name in the conversation. `AskUserQuestion` / `AskQuestion` = ask the user in chat (attended
>   sessions only — never in a headless tick). `EnterWorktree` = not available; use
>   `git worktree` via shell.
> - `${SUPER_PLUGIN_ROOT}` in commands and paths = this plugin's installed root directory (the
>   one containing `skills/` and `templates/`). Substitute its absolute path wherever it appears.
> - Skill lookup: this plugin installs via the Codex plugin marketplace; skills resolve by name
>   (e.g. `superplan`). The `superagent` supervisor skill is driven by reading its SKILL.md
>   directly (the external tick's file-read prompt), never invoked by name.
```

superenv specialization: same awk header-rewrite pattern as the cursor build, with codex wording:

```
# Model values (Codex build): a Codex model name (e.g. gpt-5.1-codex) or "inherit".
# "inherit" = omit the model override; the CLI's config.toml default applies.
# Role pins dispatch as spawn_agent parameters — no agent-definition files on Codex.
# (SUPER_MODEL_SUPERVISOR goes straight to `codex exec -m`.)
```

plus seds: the six model-key resets to `inherit` (copy the cursor build's six lines verbatim), `s/(headless tick: opus)/(headless tick: the CLI default model)/`, `SUPER_HARNESS=claude…` → `SUPER_HARNESS=codex                     # this is the Codex build — the external driver fires the Codex CLI (codex exec)`. Rewrite the effort header's claude/cursor domain lines to the codex domain (`none | minimal | low | medium | high | xhigh`; drop the `max` line and the CLAUDE_CODE_EFFORT_LEVEL note). Keep the effort VALUES unchanged (`medium`/`high`/`xhigh` are valid Codex efforts — per the spec, defaults are identical across builds). Keep `SUPER_CODEX_SANDBOX=workspace-write`.

probe skill (`codex-smoke-probe`, generated only — mirror the cursor probe with these values): name `codex-smoke-probe`; step 3 checks `<plugin_root>/skills/superloop/SKILL.md` for "GENERATED FILE — Codex build" (MUST) and for "cc-only" AND "cursor-only" (must NOT — marker leakage); step 4 reports `echo "${CODEX_HOME:-unset}"` instead of CLAUDE_PLUGIN_ROOT; report keys: `superloop_has_codex_banner`, `env_codex_home`.

manifests:

`codex/plugins/superagent/.codex-plugin/plugin.json` (version read from `.claude-plugin/plugin.json` like the cursor build):

```json
{
  "name": "superagent",
  "description": "Plan-tree authoring (supergoal/superplan) and autonomy-loop execution (superagent/superrun) skills — Codex build (external unattended driver only)",
  "version": "${version}",
  "author": { "name": "Eugene Chai", "email": "eugene.chai@gmail.com" },
  "repository": "https://github.com/blackterrarium/superagent-plugin",
  "keywords": ["planning", "autonomy-loop", "subagents", "workflows"]
}
```

`codex/marketplace.json`:

```json
{
  "name": "superagent",
  "metadata": { "description": "superagent plugin marketplace (Codex build)", "version": "${version}" },
  "plugins": [
    {
      "name": "superagent",
      "source": { "source": "path", "path": "./plugins/superagent" },
      "description": "Plan-tree authoring and autonomy-loop execution skills — Codex build",
      "category": "workflows",
      "policy": { "installation": "manual", "authentication": "none" }
    }
  ]
}
```

NOTE: this manifest schema is best-known from Codex's plugin-creator docs; smoke T2 (`codex plugin marketplace add`) is the authority. If the CLI rejects it, fix the schema to what the CLI's error/docs dictate and record the correction in `codex/README.md`.

`codex/README.md`: mirror the cursor README structure with: install commands (`codex plugin marketplace add <repo>/codex`, `codex plugin add superagent@superagent`), auth (`OPENAI_API_KEY` in target repo `.env`, else `codex login` stored auth), sandbox knob (`SUPER_CODEX_SANDBOX`), model keys take Codex model names, effort keys take `none|minimal|low|medium|high|xhigh`, a "Validated" section stating **nothing is validated yet — run scripts/codex-smoke.sh and update this section from the report**, and Known gaps: `spawn_agent` availability in plain `codex exec` sessions unverified (T4); no end-to-end multi-tick loop exercised.

`--check` mode: identical contract to the cursor build (rebuild to temp, `diff -r`, exit 1 when stale, message names `scripts/build-codex-skills.sh`).

- [ ] **Step 2: Run it and eyeball the output**

```bash
chmod +x scripts/build-codex-skills.sh && scripts/build-codex-skills.sh
test -f codex/plugins/superagent/skills/superagent/SKILL.md && echo tree-ok
grep -c "cc-only\|cursor-only" codex/plugins/superagent/skills/superloop/SKILL.md  # expect 0
grep -c "GENERATED FILE — Codex build" codex/plugins/superagent/skills/superagent/SKILL.md  # expect 1
grep -c "SUPER_HARNESS=codex" codex/templates/superenv.default  # expect 1
grep -c "SUPER_EFFORT_BRANCH_REVIEWER=xhigh" codex/templates/superenv.default  # expect 1 (defaults preserved)
scripts/build-codex-skills.sh --check  # expect: up to date
```

- [ ] **Step 3: Re-run the Task 2 stub test** (`bash /tmp/t_tick.sh`) — it fabricates then deletes `codex/`; with the real tree now committed, EDIT the test first to remove its `mkdir/touch/rm -rf "$ROOT/codex"` lines. Expect `OK`.

- [ ] **Step 4: Commit**

```bash
git add scripts/build-codex-skills.sh codex/
git commit -m "feat: codex build — generated plugin-marketplace tree (build-codex-skills.sh)"
```

---

### Task 8: `scripts/codex-smoke.sh` — T1–T6 verification harness

**Files:**
- Create: `scripts/codex-smoke.sh`

**Interfaces:**
- Consumes: `codex/` tree (Task 7), `scripts/build-codex-skills.sh`.
- Produces: `codex-smoke-report.md` at the repo root; T2/T4 failures are DESIGN-INPUT changes (stop and reassess skill delivery / subagent mapping per the spec).

- [ ] **Step 1: Write the script.** Copy `scripts/cursor-smoke.sh`'s skeleton exactly (report framing, `run_test` with truncation, PASS/FAIL counters, exit 0 always, neutral-workspace `mktemp -d`), with these changes: `REPORT="$ROOT/codex-smoke-report.md"`, `PLUGIN="$ROOT/codex"`, rebuild via `build-codex-skills.sh`, `BIN` lookup tries only `codex`, install hint `npm install -g @openai/codex`. Tests:

```bash
# T1 — CLI sanity: headless exec + auth work at all.
run_test "T1 headless sanity" "SMOKE-OK" \
  codex exec --skip-git-repo-check -C "$NEUTRAL" "Reply with exactly: SMOKE-OK"

# T2 — marketplace + plugin install (the skill-delivery mechanism; failure = design-input change).
run_test "T2 marketplace add" "" codex plugin marketplace add "$PLUGIN"
run_test "T2b plugin add" "" codex plugin add superagent@superagent

# T3 — skill enumeration from a neutral workspace (informational).
run_test "T3 skill enumeration (informational)" "" \
  codex exec --skip-git-repo-check -C "$NEUTRAL" \
  "List the names of ALL skills available to you, including plugin-provided ones. Output only the names, one per line. If none, output NONE."

# T4a — probe skill: plugin mechanism + relative file access.
run_test "T4a probe skill (neutral workspace)" "PROBE-BEGIN" \
  codex exec --skip-git-repo-check -C "$NEUTRAL" \
  "Run the codex smoke probe skill (codex-smoke-probe) and output its report. If you cannot find any such skill, output exactly: NO-SUCH-SKILL"

# T4b — spawn_agent availability (failure = design-input change for subagent mapping).
run_test "T4b spawn_agent available" "SPAWN-OK" \
  codex exec --skip-git-repo-check -C "$NEUTRAL" \
  "Do you have a tool named spawn_agent (or an equivalent tool for spawning a sub-agent with its own model/reasoning_effort)? If yes, spawn one agent with the message 'Reply with exactly: CHILD-OK', wait for its result, then output exactly: SPAWN-OK <its reply>. If no such tool exists, output exactly: NO-SPAWN-TOOL."

# T5 — the REAL external-tick mechanism: file-read prompt, superagent hard gate.
run_test "T5 tick file-read + superagent hard gate" "requires a master plan" \
  codex exec --skip-git-repo-check -C "$NEUTRAL" \
  "Read the file $PLUGIN/plugins/superagent/skills/superagent/SKILL.md and follow it: execute exactly ONE tick with no arguments (no PLAN.md, no loop file), in unattended/non-interactive mode. Show the skill's response. If you cannot read that file, output exactly: CANNOT-READ."

# T6 — effort override pass-through on this CLI version.
run_test "T6 effort override accepted" "SMOKE-OK" \
  codex exec --skip-git-repo-check -C "$NEUTRAL" -c model_reasoning_effort=low "Reply with exactly: SMOKE-OK"
```

All `codex exec` tests run with the default (read-only-ish) sandbox — no `--yolo` in smoke. The summary section reminds: "Send this file back to the session driving the Codex port; T2/T4b failures change the design (skill delivery / subagent mapping) — do not patch around them."

- [ ] **Step 2: Syntax-check without the CLI** — `bash -n scripts/codex-smoke.sh` and, on a host without codex, run it: expected `FATAL — no Codex CLI found`, report written, exit 0.

- [ ] **Step 3: Commit**

```bash
git add scripts/codex-smoke.sh
git commit -m "feat: codex smoke harness (T1-T6) mirroring cursor-smoke"
```

---

### Task 9: Docs — README, scripts/README, CHANGELOG

**Files:**
- Modify: `README.md` (harness section: add codex alongside cursor — install, auth, sandbox knob, model/effort key domains, smoke pointer)
- Modify: `scripts/README.md` (mention `build-codex-skills.sh`, `codex-smoke.sh`, `--harness codex`, exit code 8)
- Modify: `CHANGELOG.md` (new entry, version per repo convention — inspect the last entry's format, e.g. `0.3.0`, and add `0.4.0`)

- [ ] **Step 1: Write the docs.** README harness section content: `SUPER_HARNESS=codex` fires `codex exec` per tick; install = `codex plugin marketplace add <repo>/codex && codex plugin add superagent@superagent`; auth = `OPENAI_API_KEY` in the target repo's `.env` else `codex login` stored auth; sandbox = `SUPER_CODEX_SANDBOX` (`workspace-write` default → `--sandbox workspace-write` + network access config; `danger-full-access` → `--yolo`); model keys take Codex model names, effort keys take `none|minimal|low|medium|high|xhigh`; per-role effort ships defaults (`medium`/`high`/`xhigh` workers) in every build. CHANGELOG entry lists: codex harness, SUPER_EFFORT_* keys + defaults, SUPER_CODEX_SANDBOX, init validation pass, --effort on claude ticks, codex build + smoke.

- [ ] **Step 2: Verify builds one last time** — `scripts/build-cursor-skills.sh --check && scripts/build-codex-skills.sh --check` (README/CHANGELOG are not build inputs; this catches anything stale from earlier tasks).

- [ ] **Step 3: Commit**

```bash
git add README.md scripts/README.md CHANGELOG.md
git commit -m "docs: codex harness, effort keys, init validation"
```

---

### Task 10: Final verification and PR

**Files:** none (verification + PR only)

- [ ] **Step 1: Full check suite**

```bash
bash /tmp/t_common.sh && bash /tmp/t_tick.sh
scripts/build-cursor-skills.sh --check && scripts/build-codex-skills.sh --check
bash -n scripts/superagent-tick.sh scripts/_common.sh scripts/build-codex-skills.sh scripts/codex-smoke.sh
command -v shellcheck >/dev/null && shellcheck -S warning scripts/_common.sh scripts/superagent-tick.sh scripts/build-codex-skills.sh scripts/codex-smoke.sh || true
grep -rn "codex-only\|cursor-only\|cc-only" codex/plugins/superagent/skills/ && echo "MARKER LEAK" || echo "markers clean"
```

- [ ] **Step 2: Spec sweep** — reread `docs/superpowers/specs/2026-08-12-codex-harness-design.md` section by section; confirm each requirement maps to a commit. Known deferred items (spec-sanctioned, live in `codex/README.md` Known gaps): smoke T-runs on a codex host, end-to-end loop.

- [ ] **Step 3: Push and open the PR**

```bash
git push -u origin codex-harness
gh pr create --title "feat: codex harness (SUPER_HARNESS=codex) with per-role reasoning effort and init validation" --body "$(cat <<'EOF'
Implements docs/superpowers/specs/2026-08-12-codex-harness-design.md:

- SUPER_HARNESS=codex — external driver fires `codex exec` per tick (sandbox knob SUPER_CODEX_SANDBOX, model/effort pass-through, exit codes 7/8)
- Per-role reasoning effort: SUPER_EFFORT_* keys + shipped defaults; --effort on claude ticks; effort: frontmatter in generated role definitions; spawn_agent reasoning_effort mapping on codex
- superagent:init .superenv validation pass (WARN + fallback, report-only)
- Generated codex/ plugin-marketplace build (build-codex-skills.sh, --check mode) + codex-smoke.sh (T1–T6)
- Cursor build: drops codex-only markers, neutralizes effort keys

NOT yet validated on a live codex host — run scripts/codex-smoke.sh and update codex/README.md from the report before first real use. T2/T4b smoke failures are design-input changes.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review Notes (kept for the executor)

- Spec coverage: §1 architecture → Tasks 1–2; §2 driver → Tasks 1–3; §3 build/banner/guard → Tasks 5 (guard text), 7; §4 config/init/role-definitions → Tasks 2 (sandbox key), 4, 5; §5 verification → Task 8; error-handling summary → Tasks 1–2 (exit codes), 7 (--check).
- The `SUPER_BRANCH_STYLE` enum domain (`flat|slashed`) in Task 5 is inferred from the template comment ("flat = no slashes"); if the skills define other accepted values, widen the domain to what `grep -rn SUPER_BRANCH_STYLE skills/` shows rather than warning on a value the loop actually honors.
- Task 7's marketplace.json schema is best-known, validated by smoke T2 — the ONE place execution may lawfully deviate from this plan's literal content; record any correction in `codex/README.md`.
