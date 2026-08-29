# Pi Harness (`SUPER_HARNESS=pi`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the Pi CLI drive the superagent external loop (`SUPER_HARNESS=pi`), with the supervisor's own dispatches (superplan, superrun, the L7 panel) running as bridged child CLI processes and superrun's SDD children running through `pi-subagents` when it is installed.

**Architecture:** A fourth `SUPER_HARNESS` value adds a `pi -p` tick branch (skills delivered by `--skill <repo>/pi/skills`, no install step). The Pi supervisor never uses an in-process subagent tool: superplan and superrun are blocking `bash` calls to `scripts/role-bridge.sh` (whose `pi` branch grows `--tools` sets, `--approve`, `--no-session`, `--skill`, `--thinking`), and the L7 panel is one blocking call to a new `scripts/bridge-fanout.sh`. superrun's SDD children follow superpowers' own Pi mapping — `pi-subagents`' `subagent` tool with `async: false` — with role pins riding `init`-generated `.pi/agents/super-<role>.md` definitions rendered from two new Pi templates. A generated `pi/` build tree (new `pi-only` markers) and `scripts/pi-smoke.sh` complete the port on the Codex pattern.

**Tech Stack:** bash (driver scripts; offline tests with PATH shims in `scripts/bridge-test.sh`), Markdown skill files with `cc-only` / `cursor-only` / `codex-only` / `pi-only` build markers, `scripts/build-*-skills.sh` generators, Pi CLI 0.84.x (`@earendil-works/pi-coding-agent`), `pi-subagents` ≥0.58.0 (optional).

**Spec:** `docs/superpowers/specs/2026-08-29-pi-harness-design.md`

## Global Constraints

- Version bump to **0.6.0** in `.claude-plugin/plugin.json`; all four generated builds read it from there.
- Harness vocabulary is exactly `claude | codex | cursor | pi`, everywhere (`SUPER_HARNESS`, `--harness`, role prefixes).
- `SUPER_MODEL_SUPERVISOR` must be native to `SUPER_HARNESS` (tick exit 11, unchanged). A Pi supervisor model must be `<provider>/<id>` — exactly one `/` (tick exit 8).
- Pi effort domain is `off|minimal|low|medium|high|xhigh|max` on every harness's handling of `pi:` roles (`_common.sh`, `init`, bridge, tick, templates).
- Bridge exit codes stay `0` ok · `2` binary not found · `3` CLI exited non-zero · `4` empty result · `64` usage. Fan-out exit codes: `0` all ok · `3` any panelist failed/timed out · `64` usage.
- Every headless Pi run started by the driver or the bridge passes `--approve`; bridged Pi children also pass `--no-session`.
- `pi-subagents` is **recommended, not required**: floor `>=0.58.0`; `SUPER_PI_SUBAGENTS=recommended|required|off` (default `recommended`).
- Never `${N:?}` in `_common.sh` (sourced under `set -u`; use `${1:-}` + explicit checks). Never set `CLAUDE_CODE_EFFORT_LEVEL`.
- Generated builds (`codex/`, `cursor/`, `pi/`) are committed artifacts: after any change to a canonical skill, template, or build script, re-run all build scripts and commit the trees; every `scripts/build-*-skills.sh --check` must exit 0.
- `scripts/bridge-test.sh` must exit 0 after every task that touches `scripts/`.
- Commit after every task; all work on branch `spec/pi-harness` (already holds the spec); PR into `main` at the end (protected main).

---

## File map

| Path | Responsibility |
|---|---|
| `scripts/_common.sh` | `pi` in `superagent_harness`/`ensure_cli_bin`; new `ensure_pi_bin`; widened Pi effort domain. |
| `scripts/role-bridge.sh` | Pi branch: `--tools role\|planner\|executor` sets, `--approve --no-session`, `--skill $SUPERAGENT_PI_SKILLS`, `--thinking` when model is `inherit`; `planner` set on claude. |
| `scripts/bridge-fanout.sh` (new) | Run N bridge invocations concurrently, hard timeout, framed ordered output. |
| `scripts/bridge-test.sh` | Offline shim tests for the above (extended). |
| `scripts/superagent-tick.sh` | `pi` tick branch: build check, model/effort, `--skill`, `--approve`, `--mode json`, `SUPERAGENT_PI_SKILLS` export, auth note. |
| `scripts/launch.sh`, `scripts/install-timer.sh`, `scripts/bootstrap.sh` | Accept `pi` in `--harness`; bootstrap fires `pi -p`. |
| `templates/superenv.default` | `SUPER_HARNESS` comment; Pi effort domain; new `SUPER_PI_SUBAGENTS`. |
| `templates/super-role-pi-agent.md` (new) | `pi-subagents` agent definition for a native Pi S3 role (model/thinking pins). |
| `templates/super-role-pi-bridge-agent.md` (new) | `pi-subagents` relay definition for a foreign-harness S3 role. |
| `skills/init/SKILL.md` | `pi-only` blocks: prerequisites, validation, Step 3 definitions into `.pi/agents/`. |
| `skills/superagent/SKILL.md` | `pi-only` blocks: S1/S2 bridge dispatch, model resolution, "Running from the Pi CLI", Step 0.5. |
| `skills/superloop/SKILL.md` | `pi-only` block: L7 Rung 1 via `bridge-fanout.sh`. |
| `skills/superrun/SKILL.md` | `pi-only` blocks: S3 dispatch via `pi-subagents` / sequential fallback; effort policy. |
| `scripts/build-pi-skills.sh` (new) → `pi/` | Generated Pi package: filtered skills, probe skill, templates, scripts, README, `package.json`. |
| `scripts/build-codex-skills.sh`, `scripts/build-cursor-skills.sh` | Drop `pi-only` blocks. |
| `scripts/pi-smoke.sh` (new) | Live probes P1–P4 and tests T1–T5; writes `pi-smoke-report.md`. |
| `README.md`, `scripts/README.md`, `CHANGELOG.md`, `.claude-plugin/plugin.json`, `.gitignore` | Docs, version, ignore the smoke report. |

---

### Task 1: `_common.sh` — `pi` harness, `ensure_pi_bin`, widened effort domain

**Files:**
- Modify: `scripts/_common.sh:84-90` (`superagent_harness`), `:114-124` (`superagent_effort_valid`), `:141-158` (`ensure_codex_bin` / `ensure_cli_bin`)
- Test: `scripts/bridge-test.sh` (the `_common.sh role parser` section at the end)

**Interfaces:**
- Produces: `superagent_harness` echoes `pi` when `SUPER_HARNESS=pi`; `ensure_pi_bin` (fatal, install hint); `ensure_cli_bin` → `ensure_pi_bin` for `pi`; `superagent_effort_valid pi <e>` accepts `off|minimal|low|medium|high|xhigh|max`. Consumed by Tasks 2, 4, 6.

- [ ] **Step 1: Add failing tests to `bridge-test.sh`**

Append to the `# ── _common.sh role parser ──` section, before the final `echo "bridge-test: …"`:

```bash
check "effort: pi xhigh ok"           superagent_effort_valid pi xhigh
check "effort: pi max ok"             superagent_effort_valid pi max
if superagent_effort_valid pi ultra; then fail "effort: pi ultra rejected"; else ok "effort: pi ultra rejected"; fi
check "harness: pi accepted"          bash -c "SUPER_HARNESS=pi; . '$ROOT/scripts/_common.sh'; [ \"\$(superagent_harness)\" = pi ]"
check "harness: bad value rejected"   bash -c "SUPER_HARNESS=hermes; . '$ROOT/scripts/_common.sh'; ! superagent_harness 2>/dev/null"
check "ensure_cli_bin: pi resolves"   bash -c "SUPER_HARNESS=pi; . '$ROOT/scripts/_common.sh'; ensure_cli_bin"
check "ensure_pi_bin: missing → hint" bash -c "PATH=/usr/bin:/bin; . '$ROOT/scripts/_common.sh'; ensure_pi_bin 2>&1 | grep -q 'npm install -g @earendil-works/pi-coding-agent'"
```

(`ensure_cli_bin: pi resolves` passes because the test's PATH shim dir already provides a `pi` shim.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `bash scripts/bridge-test.sh | grep -E 'pi (xhigh|max|ultra)|harness:|ensure_'`
Expected: `FAIL - effort: pi xhigh ok`, `FAIL - effort: pi max ok`, `FAIL - harness: pi accepted`, `FAIL - ensure_cli_bin: pi resolves`, `FAIL - ensure_pi_bin: missing → hint` (the `ultra` and `bad value` rows already pass).

- [ ] **Step 3: Implement in `_common.sh`**

Replace `superagent_harness`:

```bash
superagent_harness() {
  local h="${SUPER_HARNESS:-claude}"
  case "$h" in
    claude|cursor|codex|pi) echo "$h" ;;
    *) echo "superagent: bad SUPER_HARNESS '$h' (want claude|cursor|codex|pi)" >&2; return 1 ;;
  esac
}
```

In `superagent_effort_valid`, replace the `pi)` arm:

```bash
    pi)     case "$e" in off|minimal|low|medium|high|xhigh|max) return 0 ;; esac ;;
```

After `ensure_codex_bin`, add:

```bash
# Fatal check: the Pi CLI (`pi`) must be findable.
ensure_pi_bin() {
  _superagent_augment_path
  if ! command -v pi >/dev/null 2>&1; then
    echo "superagent: Pi CLI not found on PATH (tried: pi; checked incl. ~/.local/bin, /usr/local/bin). Install it (npm install -g @earendil-works/pi-coding-agent) or add its directory to PATH in the scheduler env; aborting." >&2
    return 1
  fi
  return 0
}
```

In `ensure_cli_bin`, add the arm `pi)     ensure_pi_bin ;;` before `*)`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `bash scripts/bridge-test.sh | tail -1`
Expected: `bridge-test: 0 failure(s)`

- [ ] **Step 5: Commit**

```bash
git add scripts/_common.sh scripts/bridge-test.sh
git commit -m "feat(pi): accept SUPER_HARNESS=pi, ensure_pi_bin, widen pi effort domain to off..max"
```

---

### Task 2: `role-bridge.sh` — Pi branch grows tools sets, trust, skills, `--thinking`

**Files:**
- Modify: `scripts/role-bridge.sh:1-30` (header comment), `:33-56` (tools parsing), `:110-127` (pi branch)
- Test: `scripts/bridge-test.sh` (`# ── pi ──` and `# ── pi effort-suffix edge cases ──` sections; claude `--tools` rows)

**Interfaces:**
- Consumes: nothing new.
- Produces: `--tools role|planner|executor|<list>` — on `pi`: `role`/`planner` → `--tools read,edit,write,bash,grep,find,ls`; `executor` → no `--tools` flag; `<list>` verbatim. On `claude`: `planner` → `--allowedTools Read,Edit,Write,Bash,Grep,Glob,Task,Skill` (same as `executor`). Env `SUPERAGENT_PI_SKILLS=<dir>` → `--skill <dir>` on Pi children. Pi children always get `--approve --no-session`. `--model inherit --effort <e>` on Pi → `--thinking <e>`. Consumed by Tasks 3, 4, 6, 8.

- [ ] **Step 1: Update the Pi tests in `bridge-test.sh` to the new argv**

Replace the whole `# ── pi ──` block with:

```bash
# ── pi ──
out="$("$BRIDGE" --harness pi --model openai/gpt-5 --effort high --cwd "$T/cwd" --prompt-file "$T/prompt.txt" 2>/dev/null)"
check "pi: stdout"  [ "$out" = "RESULT-pi" ]
check "pi: model with level suffix + role tools" [ "$(argv pi)" = "-p --approve --no-session --model openai/gpt-5:high --tools read,edit,write,bash,grep,find,ls " ]
check "pi: prompt on stdin" cmp -s "$T/pi.stdin" "$T/prompt.txt"
"$BRIDGE" --harness pi --model openai/gpt-5 --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1
check "pi: no suffix when effort inherit" [ "$(argv pi)" = "-p --approve --no-session --model openai/gpt-5 --tools read,edit,write,bash,grep,find,ls " ]
"$BRIDGE" --harness pi --model inherit --effort inherit --tools planner --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1
check "pi: --tools planner = role set" [ "$(argv pi)" = "-p --approve --no-session --tools read,edit,write,bash,grep,find,ls " ]
"$BRIDGE" --harness pi --model inherit --effort inherit --tools executor --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1
check "pi: --tools executor = no --tools flag" [ "$(argv pi)" = "-p --approve --no-session " ]
"$BRIDGE" --harness pi --model inherit --effort inherit --tools "read,bash" --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1
check "pi: --tools explicit list" [ "$(argv pi)" = "-p --approve --no-session --tools read,bash " ]
SUPERAGENT_PI_SKILLS="$T/skills" "$BRIDGE" --harness pi --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1
check "pi: SUPERAGENT_PI_SKILLS → --skill" [ "$(argv pi)" = "-p --approve --no-session --skill $T/skills --tools read,edit,write,bash,grep,find,ls " ]
```

Replace the `# ── pi effort-suffix edge cases ──` block with:

```bash
# ── pi effort edge cases ──
"$BRIDGE" --harness pi --model inherit --effort high --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>"$T/errpi1"
check "pi: --thinking when model inherit" [ "$(argv pi)" = "-p --approve --no-session --thinking high --tools read,edit,write,bash,grep,find,ls " ]
if grep -q "dropped" "$T/errpi1"; then fail "pi: no 'dropped' warning any more"; else ok "pi: no 'dropped' warning any more"; fi
"$BRIDGE" --harness pi --model openai/gpt-5:high --effort low --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>"$T/errpi2"
check "pi: no double suffix" [ "$(argv pi)" = "-p --approve --no-session --model openai/gpt-5:high --tools read,edit,write,bash,grep,find,ls " ]
check "pi: WARN on already-pinned level" grep -q "already pins a level" "$T/errpi2"
```

Add after the existing `claude: --tools executor allowlist` row:

```bash
"$BRIDGE" --harness claude --model opus --effort high --tools planner --cwd "$T/cwd" --prompt-file "$T/prompt.txt" --role planner >/dev/null 2>&1
check "claude: --tools planner allowlist" [ "$(argv claude)" = "-p --model opus --effort high --allowedTools Read,Edit,Write,Bash,Grep,Glob,Task,Skill " ]
```

- [ ] **Step 2: Run the tests to verify the new rows fail**

Run: `bash scripts/bridge-test.sh | grep -E '^FAIL'`
Expected: every `pi:` row above and `claude: --tools planner allowlist` listed as FAIL; nothing else.

- [ ] **Step 3: Implement**

Header comment: replace the `--tools (claude harness only; …)` paragraph with:

```bash
# --tools picks the child's tool allowlist (claude: --allowedTools; pi: --tools; codex/cursor: ignored):
#   role     (default) claude Read,Edit,Write,Bash,Grep,Glob · pi read,edit,write,bash,grep,find,ls —
#            a leaf role (implementer/reviewer/panelist)
#   planner  a superplan dispatch: claude adds Task,Skill (it invokes skills); pi = the role set
#   executor a controller role (superrun) that must dispatch subagents and invoke skills itself:
#            claude Read,Edit,Write,Bash,Grep,Glob,Task,Skill; pi = NO --tools flag (built-ins plus
#            extension tools such as pi-subagents' `subagent`). This is how superagent runs superrun
#            as the TOP-LEVEL agent of its own CLI process (issue #25): a subagent cannot
#            foreground-wait on its own children, so the SDD controller has to be depth 0 in some process.
#   <list>   an explicit comma-separated allowlist in the harness's own tool names.
# Pi children always run with --approve (project trust for one run; the operator chose the repo)
# and --no-session (a bridged run is ephemeral; the log file is its record). When
# SUPERAGENT_PI_SKILLS is set (exported by superagent-tick.sh on the pi harness) it is passed as
# --skill so the child sees the plugin's skills.
```

Tools parsing — replace the `TOOLS_*` constants and the `case "$tools"` block:

```bash
TOOLS_ROLE="Read,Edit,Write,Bash,Grep,Glob"
TOOLS_EXECUTOR="Read,Edit,Write,Bash,Grep,Glob,Task,Skill"
TOOLS_PI_ROLE="read,edit,write,bash,grep,find,ls"
…
case "$tools" in
  role)     allowed="$TOOLS_ROLE";     pi_allowed="$TOOLS_PI_ROLE" ;;
  planner)  allowed="$TOOLS_EXECUTOR"; pi_allowed="$TOOLS_PI_ROLE" ;;
  executor) allowed="$TOOLS_EXECUTOR"; pi_allowed="" ;;
  "")       echo "role-bridge: --tools must be role|planner|executor|<comma-separated list> (got '')" >&2; exit 64 ;;
  *)        allowed="$tools";          pi_allowed="$tools" ;;
esac
```

Pi branch — replace the whole `pi)` arm:

```bash
  pi)
    args=(-p --approve --no-session)
    [ -n "${SUPERAGENT_PI_SKILLS:-}" ] && args+=(--skill "$SUPERAGENT_PI_SKILLS")
    # pi carries the thinking level as a ":<level>" suffix on the model string. With no model
    # the CLI's --thinking flag carries it instead. An explicit level already on the model
    # ("openai/gpt-5:high") wins — never suffix twice.
    m="$model"
    if [ "$effort" != inherit ]; then
      if [ "$model" = inherit ]; then
        args+=(--thinking "$effort")
      elif printf '%s' "$m" | grep -q ':[A-Za-z0-9_-]*$'; then
        echo "role-bridge: warning — --model '$m' already pins a level; ignoring --effort '$effort'" >&2
      else
        m="${m}:${effort}"
      fi
    fi
    [ "$model" != inherit ] && args+=(--model "$m")
    [ -n "$pi_allowed" ] && args+=(--tools "$pi_allowed")
    result="$(cd "$cwd" && pi "${args[@]}" <"$prompt_file" 2>>"$log")" || rc=$?
    ;;
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `bash scripts/bridge-test.sh | tail -1`
Expected: `bridge-test: 0 failure(s)`

- [ ] **Step 5: Commit**

```bash
git add scripts/role-bridge.sh scripts/bridge-test.sh
git commit -m "feat(bridge): pi branch — tools sets, --approve/--no-session, --skill passthrough, --thinking; planner tools set"
```

---

### Task 3: `scripts/bridge-fanout.sh` — concurrent bridge runs with a hard timeout

**Files:**
- Create: `scripts/bridge-fanout.sh`
- Test: `scripts/bridge-test.sh` (new `# ── bridge-fanout ──` section; extend `mkshim` with a `slow` mode)

**Interfaces:**
- Consumes: `scripts/role-bridge.sh` CLI (Task 2); env `SUPERAGENT_BRIDGE` (optional override of the bridge path).
- Produces: `bridge-fanout.sh --harness <h> --model <m> --effort <e> --cwd <dir> [--tools role] [--role panelist] [--timeout <sec>] --prompt-file <f> [--prompt-file <f>…]`. stdout: for each prompt file, in order, `=== PANELIST <n> exit=<rc> ===`, the bridge stdout (or a `BRIDGE-FAILED exit=<rc> harness=<h> role=<role>-<n> log=<path>` line), `=== END <n> ===`. Exit 0 all ok · 3 any failed · 64 usage. Consumed by Task 6 (superloop L7) and Task 8.

- [ ] **Step 1: Add the `slow` shim mode and failing tests**

In `mkshim`, change the `case "\${SHIM_MODE:-ok}"` to:

```bash
case "\${SHIM_MODE:-ok}" in
  fail) echo "boom" >&2; exit 9 ;;
  empty) exit 0 ;;
  slow) sleep 30; echo "RESULT-$name"; exit 0 ;;
esac
```

Append before the `# ── _common.sh role parser ──` section:

```bash
# ── bridge-fanout ──
FANOUT="$ROOT/scripts/bridge-fanout.sh"
printf 'panel prompt one\n' >"$T/p1.txt"; printf 'panel prompt two\n' >"$T/p2.txt"; printf 'panel prompt three\n' >"$T/p3.txt"
out="$("$FANOUT" --harness pi --model openai/gpt-5 --effort high --cwd "$T/cwd" --prompt-file "$T/p1.txt" --prompt-file "$T/p2.txt" --prompt-file "$T/p3.txt" 2>"$T/fanerr")"; rc=$?
check "fanout: exit 0 when all ok" [ "$rc" -eq 0 ]
check "fanout: three framed results in order" bash -c "printf '%s\n' \"\$1\" | grep -n -E '^=== (PANELIST [123] exit=0|END [123]) ===$' | tr '\n' ' ' | grep -q '^1:=== PANELIST 1 exit=0 === 3:=== END 1 === 4:=== PANELIST 2 exit=0 === 6:=== END 2 === 7:=== PANELIST 3 exit=0 === 9:=== END 3 === $'" _ "$out"
check "fanout: each block carries the bridge stdout" [ "$(printf '%s\n' "$out" | grep -c '^RESULT-pi$')" -eq 3 ]
out="$(SHIM_MODE=slow "$FANOUT" --harness pi --model inherit --effort inherit --cwd "$T/cwd" --timeout 2 --prompt-file "$T/p1.txt" --prompt-file "$T/p2.txt" 2>/dev/null)"; rc=$?
check "fanout: exit 3 on timeout" [ "$rc" -eq 3 ]
check "fanout: timed-out panelist is BRIDGE-FAILED" bash -c "printf '%s\n' \"\$1\" | grep -q '^BRIDGE-FAILED exit=[0-9]* harness=pi role=panelist-1 log='" _ "$out"
out="$(SHIM_MODE=fail "$FANOUT" --harness pi --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/p1.txt" 2>/dev/null)"; rc=$?
check "fanout: exit 3 when a bridge fails" [ "$rc" -eq 3 ]
check "fanout: failed panelist framed with exit=3" bash -c "printf '%s\n' \"\$1\" | grep -q '^=== PANELIST 1 exit=3 ===$'" _ "$out"
"$FANOUT" --harness pi --model inherit --effort inherit --cwd "$T/cwd" >/dev/null 2>&1; rc=$?
check "fanout: usage error without prompt files" [ "$rc" -eq 64 ]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `bash scripts/bridge-test.sh | grep -E '^FAIL - fanout'`
Expected: every `fanout:` row FAIL (script does not exist).

- [ ] **Step 3: Write `scripts/bridge-fanout.sh`**

```bash
#!/usr/bin/env bash
# bridge-fanout.sh — run N role-bridge.sh invocations CONCURRENTLY and block until all finish.
#
#   bridge-fanout.sh --harness <h> --model <m|inherit> --effort <e|inherit> --cwd <dir>
#                    [--tools role|planner|executor|<list>] [--role <name>] [--timeout <sec>]
#                    --prompt-file <f> [--prompt-file <f> ...]
#
# The L7 panel primitive for harnesses with no blocking parallel subagent tool (pi): the supervisor
# makes ONE blocking shell call and gets every panelist's verdict back — "wait, never poll".
# Each prompt file becomes one role-bridge.sh child (--role <name>-<n>). stdout, in prompt-file
# order:
#   === PANELIST <n> exit=<rc> ===
#   <the bridge's stdout>            (or: BRIDGE-FAILED exit=<rc> harness=<h> role=<name>-<n> log=<path>)
#   === END <n> ===
# --timeout (default 1800 s): after it elapses, still-running children are killed (with their
# CLI grandchildren) and reported as failed. Exit: 0 every child ok · 3 any child failed or timed
# out · 64 usage. Env: SUPERAGENT_BRIDGE overrides the bridge path (default: sibling role-bridge.sh).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRIDGE="${SUPERAGENT_BRIDGE:-$SCRIPT_DIR/role-bridge.sh}"

harness=""; model="inherit"; effort="inherit"; cwd=""; tools="role"; role="panelist"; timeout=1800
files=()
usage() { echo "bridge-fanout: $1" >&2; exit 64; }
while [ $# -gt 0 ]; do
  case "$1" in
    --harness)     [ $# -ge 2 ] || usage "--harness requires a value"; harness="$2"; shift 2 ;;
    --model)       [ $# -ge 2 ] || usage "--model requires a value"; model="$2"; shift 2 ;;
    --effort)      [ $# -ge 2 ] || usage "--effort requires a value"; effort="$2"; shift 2 ;;
    --cwd)         [ $# -ge 2 ] || usage "--cwd requires a value"; cwd="$2"; shift 2 ;;
    --tools)       [ $# -ge 2 ] || usage "--tools requires a value"; tools="$2"; shift 2 ;;
    --role)        [ $# -ge 2 ] || usage "--role requires a value"; role="$2"; shift 2 ;;
    --timeout)     [ $# -ge 2 ] || usage "--timeout requires a value"; timeout="$2"; shift 2 ;;
    --prompt-file) [ $# -ge 2 ] || usage "--prompt-file requires a value"; files+=("$2"); shift 2 ;;
    *) usage "unknown argument '$1'" ;;
  esac
done
[ -n "$harness" ] || usage "--harness is required"
[ -d "$cwd" ] || usage "--cwd '$cwd' is not a directory"
[ "${#files[@]}" -ge 1 ] || usage "at least one --prompt-file is required"
[[ "$timeout" =~ ^[1-9][0-9]*$ ]] || usage "--timeout must be a positive integer (seconds)"
for f in "${files[@]}"; do [ -f "$f" ] || usage "--prompt-file '$f' not found"; done
[ -x "$BRIDGE" ] || usage "bridge not executable: $BRIDGE"

work="$(mktemp -d "${TMPDIR:-/tmp}/superagent-fanout.XXXXXX")"
trap 'rm -rf "$work"' EXIT

pids=(); n=0
for f in "${files[@]}"; do
  n=$((n + 1))
  "$BRIDGE" --harness "$harness" --model "$model" --effort "$effort" --tools "$tools" \
            --cwd "$cwd" --prompt-file "$f" --role "${role}-${n}" \
            >"$work/$n.out" 2>"$work/$n.err" &
  pids+=($!)
done

# Watchdog: after --timeout seconds kill every child still running, grandchildren first so a
# hung CLI does not outlive its bridge.
(
  sleep "$timeout"
  for p in "${pids[@]}"; do
    pkill -P "$p" 2>/dev/null || true
    kill "$p" 2>/dev/null || true
  done
) &
wd=$!

failed=0; i=0
for p in "${pids[@]}"; do
  i=$((i + 1))
  wait "$p"; rc=$?
  echo "$rc" >"$work/$i.rc"
  [ "$rc" -eq 0 ] || failed=$((failed + 1))
done
kill "$wd" 2>/dev/null || true
wait "$wd" 2>/dev/null || true

i=0
for _ in "${pids[@]}"; do
  i=$((i + 1))
  rc="$(cat "$work/$i.rc")"
  echo "=== PANELIST $i exit=$rc ==="
  if [ "$rc" -eq 0 ]; then
    cat "$work/$i.out"
  else
    logpath="$(sed -n 's/^role-bridge: log=//p' "$work/$i.err" | head -1)"
    echo "BRIDGE-FAILED exit=$rc harness=$harness role=${role}-${i} log=${logpath:-none}"
    tail -n 40 "$work/$i.err" 2>/dev/null || true
  fi
  echo "=== END $i ==="
done

[ "$failed" -eq 0 ] && exit 0 || exit 3
```

Then `chmod +x scripts/bridge-fanout.sh`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `bash scripts/bridge-test.sh | tail -1`
Expected: `bridge-test: 0 failure(s)` (the timeout test takes ~2 s).

- [ ] **Step 5: Commit**

```bash
git add scripts/bridge-fanout.sh scripts/bridge-test.sh
git commit -m "feat(bridge): bridge-fanout.sh — concurrent bridge runs with hard timeout and framed output (L7 panel primitive)"
```

---

### Task 4: `superagent-tick.sh` Pi branch; `launch.sh` / `install-timer.sh` / `bootstrap.sh` accept `pi`

**Files:**
- Modify: `scripts/superagent-tick.sh:76` (comment), `:145-173` (harness branches), `:189-198` (inherit re-map), `:200-218` (bridge export / effort), `:298-305` (auth notes), `:319-350` (invocation)
- Modify: `scripts/launch.sh:27,50,54-56`; `scripts/install-timer.sh:26,48,83-87`; `scripts/bootstrap.sh:50-88`
- Test: a PATH-shim run of the tick (below); `bash -n` on each script

**Interfaces:**
- Consumes: `superagent_harness`/`ensure_pi_bin` (Task 1); bridge env contract (Task 2).
- Produces: on `SUPER_HARNESS=pi` the tick runs `pi -p --approve --skill <repo>/pi/skills [--model M] [--thinking E] [--mode json]` with the prompt on stdin; exports `SUPERAGENT_PI_SKILLS=<repo>/pi/skills` and `SUPERAGENT_FANOUT=<repo>/scripts/bridge-fanout.sh`; exit 7 when `pi/` is missing, exit 8 on a malformed Pi supervisor model. Consumed by Tasks 6, 7, 8.

- [ ] **Step 1: Write the shim test script (throwaway, in the scratchpad — not committed)**

```bash
#!/usr/bin/env bash
# tick-pi-shim.sh — run superagent-tick.sh with SUPER_HARNESS=pi against PATH shims.
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"   # adjust: absolute path of the plugin repo
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/bin" "$T/repo" "$T/pi/skills/superagent"
cat >"$T/bin/pi" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$@" >"$T/pi.argv"; cat >"$T/pi.stdin"; echo "tick done"
EOF
cat >"$T/bin/gh" <<'EOF'
#!/usr/bin/env bash
case "$*" in *"auth status"*) exit 0 ;; *"auth token"*) echo ghs_shim ;; *) exit 0 ;; esac
EOF
chmod +x "$T/bin/pi" "$T/bin/gh"
( cd "$T/repo" && git init -q && git commit -q --allow-empty -m init )
printf -- '---\nstatus: WAITING FOR PLAN\n---\n' >"$T/repo/loop.md"
echo "stub" >"$T/pi/skills/superagent/SKILL.md"
# Run the REAL tick script but with PLUGIN_ROOT's pi/ tree pointed at the stub via a symlinked copy.
cp -R "$ROOT" "$T/plugin"; rm -rf "$T/plugin/pi"; cp -R "$T/pi" "$T/plugin/pi"
PATH="$T/bin:$PATH" SUPER_HARNESS=pi SUPER_MODEL_SUPERVISOR=pi:openai/gpt-5 SUPER_EFFORT_SUPERVISOR=high \
  REPO="$T/repo" LOOP_FILE="$T/repo/loop.md" LOG_FILE="$T/tick.log" TICK_OUTPUT_FORMAT=text \
  bash "$T/plugin/scripts/superagent-tick.sh"; echo "tick rc=$?"
echo "argv: $(tr '\n' ' ' <"$T/pi.argv")"
echo "stdin head: $(head -c 60 "$T/pi.stdin")"
grep -c 'superagent-tick harness=pi' "$T/tick.log"
```

(If `ensure_gh_auth` in `_common.sh` calls `gh` with other subcommands, extend the shim's `case` so each succeeds — the shim only needs the preflight to pass.)

Expected after Step 3: `tick rc=0`; `argv: -p --approve --skill <T>/plugin/pi/skills --model openai/gpt-5 --thinking high`; stdin begins `Read <T>/plugin/pi/skills/superagent/SKILL.md and execute exactly ONE --tick`; the grep prints `1`.

- [ ] **Step 2: Run it to verify it fails**

Run: `bash <scratchpad>/tick-pi-shim.sh`
Expected: `superagent: bad SUPER_HARNESS 'pi' (want claude|cursor|codex|pi)` is gone (Task 1), but the tick exits 7 or runs the claude branch — `argv` is empty or not `-p --approve …`.

- [ ] **Step 3: Implement the Pi branch in `superagent-tick.sh`**

Line 76 comment → `# Which agent CLI drives the tick: SUPER_HARNESS=claude (default) | cursor | codex | pi.`

After the `elif [[ "$HARNESS" == codex ]]; then … fi` harness block's codex arm (before `else`), add:

```bash
elif [[ "$HARNESS" == pi ]]; then
  # Pi build of the plugin: a Pi package tree under <plugin-repo>/pi (generated by
  # scripts/build-pi-skills.sh). Skills are delivered per run with --skill (additive; no install
  # step); superpowers comes from the operator's global Pi package install.
  SKILLS_ROOT="$PLUGIN_ROOT/pi"
  if [[ ! -f "$SKILLS_ROOT/skills/superagent/SKILL.md" ]]; then
    echo "superagent-tick: Pi build missing at $SKILLS_ROOT (run scripts/build-pi-skills.sh)" >&2
    exit 7
  fi
  # Model: TICK_MODEL > SUPER_MODEL_SUPERVISOR; values are Pi model strings (<provider>/<id>).
  # "inherit" -> empty -> omit --model (the CLI's settings.json default applies).
  TICK_MODEL="${TICK_MODEL:-${SUPER_MODEL_SUPERVISOR:-inherit}}"
  [[ "$TICK_MODEL" == "inherit" ]] && TICK_MODEL=""
```

In the inherit re-map comment/branch (`if [[ "$TICK_MODEL" == "inherit" ]]; then …`), the existing `else TICK_MODEL=""` already covers pi. Directly after that block add the shape check:

```bash
# A Pi supervisor model must be <provider>/<id> (an optional ":<level>" suffix is allowed) —
# anything else would reach the CLI as a bogus model name and fail every tick.
if [[ "$HARNESS" == pi && -n "$TICK_MODEL" ]]; then
  if ! [[ "${TICK_MODEL%%:*}" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
    echo "superagent-tick: SUPER_MODEL_SUPERVISOR='$TICK_MODEL' is not a Pi model string (<provider>/<id>)" >&2
    exit 8
  fi
fi
```

After `export SUPERAGENT_BRIDGE=…` add:

```bash
export SUPERAGENT_FANOUT="$PLUGIN_ROOT/scripts/bridge-fanout.sh"
# Pi harness: every bridged child pi process must see the plugin's skills the same way this tick
# does (role-bridge.sh passes it as --skill). Unset on other harnesses.
if [[ "$HARNESS" == pi ]]; then export SUPERAGENT_PI_SKILLS="$SKILLS_ROOT/skills"; fi
```

Effort comment line 212 → `# Harness-native names (claude: low..max; codex: none..xhigh; pi: off..max); inherit -> pass nothing.`

Auth notes: add before the `claude` arm:

```bash
elif [[ "$HARNESS" == pi && ! -f "$HOME/.pi/agent/auth.json" ]]; then
  echo "    note: ~/.pi/agent/auth.json not found; relying on provider API keys in the environment ($REPO/.env)" >>"$LOG_FILE"
```

Invocation: add before the `elif [[ "$HARNESS" == cursor ]]` arm:

```bash
elif [[ "$HARNESS" == pi ]]; then
  # Pi CLI: --approve (headless project trust for one run — the operator armed this loop on this
  # repo; Cursor --trust parity), --skill (the plugin's skills, additive, no install), prompt on
  # stdin. No --tools restriction: Pi's built-in set is already the tick's set, there are no
  # interactive tools to exclude, and extension tools (pi-subagents' `subagent`) must stay
  # available to superrun's children. Sessions are kept (debuggable, like Codex rollouts).
  pi_args=(-p --approve --skill "$SKILLS_ROOT/skills")
  [[ -n "$TICK_MODEL" ]]  && pi_args+=(--model "$TICK_MODEL")
  [[ -n "$TICK_EFFORT" ]] && pi_args+=(--thinking "$TICK_EFFORT")
  [[ "$TICK_OUTPUT_FORMAT" == stream ]] && pi_args+=(--mode json)
  ( cd "$REPO" && "${TIMEOUT_CMD[@]+"${TIMEOUT_CMD[@]}"}" pi "${pi_args[@]}" <<<"$PROMPT" ) \
    >>"$LOG_FILE" 2>&1 || rc=$?
```

- [ ] **Step 4: Update the other driver scripts**

`launch.sh:27` and `install-timer.sh:26` usage strings: `--harness claude|cursor|codex|pi`. `launch.sh:50` and `install-timer.sh:48`: `case "$HARNESS" in claude|cursor|codex|pi) ;; *) echo "bad --harness '$HARNESS' (want claude|cursor|codex|pi)" >&2; exit 2 ;; esac`. `launch.sh:54-56`: add `elif [[ "$HARNESS" == pi ]]; then MODEL_SHOWN="settings default"`. `install-timer.sh:83-85` comments: `(claude: opus; cursor: the CLI's auto; codex/pi: the CLI's configured default)` and `(claude | cursor | codex | pi)`.

`bootstrap.sh`: in the `SKILLS_ROOT` block add

```bash
elif [[ "$HARNESS" == pi ]]; then
  SKILLS_ROOT="$PLUGIN_ROOT/pi"
  if [[ ! -f "$SKILLS_ROOT/skills/superagent/SKILL.md" ]]; then
    echo "bootstrap: Pi build missing at $SKILLS_ROOT (run scripts/build-pi-skills.sh)" >&2
    exit 7
  fi
```

and in the invocation block, before the final `else`:

```bash
elif [[ "$HARNESS" == pi ]]; then
  export SUPERAGENT_BRIDGE="$PLUGIN_ROOT/scripts/role-bridge.sh" SUPERAGENT_FANOUT="$PLUGIN_ROOT/scripts/bridge-fanout.sh" SUPERAGENT_PI_SKILLS="$SKILLS_ROOT/skills"
  ( cd "$REPO" && "${TIMEOUT_CMD[@]+"${TIMEOUT_CMD[@]}"}" pi -p --approve --skill "$SKILLS_ROOT/skills" <<<"$PROMPT" )
```

(`bootstrap.sh` has no codex arm today either; the pi arm is the minimum for `launch.sh --harness pi` to work.)

- [ ] **Step 5: Verify**

Run: `for s in superagent-tick launch install-timer bootstrap; do bash -n scripts/$s.sh && echo "$s ok"; done; bash <scratchpad>/tick-pi-shim.sh; bash scripts/bridge-test.sh | tail -1`
Expected: four `ok` lines; the shim run prints `tick rc=0`, the argv line shown in Step 1, the stdin head, and `1`; `bridge-test: 0 failure(s)`.

Also: `SUPER_MODEL_SUPERVISOR=pi:not-a-model bash …superagent-tick.sh` (same env otherwise) → stderr `is not a Pi model string`, `tick rc=8`. And `SUPER_MODEL_SUPERVISOR=codex:gpt-5` → `tick rc=11`.

- [ ] **Step 6: Commit**

```bash
git add scripts/superagent-tick.sh scripts/launch.sh scripts/install-timer.sh scripts/bootstrap.sh
git commit -m "feat(pi): superagent-tick pi branch (--skill delivery, --approve, --thinking, --mode json); pi in launch/install-timer/bootstrap"
```

---

### Task 5: Templates — `superenv.default`, two Pi agent-definition templates

**Files:**
- Modify: `templates/superenv.default:32-38` (effort comment), `:53-54` (harness block)
- Create: `templates/super-role-pi-agent.md`, `templates/super-role-pi-bridge-agent.md`

**Interfaces:**
- Produces: new key `SUPER_PI_SUBAGENTS` (`recommended|required|off`, default `recommended`); Pi templates with placeholders `<role>`, `<KEY>`, `<model>`, `<effort>`, `<harness>`, `<relay-model>`, `<bridge-path>`. Consumed by Task 6 (`init`), Task 7 (build copies them), Task 8 (T4 renders the bridge one).

- [ ] **Step 1: Edit `templates/superenv.default`**

Effort comment: replace the `#   pi:     off | minimal | low | medium | high (applied as the :<level> model suffix)` line with `#   pi:     off | minimal | low | medium | high | xhigh | max (the :<level> model suffix, or --thinking when the model is inherit)`, and in the sentence `SUPER_EFFORT_SUPERVISOR is passed at tick invocation (claude: --effort, codex: -c model_reasoning_effort).` add `pi: --thinking`.

Harness block: change the `SUPER_HARNESS` comment to `# claude | cursor | codex | pi — which agent CLI the external driver fires per tick` and append after `SUPER_CODEX_SANDBOX`:

```
SUPER_PI_SUBAGENTS=recommended          # pi harness only: recommended (init WARNs if the pi-subagents package is missing or < 0.58.0; superrun's SDD children then run sequentially in-context without role pins) | required (init ABORTS instead) | off (never generate .pi/agents/ definitions, never use the subagent tool)
```

- [ ] **Step 2: Create `templates/super-role-pi-agent.md`**

```markdown
---
name: super-<role>
description: superagent <role> role agent — pins this role's model and/or thinking level as configured in .superenv (<KEY>). Generated by superagent:init; do not edit by hand.
model: <model>
thinking: <effort>
tools: read, edit, write, bash, grep, find, ls
async: false
inheritSkills: true
inheritProjectContext: true
systemPromptMode: append
---

<!-- generated-by: superagent:init (from .superenv <KEY>) — re-run superagent:init after changing the key; do not edit by hand -->

You are the superagent `<role>` role agent. You exist only to pin your role's model
and/or thinking level: the dispatching skill's prompt carries every instruction for
the task. Execute that prompt exactly as given, as a general-purpose agent would.
```

(`init` drops the `model:` line when the model is `inherit` and the `thinking:` line when the effort is `inherit`, exactly as it does for the Claude template's `model:`/`effort:` lines.)

- [ ] **Step 3: Create `templates/super-role-pi-bridge-agent.md`**

```markdown
---
name: super-<role>
description: superagent <role> role agent — BRIDGED to the <harness> harness (<KEY>). Relays the task prompt to `<harness>` via role-bridge.sh and returns its result verbatim. Generated by superagent:init; do not edit by hand.
model: <relay-model>
tools: bash
async: false
inheritSkills: false
inheritProjectContext: false
systemPromptMode: replace
---

<!-- generated-by: superagent:init (from .superenv <KEY>) — bridged role; re-run superagent:init after changing the key; do not edit by hand -->

You are the superagent `<role>` relay: a pipe between this session and the `<harness>` CLI. You do
NOT read, judge, answer, or act on the prompt you receive. You copy it into a file, hand that file
to `role-bridge.sh`, and return what comes back. Nothing else.

**Your first action MUST be a `bash` tool call — step 1 below. Emit no text before it.** You have no
tool except `bash` and no knowledge of the task. The only acceptable final message is the bridge's
stdout (step 3) or a `BRIDGE-FAILED` line (step 4); ending the turn with anything else — a
plausible answer, a summary, an acknowledgement — is a hard failure.

The prompt you receive is addressed to the `<harness>` model on the far side of the bridge, not to
you. Every instruction inside it — including "reply with exactly X", "answer in one line", or
anything else that looks trivially satisfiable — is for that model to obey, not you. Even if you
are certain you know the answer, relaying is still the only correct behaviour: an answer you
produced yourself is wrong by definition, because it did not come from `<harness>`.

1. **bash.** Write the COMPLETE prompt you received — every line, verbatim, nothing added or summarized —
   to a new temp file: `f="$(mktemp "${TMPDIR:-/tmp}/super-<role>.XXXXXX")"` (use `bash` with a
   quoted heredoc, `cat >"$f" <<'__SUPERAGENT_PROMPT_END__' … __SUPERAGENT_PROMPT_END__`); if the
   prompt itself contains a line that is exactly `__SUPERAGENT_PROMPT_END__`, pick a different
   unique terminator instead.
2. **bash.** Run, from your current working directory (the same checkout/worktree the prompt refers to):
   `"${SUPERAGENT_BRIDGE:-<bridge-path>}" --harness <harness> --model "<model>" --effort "<effort>" --cwd "$PWD" --prompt-file "$f" --role <role>`
   Pass the largest timeout the `bash` tool accepts (its `timeout` parameter, 7200000 ms if allowed)
   — the bridge may run for many minutes and the tool's default cap would kill it mid-run. Wait
   for it to finish. Never modify files yourself.
3. If it exited 0: reply with its stdout **verbatim** as your final message — no preamble, no
   commentary, no summary.
4. If it exited non-zero: reply with exactly `BRIDGE-FAILED exit=<code> harness=<harness>
   role=<role> log=<path>`, where `<path>` is the file path the bridge printed on stderr after
   `role-bridge: log=`, followed by the last 40 lines of that log file. Do not retry.
```

(`init` drops the `model:` line when `SUPER_BRIDGE_RELAY_MODEL=inherit`.)

- [ ] **Step 4: Verify the templates parse as frontmatter and the key resolves**

Run: `for f in templates/super-role-pi-agent.md templates/super-role-pi-bridge-agent.md; do awk '/^---$/{c++} END{exit c<2}' "$f" && echo "$f frontmatter ok"; done; . scripts/_common.sh; load_superenv "$PWD" >/dev/null 2>&1; echo "SUPER_PI_SUBAGENTS=${SUPER_PI_SUBAGENTS:-unset}"; bash scripts/build-codex-skills.sh --check >/dev/null 2>&1; echo "codex check rc=$? (1 expected — template changed; rebuilt in Task 7)"`
Expected: two `frontmatter ok` lines; `SUPER_PI_SUBAGENTS=recommended`.

- [ ] **Step 5: Commit**

```bash
git add templates/superenv.default templates/super-role-pi-agent.md templates/super-role-pi-bridge-agent.md
git commit -m "feat(pi): SUPER_PI_SUBAGENTS key, pi effort domain in superenv.default; pi-subagents agent/relay templates"
```

---

### Task 6: Skill text — `pi-only` blocks in `init`, `superagent`, `superloop`, `superrun`

**Files:**
- Modify: `skills/init/SKILL.md` (Step 1 items 2/5, validation items 2/5/6, Step 3), `skills/superagent/SKILL.md` (Step 0.5, Subagent dispatch, Model resolution, "Running from …"), `skills/superloop/SKILL.md` (L7 Rung 1), `skills/superrun/SKILL.md` (Step 3 note, Model policy item 3, Effort policy)

**Interfaces:**
- Consumes: bridge CLI (Task 2), `bridge-fanout.sh` (Task 3), env `SUPERAGENT_BRIDGE`/`SUPERAGENT_FANOUT`/`SUPERAGENT_PI_SKILLS` (Task 4), templates + `SUPER_PI_SUBAGENTS` (Task 5).
- Produces: the marker vocabulary `<!-- pi-only:start` … `pi-only:end -->` (inert comment form, identical to `codex-only`), consumed by Task 7's build scripts.

The `pi-only` marker form is exactly:

```
<!-- pi-only:start
…content…
pi-only:end -->
```

- [ ] **Step 1: `skills/init/SKILL.md`**

Step 1 item 2 (superpowers resolvable): append a `pi-only` block after the existing sentence:

```
<!-- pi-only:start
   On Pi, superpowers is a Pi package: `pi list` must show `superpowers` (install:
   `pi install git:github.com/obra/superpowers`). Then check the `pi-subagents` package per
   `SUPER_PI_SUBAGENTS` (validated below): read its installed version from
   `~/.pi/agent/npm/node_modules/pi-subagents/package.json` or `.pi/npm/node_modules/pi-subagents/package.json`
   (whichever exists); missing or `< 0.58.0` → `recommended`: WARN "pi-subagents missing/old —
   superrun's SDD children will run sequentially in-context without role pins; install:
   `pi install npm:pi-subagents`"; `required`: ABORT with the same hint; `off`: skip the check.
   Record the version (or `absent`) in the summary — Step 3 keys off it.
pi-only:end -->
```

Step 1 item 5 (bridge targets): the sentence `pi → for a <provider>/ of openai or anthropic, OPENAI_API_KEY / ANTHROPIC_API_KEY set` stays; append `; on the Pi harness also run \`pi auth check --provider <p>\` for each distinct provider a \`pi:\` role names (WARN on failure)` inside a `pi-only` block.

Validation item 2 enums: change `SUPER_HARNESS ∈ claude|cursor|codex` to `claude|cursor|codex|pi`; add `SUPER_PI_SUBAGENTS ∈ recommended|required|off`; add a `pi-only` block after the `SUPER_PANEL_AGENT_TYPE` enum: `On Pi \`SUPER_PANEL_AGENT_TYPE\` is ignored (the panel is a bridge fan-out, not typed subagents) — WARN once if it is set to anything.`

Validation item 5 native-model validation: add a `pi-only` block alongside the `cc-only`/`cursor-only`/`codex-only` ones:

```
<!-- pi-only:start
   a Pi model string — exactly one `/` (`<provider>/<model>`, an optional `:<level>` suffix allowed)
   — or `inherit`; anything else → WARN, treat as `inherit`. A bare Claude tier / `claude-*` /
   `gpt-*` value infers its own harness under arm (c) and is therefore **bridged** (its CLI must be
   present per Step 1 item 5), never a Pi model.
pi-only:end -->
```

Validation item 6 effort domains: change `pi off|minimal|low|medium|high` to `pi off|minimal|low|medium|high|xhigh|max`.

Step 3 intro: add a `pi-only` block after the `codex-only` intro:

```
<!-- pi-only:start
Nine `SUPER_MODEL_*` role keys dispatch through subagents — all but `SUPER_MODEL_SUPERVISOR`,
which the external tick passes straight to `pi --model`. On Pi the supervisor's OWN dispatches
(planner, executor, panel) are bridge processes that take the pins as CLI flags and need no
definition; only superrun's SDD roles (implementer, fix-applier, task-reviewer, re-reviewer,
branch-reviewer, fix-planner) dispatch through the `pi-subagents` `subagent` tool, and THOSE ride
generated `.pi/agents/super-<role>.md` definitions. Generation happens only when Step 1 found
`pi-subagents` ≥ 0.58.0 and `SUPER_PI_SUBAGENTS` ≠ `off`; otherwise this step generates nothing
and reports `dispatch=sequential (no pi-subagents)` for the six SDD roles.
pi-only:end -->
```

Step 3 table: the "Generated definition" column is Claude-specific; add one line under the table inside a `pi-only` block: `On Pi the listed path is \`.pi/agents/super-<role>.md\` for the six SDD roles; planner/executor/panel never get a file.`

Step 3 bullets: add a `pi-only` block after the `codex-only` bullets:

```
<!-- pi-only:start
- **SDD role, native (`pi:` or inherit) — generate when** the model is non-`inherit` OR the effort is
  non-`inherit`: render `${SUPER_PLUGIN_ROOT}/templates/super-role-pi-agent.md` to
  `.pi/agents/super-<role>.md` (create `.pi/agents/` if needed), substituting `<role>`, `<KEY>`,
  `<model>` (prefix stripped; drop the `model:` line when `inherit`) and `<effort>` (drop the
  `thinking:` line when `inherit`). A role with both keys `inherit` needs no file.
- **SDD role, bridged (harness ≠ pi):** render
  `${SUPER_PLUGIN_ROOT}/templates/super-role-pi-bridge-agent.md` to the same path, substituting
  `<role>`, `<KEY>`, `<harness>`, `<model>` (prefix stripped), `<effort>` (`inherit` when
  unset/invalid), `<relay-model>` = `SUPER_BRIDGE_RELAY_MODEL` (drop the `model:` line when
  `inherit`) and `<bridge-path>` = the absolute path of `${SUPER_PLUGIN_ROOT}/scripts/role-bridge.sh`.
- **Planner / executor / panel:** never a file; record `dispatch=bridge(<harness>)` (native roles
  show `bridge(pi)`).
- Ownership rules are the Claude build's: files carry the `generated-by: superagent:init` marker;
  rewrite marked files whose pins drifted; never touch an unmarked file (report `conflict`);
  delete a marked file no key requires (`removed (stale)`). When `pi-subagents` is absent/`off`,
  existing marked files are left in place and reported `unused (no pi-subagents)`.
- A leftover `.claude/agents/super-*.md` from a Claude Code init of the same repo belongs to that
  harness's build: leave it untouched and do not report it as stale.
pi-only:end -->
```

Also add the "definitions load at session start" note as a `pi-only` block: `Agent definitions are read by pi-subagents at child launch, so files written here take effect from the next superrun dispatch.`

- [ ] **Step 2: `skills/superagent/SKILL.md`**

Step 0.5: add after the `codex-only` block:

```
<!-- pi-only:start
A structural no-op in this build (superloop L4): the external driver is the only driver and every tick
runs in a fresh context. Go straight to **Step 1**.
pi-only:end -->
```

Subagent dispatch section: the `superplan → an Agent-tool subagent` bullet is Claude/Cursor/Codex text. Wrap that bullet in `<!-- cc-only:start -->`…`<!-- cc-only:end -->` **only if** it is not already inside one (check the surrounding markers at `:162-172`; the cursor/codex builds currently keep it, so leave their behaviour unchanged by adding a `pi-only` block instead of re-marking). Add a `pi-only` block immediately after that bullet:

```
<!-- pi-only:start
- **On Pi, `superplan` is ALSO its own CLI process.** This harness has no in-process subagent tool
  in the supervisor; every heavy dispatch is a blocking `bash` call to the bridge. Dispatch
  `superplan` exactly like `superrun` below, with two differences: `--tools planner` and
  `--role planner`, and the model/effort from `SUPER_MODEL_PLANNER` / `SUPER_EFFORT_PLANNER`:
  `"${SUPERAGENT_BRIDGE:-${SUPER_PLUGIN_ROOT}/scripts/role-bridge.sh}" --harness <h> --model "<m>" --effort "<e>" --tools planner --cwd "<primary root>" --prompt-file "$f" --role planner`
  A native (`pi:`/inherit) planner runs with `--harness pi` — native and bridged are the same code
  path on this harness. The child inherits `SUPERAGENT_PI_SKILLS` from the tick, so `superplan`
  and the `superpowers:*` skills resolve inside it. Exit 0 → stdout is the Final Report; non-zero
  → the crashed-dispatch path (retry once, then the crash-recovery mapping: restore the ready
  status, `release_lock()`, end the tick, quoting the `log=` path in `Findings & issues`).
pi-only:end -->
```

In the `superrun` bullet's Preflight paragraph, add a `pi-only` block: `On Pi there is no \`BASH_MAX_TIMEOUT_MS\` env; pass the largest \`timeout\` the \`bash\` tool accepts on the call itself and skip the env check.`

Model resolution — after the `*superplan (Agent-tool dispatch):*` list add:

```
<!-- pi-only:start
*`superplan` on Pi (process dispatch):* identical to the `superrun` rule above with
`SUPER_MODEL_PLANNER` / `SUPER_EFFORT_PLANNER` and `--tools planner`. No agent definition is
involved for planner, executor, or panel on this harness.
pi-only:end -->
```

"Running from the … CLI" paragraphs: add after the `codex-only` one:

```
<!-- pi-only:start
**Running from the Pi CLI.** For `external` mode the tick fires in a fresh headless `pi -p` session
per interval; the scheduler drives it by asking the CLI to *read `pi/skills/superagent/SKILL.md`
directly (in the plugin repository's generated Pi build) and run exactly one `--tick`* (superloop
L2, Driver B). The plugin's skills are delivered per run with `--skill <plugin-repo>/pi/skills` —
no install step; superpowers must be installed as a Pi package (`pi install
git:github.com/obra/superpowers`). The shipped `scripts/` wrappers are harness-aware:
`SUPER_HARNESS=pi` makes `superagent-tick.sh` fire `pi -p --approve --skill … [--model] [--thinking]`
and export `SUPERAGENT_BRIDGE`, `SUPERAGENT_FANOUT`, and `SUPERAGENT_PI_SKILLS` for the bridge
children. The driver must never resume a prior session (fresh context per tick — L4 is a no-op in
`external` mode, so the loop runs straight to `DONE`); an interactive monitoring/answering console is
a separate plane that can be started/stopped independently.
pi-only:end -->
```

Rationalization table: add a `pi-only` row block after the `codex-only` one at `:64-67`:

```
<!-- pi-only:start
| "I'll dispatch `superplan` with the `subagent` tool — it's right there" | NO. On Pi the supervisor NEVER uses a subagent tool. `superplan`, `superrun`, and every panelist are bridge processes started from your `bash` tool (see **Subagent dispatch**); `pi-subagents` is for `superrun`'s SDD children only. |
pi-only:end -->
```

- [ ] **Step 3: `skills/superloop/SKILL.md` — L7 Rung 1**

After the `codex-only` block at `:717-724` add:

```
<!-- pi-only:start
Dispatch **3 panelists in one blocking `bash` call** to the fan-out script — this harness has no
blocking parallel subagent tool, and the supervisor never uses a subagent tool at all. Write the
identical packet to three temp files (`mktemp "${TMPDIR:-/tmp}/super-panel.XXXXXX"` ×3, quoted
heredocs), resolve the panel's harness/model/effort from `SUPER_MODEL_PANEL` / `SUPER_EFFORT_PANEL`
(`. "${SUPER_PLUGIN_ROOT}/scripts/_common.sh"`; `superagent_role_harness`, an `inherit` harness →
`pi`; `superagent_role_model`), then run with the largest `timeout` the `bash` tool accepts:
`"${SUPERAGENT_FANOUT:-${SUPER_PLUGIN_ROOT}/scripts/bridge-fanout.sh}" --harness <h> --model "<m>" --effort "<e>" --tools role --cwd "$PWD" --role panelist --timeout 1800 --prompt-file "$f1" --prompt-file "$f2" --prompt-file "$f3"`
stdout carries the three verdicts framed `=== PANELIST <n> exit=<rc> === … === END <n> ===`; a
block whose body begins `BRIDGE-FAILED` (bridge error or the 1800 s timeout) is that panelist
returning `insufficient-info`. `SUPER_PANEL_AGENT_TYPE` is ignored on Pi. The call blocks until
all three return — never launch panelists as background `pi-subagents` runs and poll them.
pi-only:end -->
```

- [ ] **Step 4: `skills/superrun/SKILL.md`**

Step 3 blockquote ("You must be the top-level agent of your process"): add a `pi-only` block after it:

```
<!-- pi-only:start
> **On Pi, SDD's subagents are the `pi-subagents` `subagent` tool** (superpowers' own Pi mapping,
> `references/pi-tools.md`). Dispatch every SDD child with `async: false` — one child per call,
> foreground, the tool result is the child's final output. If no `subagent` tool is available in
> this session, follow SDD's documented fallback (execute the task sequentially in this context)
> and record `sdd-dispatch: sequential (no pi-subagents)` under Findings in the closeout so the
> operator sees the degraded mode. Never launch background, parallel, chain, or workflow runs.
pi-only:end -->
```

Model policy item 3: add a `pi-only` block after the `codex-only` effort block at `:166-175`:

```
<!-- pi-only:start
   In this build a role's pins ride the `pi-subagents` agent definition `superagent:init`
   generated at `.pi/agents/super-<role>.md`: dispatch the role with `agent: super-<role>` and
   no model/thinking override on the call (native definition = model/thinking pins; bridged
   definition = a relay that runs the foreign CLI and returns its result verbatim — a reply
   beginning `BRIDGE-FAILED` is a crashed child: retry once, then the skill's normal escalation,
   quoting the `log=` path). A role with both keys `inherit` has no definition: dispatch a plain
   `subagent` call with no `agent`. A missing definition for a pinned role is a hard error (re-run
   `superagent:init`) — unless the `subagent` tool itself is unavailable, in which case the
   sequential fallback above applies and the pins are reported as not applied.
pi-only:end -->
```

- [ ] **Step 5: Verify marker hygiene**

Run: `for f in skills/init/SKILL.md skills/superagent/SKILL.md skills/superloop/SKILL.md skills/superrun/SKILL.md; do s=$(grep -c '^<!-- pi-only:start$' "$f"); e=$(grep -c '^pi-only:end -->$' "$f"); echo "$f start=$s end=$e"; [ "$s" = "$e" ] || echo "MISMATCH"; done`
Expected: equal counts per file (init 8, superagent 6, superloop 1, superrun 2), no `MISMATCH`. Also `bash scripts/build-codex-skills.sh --check; echo rc=$?` → rc=1 with the `pi-only` lines visible in the diff (they leak until Task 7 teaches the builds to drop them — expected here).

- [ ] **Step 6: Commit**

```bash
git add skills/init/SKILL.md skills/superagent/SKILL.md skills/superloop/SKILL.md skills/superrun/SKILL.md
git commit -m "feat(pi): pi-only skill blocks — bridge dispatch for planner/executor/panel, pi-subagents for SDD roles, init definitions in .pi/agents"
```

---

### Task 7: `build-pi-skills.sh` → `pi/`; other builds drop `pi-only`

**Files:**
- Create: `scripts/build-pi-skills.sh`, generated `pi/` tree
- Modify: `scripts/build-codex-skills.sh:56-63` and `scripts/build-cursor-skills.sh:50-62` (`filter_markers`), plus the header comments listing markers
- Test: `--check` on all three build scripts; grep for leakage

**Interfaces:**
- Consumes: `pi-only` markers (Task 6), templates (Task 5), `role-bridge.sh`/`bridge-fanout.sh`/`_common.sh` (Tasks 1–3).
- Produces: `pi/package.json`, `pi/skills/<name>/SKILL.md`, `pi/skills/pi-smoke-probe/SKILL.md`, `pi/templates/{superenv.default,super-role-pi-agent.md,super-role-pi-bridge-agent.md,vault-root.md}`, `pi/scripts/{role-bridge.sh,bridge-fanout.sh,_common.sh}`, `pi/README.md`. `${SUPER_PLUGIN_ROOT}` in the Pi build = `<repo>/pi`. Consumed by Tasks 4 (tick reads `pi/skills`), 8, 9.

- [ ] **Step 1: Teach the Codex and Cursor builds to drop `pi-only`**

In both `filter_markers` awk programs add, next to the arm that drops the other harness's block:

```awk
    /^[[:space:]]*<!-- pi-only:start[[:space:]]*$/ { pdrop=1; next }
    /^[[:space:]]*pi-only:end -->[[:space:]]*$/    { pdrop=0; next }
    pdrop                     { next }
```

Add a header-comment line in each: `#   <!-- pi-only:start … pi-only:end -->   block DROPPED here (wrapper AND content)`.

Run: `bash scripts/build-codex-skills.sh && bash scripts/build-cursor-skills.sh && grep -rl 'pi-only' codex cursor; echo "leak grep rc=$? (1 = clean)"`
Expected: `leak grep rc=1`.

- [ ] **Step 2: Write `scripts/build-pi-skills.sh`**

Model it on `build-codex-skills.sh` (same `--check` contract, same header-marker guard on `superenv.default`, same `insert_banner`):

```bash
#!/usr/bin/env bash
# build-pi-skills.sh — generate the Pi build of the superagent plugin into pi/.
#
# Canonical skills under skills/ are the single source of truth. Markers:
#   <!-- cc-only:start --> … <!-- cc-only:end -->   DROPPED (marker lines too)
#   <line> <!-- cc-only -->                         line DROPPED
#   <!-- cursor-only:start … cursor-only:end -->    DROPPED (wrapper AND content)
#   <!-- codex-only:start … codex-only:end -->      DROPPED (wrapper AND content)
#   <!-- pi-only:start … pi-only:end -->            wrapper dropped, content ACTIVATED
# Output layout (committed; re-run after editing skills/), a valid Pi package:
#   pi/package.json                          { "pi": { "skills": ["skills"] } }
#   pi/skills/<name>/SKILL.md                filtered + substituted skills
#   pi/skills/pi-smoke-probe/SKILL.md        smoke-test probe skill (generated only)
#   pi/templates/                            superenv.default (Pi-specialized), pi agent templates, vault-root.md
#   pi/scripts/                              role-bridge.sh, bridge-fanout.sh, _common.sh (so ${SUPER_PLUGIN_ROOT}/scripts/* resolves)
#   pi/README.md
# Usage: scripts/build-pi-skills.sh [--check]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/pi"
CHECK=false
[ "${1:-}" = "--check" ] && CHECK=true

grep -q '^# (SUPER_MODEL_SUPERVISOR' "$ROOT/templates/superenv.default" \
  || { echo "build: superenv.default header end-marker missing" >&2; exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
TMP="$WORK/out"
mkdir -p "$TMP"

filter_markers() {
  awk '
    /<!-- cc-only:start -->/  { drop=1; next }
    /<!-- cc-only:end -->/    { drop=0; next }
    drop                      { next }
    /<!-- cc-only -->/        { next }
    /^[[:space:]]*<!-- cursor-only:start[[:space:]]*$/ { udrop=1; next }
    /^[[:space:]]*cursor-only:end -->[[:space:]]*$/    { udrop=0; next }
    udrop                     { next }
    /^[[:space:]]*<!-- codex-only:start[[:space:]]*$/ { cdrop=1; next }
    /^[[:space:]]*codex-only:end -->[[:space:]]*$/    { cdrop=0; next }
    cdrop                     { next }
    /^[[:space:]]*<!-- pi-only:start[[:space:]]*$/ { next }
    /^[[:space:]]*pi-only:end -->[[:space:]]*$/    { next }
    { print }
  '
}

substitute() {
  sed \
    -e 's/\${CLAUDE_PLUGIN_ROOT}/\${SUPER_PLUGIN_ROOT}/g' \
    -e 's/claude -p/pi -p/g' \
    -e 's/claude --model/pi --model/g' \
    -e 's/Claude CLI/Pi CLI/g' \
    -e 's/^driver: cron  .*/driver: external                  # the only driver in this build (external scheduler — fresh context per tick)/' \
    -e 's/^cron_id:  .*# CronCreate job id.*/cron_id:                          # unused in this build (Claude Code in-session driver only); leave empty/'
}

banner_file="$WORK/banner"
cat >"$banner_file" <<'EOF'

<!-- GENERATED FILE — Pi build. Do not edit by hand: edit the canonical skill under skills/
     in the plugin repository and re-run scripts/build-pi-skills.sh. -->

> **Pi build notes.**
> - Only the **external** driver exists in this build. Claude Code's in-session cron driver and its
>   `CronCreate` / `CronList` / `CronDelete` / `Monitor` / `AskUserQuestion` tools do **not** exist
>   on Pi — treat any residual mention as inapplicable and NEVER attempt those tool calls.
> - Tool mapping in the SUPERVISOR (`superagent`, `superloop`): "Agent tool" / "dispatch a
>   subagent" = a blocking `bash` call to `${SUPER_PLUGIN_ROOT}/scripts/role-bridge.sh`
>   (`superplan`, `superrun`) or `${SUPER_PLUGIN_ROOT}/scripts/bridge-fanout.sh` (the L7 panel),
>   per the `pi-only` text in those skills. The supervisor never uses a subagent tool.
> - Tool mapping in `superrun` (the SDD controller): "dispatch a subagent" = the `subagent` tool
>   from the `pi-subagents` package with `async: false`, one child per call; role pins ride the
>   `.pi/agents/super-<role>.md` definitions `init` generates. If the tool is absent, follow SDD's
>   sequential fallback and report it.
> - "Skill tool / invoke skill X" = `read` `${SUPER_PLUGIN_ROOT}/skills/X/SKILL.md` and follow it
>   (`/skill:` commands are interactive-only). Superpowers skills are listed by Pi from the
>   installed `superpowers` package — reference them by name.
> - `${SUPER_PLUGIN_ROOT}` = the plugin repository's `pi/` directory (two levels above each
>   SKILL.md). It contains `skills/`, `templates/`, and `scripts/` (`role-bridge.sh`,
>   `bridge-fanout.sh`, `_common.sh`). The external-driver wrappers (`superagent-tick.sh`,
>   `launch.sh`, …) live in the repository's top-level `scripts/` — one directory up.
> - `EnterWorktree` = not available; use `git worktree` via `bash`.
EOF

insert_banner() {
  local src="$1" fmline
  fmline="$(awk '/^---$/{c++; if(c==2){print NR; exit}}' "$src")"
  if [ -z "$fmline" ]; then cat "$src"; return; fi
  head -n "$fmline" "$src"; cat "$banner_file"; tail -n +"$((fmline + 1))" "$src"
}

for dir in "$ROOT"/skills/*/; do
  name="$(basename "$dir")"
  mkdir -p "$TMP/skills/$name"
  filter_markers <"$dir/SKILL.md" | substitute >"$WORK/pre"
  insert_banner "$WORK/pre" >"$TMP/skills/$name/SKILL.md"
done

mkdir -p "$TMP/skills/pi-smoke-probe"
cat >"$TMP/skills/pi-smoke-probe/SKILL.md" <<'EOF'
---
name: pi-smoke-probe
description: Use when asked to run the pi smoke probe (or "superagent pi probe") — verifies the Pi build of the superagent plugin is loaded and reports environment facts for the port smoke test.
---

# Pi smoke probe

Perform these checks with your file/shell tools, then output ONLY the report block below —
no extra prose before or after it.

1. Determine this skill file's own location and derive `plugin_root` = the directory two levels
   above it (the directory containing `skills/`, `templates/`, `scripts/`). If you cannot
   determine the file's location, report `unknown`.
2. Check whether `<plugin_root>/templates/superenv.default` is readable; capture its first line.
3. Check `<plugin_root>/skills/superloop/SKILL.md`: does it exist; does it contain the string
   "GENERATED FILE — Pi build" (a correct Pi build MUST); does it contain "cc-only", "cursor-only",
   or "codex-only" (a correct Pi build must NOT — marker leakage).
4. Do you have a tool named `subagent`? Report `yes` or `no`.
5. Check whether `<plugin_root>/scripts/role-bridge.sh` and `<plugin_root>/scripts/bridge-fanout.sh`
   exist and are executable.

Report block (fill every value):

    PROBE-BEGIN
    plugin_root: <absolute path, or unknown>
    superenv_default_readable: <yes|no>
    superenv_first_line: <the line, or n/a>
    superloop_skill_present: <yes|no>
    superloop_has_pi_banner: <yes|no>
    superloop_marker_leakage: <yes|no>
    subagent_tool: <yes|no>
    role_bridge_present: <yes|no>
    bridge_fanout_present: <yes|no>
    PROBE-END
EOF

mkdir -p "$TMP/templates" "$TMP/scripts"
cp "$ROOT/templates/super-role-pi-agent.md" "$ROOT/templates/super-role-pi-bridge-agent.md" "$ROOT/templates/vault-root.md" "$TMP/templates/"
cp "$ROOT/scripts/role-bridge.sh" "$ROOT/scripts/bridge-fanout.sh" "$ROOT/scripts/_common.sh" "$TMP/scripts/"
chmod +x "$TMP/scripts/role-bridge.sh" "$TMP/scripts/bridge-fanout.sh"

substitute <"$ROOT/templates/superenv.default" | awk '
  /^# Model values:/ { inhdr=1
    print "# Model values: \"inherit\", or [<harness>:]<model> where <harness> is claude | codex | cursor | pi"
    print "# and <model> is that harness'"'"'s native model string — pi: <provider>/<model> (openai/gpt-5,"
    print "# anthropic/claude-opus-5; optional :<level> suffix); claude: a tier (sonnet|opus|haiku|fable) or full"
    print "# ID; codex: a Codex model (gpt-5.6-sol); cursor: `agent --list-models`. The prefix is optional when"
    print "# the model is recognizable (a \"/\" → pi, tiers/claude-* → claude, gpt-*/o<n>/codex* → codex)."
    print "# On Pi the supervisor'"'"'s own dispatches (planner, executor, panel) are bridge PROCESSES for"
    print "# every harness including pi itself — pins ride CLI flags, no agent definition. superrun'"'"'s SDD"
    print "# roles dispatch through the pi-subagents `subagent` tool; their pins ride .pi/agents/super-<role>.md"
    print "# definitions generated by superagent:init (re-run it after changing one)."
    print "# (SUPER_MODEL_SUPERVISOR must be native to SUPER_HARNESS; the tick refuses a foreign one.)"
    next }
  inhdr && /^# \(SUPER_MODEL_SUPERVISOR/ { inhdr=0; next }
  inhdr && /^#/ { next }
  { inhdr=0 }
  /^# ── Reasoning effort per agent role/ { inefh=1
    print "# ── Reasoning effort per agent role ───────────────────────────────"
    print "# Values are effort names in the ROLE'"'"'s harness, or \"inherit\" (= the CLI/model default)."
    print "#   pi:     off | minimal | low | medium | high | xhigh | max"
    print "#   claude: low | medium | high | xhigh | max · codex: none | minimal | low | medium | high | xhigh"
    print "# SUPER_EFFORT_SUPERVISOR is passed at tick invocation (pi --thinking). Other roles: the"
    print "# bridge'"'"'s :<level> suffix (planner/executor/panel) or the definition'"'"'s thinking: line (SDD roles)."
    next }
  inefh && /^# NOTE \(claude\):/ { inefh=2; next }
  inefh==2 && /^#/ { inefh=0; next }
  inefh==1 && /^#/ { next }
  { inefh=0 }
  { print }
' | sed \
  -e 's/^SUPER_MODEL_\([A-Z_]*\)=claude:[a-z]*/SUPER_MODEL_\1=inherit/' \
  -e 's/^SUPER_HARNESS=claude\([[:space:]]*\)#.*/SUPER_HARNESS=pi\1# this is the Pi build — the external driver fires the Pi CLI (pi -p)/' \
  -e 's/^SUPER_BRIDGE_RELAY_MODEL=sonnet\([[:space:]]*\)#.*/SUPER_BRIDGE_RELAY_MODEL=inherit\1# relay agent model for a BRIDGED SDD role (.pi\/agents relay definition); inherit = the pi-subagents default; never a weak model — it answers instead of relaying/' \
  >"$TMP/templates/superenv.default"

version="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$ROOT/.claude-plugin/plugin.json" | head -1)"
cat >"$TMP/package.json" <<EOF
{
  "name": "superagent-pi",
  "version": "${version}",
  "description": "superagent plugin — Pi build (external unattended driver only)",
  "pi": { "skills": ["skills"] }
}
EOF

cat >"$TMP/README.md" <<'EOF'
# superagent — Pi build (GENERATED)

Everything here is generated by `scripts/build-pi-skills.sh` from the canonical skills at the
repository root. **Do not edit by hand.**

- **External driver only.** Loops run via an OS scheduler firing fresh headless `pi -p` sessions
  (`SUPER_HARNESS=pi` in `superagent-tick.sh`).
- **Skill delivery:** the tick passes `--skill <repo>/pi/skills` — no install step. For interactive
  use `pi install /path/to/superagent-plugin/pi` (this directory is a valid Pi package).
- **Prerequisites:** `pi` (`npm install -g @earendil-works/pi-coding-agent`), superpowers as a Pi
  package (`pi install git:github.com/obra/superpowers`), and — recommended — `pi-subagents`
  ≥ 0.58.0 (`pi install npm:pi-subagents`). Without it superrun's SDD children run sequentially
  in-context with no role pins (`SUPER_PI_SUBAGENTS=required` makes init abort instead).
- **Dispatch:** the supervisor runs `superplan`/`superrun` through `scripts/role-bridge.sh` and the
  L7 panel through `scripts/bridge-fanout.sh` — child CLI processes, every harness including Pi.
  superrun's SDD roles use `pi-subagents`' `subagent` tool (`async: false`); their pins ride
  `.pi/agents/super-<role>.md` definitions generated by `init`.
- **Trust:** every headless run passes `--approve` (the operator armed the loop on this repo).
- **Model keys** are `[<harness>:]<model>`; Pi-native values are `<provider>/<model>`; effort keys
  in Pi's domain `off | minimal | low | medium | high | xhigh | max`.

## Validated

(Filled in by `scripts/pi-smoke.sh` runs — see the repository README's Pi section.)

## Known gaps

- No end-to-end multi-tick loop driven to DONE on Pi yet.
- S3 with `pi-subagents` not exercised inside a real superrun.
EOF

grep -q 'GENERATED FILE — Pi build' "$TMP/skills/superloop/SKILL.md" || { echo "build-pi-skills: banner missing" >&2; exit 1; }
if grep -rqE 'cc-only|cursor-only|codex-only|pi-only' "$TMP/skills"; then echo "build-pi-skills: marker leakage" >&2; exit 1; fi

if $CHECK; then
  [ -d "$OUT" ] || { echo "build-pi-skills: --check: $OUT does not exist (run the build first)" >&2; exit 1; }
  if diff -r "$TMP" "$OUT" >/dev/null 2>&1; then echo "build-pi-skills: pi/ is up to date"
  else echo "build-pi-skills: pi/ is STALE — re-run scripts/build-pi-skills.sh:" >&2; diff -r "$TMP" "$OUT" >&2 || true; exit 1; fi
else
  rm -rf "$OUT"; mkdir -p "$OUT"; cp -R "$TMP"/. "$OUT"/
  echo "build-pi-skills: wrote $OUT"
fi
```

`chmod +x scripts/build-pi-skills.sh`.

- [ ] **Step 3: Build and verify**

Run: `bash scripts/build-pi-skills.sh && bash scripts/build-pi-skills.sh --check && bash scripts/build-codex-skills.sh --check && bash scripts/build-cursor-skills.sh --check && grep -c 'pi -p' pi/skills/superagent/SKILL.md && grep -c 'bridge-fanout' pi/skills/superloop/SKILL.md && grep -n '^SUPER_HARNESS=\|^SUPER_MODEL_IMPLEMENTER=\|^SUPER_PI_SUBAGENTS=' pi/templates/superenv.default && ls pi/scripts`
Expected: three `up to date` lines; non-zero counts; `SUPER_HARNESS=pi`, `SUPER_MODEL_IMPLEMENTER=inherit`, `SUPER_PI_SUBAGENTS=recommended`; `_common.sh bridge-fanout.sh role-bridge.sh`.

Also run the shim test from Task 4 again against the real `pi/` tree (drop the stub-copy lines): the tick must find `pi/skills/superagent/SKILL.md`.

- [ ] **Step 4: Commit**

```bash
git add scripts/build-pi-skills.sh scripts/build-codex-skills.sh scripts/build-cursor-skills.sh pi codex cursor
git commit -m "feat(pi): build-pi-skills.sh and the generated pi/ package; codex/cursor builds drop pi-only"
```

---

### Task 8: `scripts/pi-smoke.sh` — live probes P1–P4 and tests T1–T5

**Files:**
- Create: `scripts/pi-smoke.sh`
- Modify: `.gitignore` (add `pi-smoke-report.md`)

**Interfaces:**
- Consumes: `pi/` build (Task 7), bridge/fan-out (Tasks 2–3), templates (Task 5).
- Produces: `pi-smoke-report.md` at the repo root (gitignored); always exits 0.

- [ ] **Step 1: Write `scripts/pi-smoke.sh`**

Reuse `codex-smoke.sh`'s `run_test` helper verbatim (report framing, truncation, timeout wrapper). Body after the helper:

```bash
NEUTRAL="$(mktemp -d)"; trap 'rm -rf "$NEUTRAL"' EXIT
( cd "$NEUTRAL" && git init -q )
PI_MODEL="${PI_SMOKE_MODEL:-}"            # optional: provider/id to pin; empty = the CLI default
MODEL_ARGS=(); [ -n "$PI_MODEL" ] && MODEL_ARGS=(--model "$PI_MODEL")
SUBAGENTS_VERSION="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$HOME/.pi/agent/npm/node_modules/pi-subagents/package.json" 2>/dev/null | head -1)"
echo "- pi-subagents: ${SUBAGENTS_VERSION:-absent}" >>"$REPORT"
echo "- superpowers package: $(pi list 2>/dev/null | grep -c superpowers)" >>"$REPORT"

# P1 — exit status on a failed turn (decides the bridge's 3-vs-4 mapping; informational).
run_test "P1 exit status on bad model (informational)" "" \
  "$BIN" -p --no-session --model "nonexistent-provider/no-such-model" "Reply with exactly: NEVER"

# P2 — --skill delivery + probe skill + superpowers listing.
run_test "P2 --skill delivery (probe skill)" "PROBE-BEGIN" \
  bash -c "cd '$NEUTRAL' && echo 'Run the pi smoke probe skill (pi-smoke-probe) and output its report. If you cannot find any such skill, output exactly: NO-SUCH-SKILL' | '$BIN' -p --no-session --approve --skill '$ROOT/pi/skills' ${MODEL_ARGS[*]}"

# P3 — pi-subagents blocking child, model pin, nested foreground wait (skipped when absent).
if [ -n "$SUBAGENTS_VERSION" ]; then
  mkdir -p "$NEUTRAL/.pi/agents"
  cat >"$NEUTRAL/.pi/agents/smoke-child.md" <<'EOF'
---
name: smoke-child
description: smoke child
tools: bash
async: false
---
Reply with exactly what the prompt asks. Also append on a second line: MODEL=<the model id you are running as, if you know it>.
EOF
  cat >"$NEUTRAL/.pi/agents/smoke-parent.md" <<'EOF'
---
name: smoke-parent
description: smoke parent
async: false
allowNestedSubagents: true
---
Use the subagent tool with agent smoke-child and async false, prompt "Reply with exactly: GRANDCHILD-OK". Output exactly: NEST-OK <its reply>.
EOF
  run_test "P3a subagent async:false returns child output" "SUB-OK CHILD-OK" \
    bash -c "cd '$NEUTRAL' && echo 'Use the subagent tool with agent smoke-child, async false, prompt: Reply with exactly: CHILD-OK. Then output exactly: SUB-OK <its first line>.' | '$BIN' -p --no-session --approve ${MODEL_ARGS[*]}"
  run_test "P3c nested foreground wait" "NEST-OK GRANDCHILD-OK" \
    bash -c "cd '$NEUTRAL' && echo 'Use the subagent tool with agent smoke-parent, async false, prompt: go. Output its reply verbatim.' | '$BIN' -p --no-session --approve ${MODEL_ARGS[*]}"
else
  echo "## P3 pi-subagents probes — SKIPPED (package absent)" >>"$REPORT"
fi

# P4 — --tools allowlist excludes extension tools; no flag includes them (informational).
run_test "P4a --tools role set hides subagent" "" \
  bash -c "echo 'List the names of every tool you have, one per line, nothing else.' | '$BIN' -p --no-session --tools read,edit,write,bash,grep,find,ls ${MODEL_ARGS[*]}"
run_test "P4b no --tools shows extension tools" "" \
  bash -c "echo 'List the names of every tool you have, one per line, nothing else.' | '$BIN' -p --no-session ${MODEL_ARGS[*]}"

# T1 — bridge echo → pi with the new flags and SUPERAGENT_PI_SKILLS.
printf 'Reply with exactly: BRIDGE-ECHO-OK\n' >"$NEUTRAL/echo.txt"
run_test "T1 bridge → pi (role tools, --skill)" "BRIDGE-ECHO-OK" \
  env SUPERAGENT_PI_SKILLS="$ROOT/pi/skills" "$ROOT/scripts/role-bridge.sh" --harness pi --model "${PI_MODEL:-inherit}" --effort low --cwd "$NEUTRAL" --prompt-file "$NEUTRAL/echo.txt" --role smoke

# T2 — fan-out, three live echoes.
run_test "T2 bridge-fanout ×3" "=== PANELIST 3 exit=0 ===" \
  "$ROOT/scripts/bridge-fanout.sh" --harness pi --model "${PI_MODEL:-inherit}" --effort inherit --cwd "$NEUTRAL" --timeout 300 --prompt-file "$NEUTRAL/echo.txt" --prompt-file "$NEUTRAL/echo.txt" --prompt-file "$NEUTRAL/echo.txt"

# T3 — the REAL tick entry: file-read prompt drives the supervisor skill's hard gate.
run_test "T3 tick file-read + superagent hard gate" "requires a master plan" \
  bash -c "cd '$NEUTRAL' && echo 'Read the file $ROOT/pi/skills/superagent/SKILL.md and follow it: execute exactly ONE tick with no arguments (no PLAN.md, no loop file), in unattended/non-interactive mode. Show the skill response. If you cannot read that file, output exactly: CANNOT-READ.' | '$BIN' -p --no-session --approve --skill '$ROOT/pi/skills' ${MODEL_ARGS[*]}"

# T4 — relay definition round trip pi→codex (needs pi-subagents AND codex).
if [ -n "$SUBAGENTS_VERSION" ] && command -v codex >/dev/null 2>&1; then
  sed -e 's/<role>/implementer/g' -e 's/<KEY>/SUPER_MODEL_IMPLEMENTER/g' -e 's/<harness>/codex/g' \
      -e 's/<model>/inherit/g' -e 's/<effort>/low/g' -e '/^model: <relay-model>$/d' \
      -e "s#<bridge-path>#$ROOT/scripts/role-bridge.sh#g" "$ROOT/templates/super-role-pi-bridge-agent.md" >"$NEUTRAL/.pi/agents/super-implementer.md"
  export TMPDIR="$NEUTRAL/tmp"; mkdir -p "$TMPDIR"
  run_test "T4 relay definition round trip (pi→codex)" "RELAY-PROVEN" \
    bash -c "cd '$NEUTRAL' && out=\$(echo 'Use the subagent tool with agent super-implementer, async false, prompt: Reply with exactly: RELAY-OK. Output its reply verbatim.' | '$BIN' -p --no-session --approve ${MODEL_ARGS[*]}); echo \"\$out\"; ls '$TMPDIR'/superagent-bridge/implementer-*.log >/dev/null 2>&1 && [[ \"\$out\" == *RELAY-OK* ]] && echo RELAY-PROVEN"
else
  echo "## T4 relay round trip — SKIPPED (needs pi-subagents and codex)" >>"$REPORT"
fi

# T5 — build freshness (offline).
run_test "T5 build-pi-skills --check" "up to date" bash "$ROOT/scripts/build-pi-skills.sh" --check
```

Header/summary blocks mirror `codex-smoke.sh` with `BIN=pi`, `REPORT="$ROOT/pi-smoke-report.md"`, install hint `npm install -g @earendil-works/pi-coding-agent`, and the P2/P3a-failure note: "P2 or P3a failures are DESIGN-INPUT changes (skill delivery / SDD dispatch) — stop and reassess."

- [ ] **Step 2: `.gitignore`**

Append `pi-smoke-report.md`.

- [ ] **Step 3: Verify**

Run: `bash -n scripts/pi-smoke.sh && echo syntax ok; chmod +x scripts/pi-smoke.sh; bash scripts/pi-smoke.sh; tail -20 pi-smoke-report.md`
Expected on this machine (pi 0.84.3, `defaultProvider: openai-codex`, superpowers + pi-subagents installed): T1, T2, T3, T5 PASS; P2 PASS with `PROBE-BEGIN`; P3a/P3c PASS or recorded as design input; P1/P4 informational with their outputs captured. Record the P1 exit code and the P3c verdict in the Task 9 docs.

- [ ] **Step 4: Commit**

```bash
git add scripts/pi-smoke.sh .gitignore
git commit -m "test(pi): pi-smoke.sh — probes P1-P4 (exit status, --skill, pi-subagents, tools) and T1-T5"
```

---

### Task 9: Docs, changelog, version 0.6.0, rebuild all

**Files:**
- Modify: `.claude-plugin/plugin.json:4`, `CHANGELOG.md` (new top entry), `README.md` (Install, Prerequisites, Configuration key table, new `## Pi (experimental)` section before `## Cutting over an existing repo`), `scripts/README.md` (Harness section, exit-code table rows 5/6/7/8, Files list, Prerequisites), `pi/README.md` "Validated" section (via the build script's heredoc)
- Regenerate: `codex/`, `cursor/`, `pi/`

- [ ] **Step 1: Version**

`.claude-plugin/plugin.json`: `"version": "0.6.0"`.

- [ ] **Step 2: CHANGELOG entry**

```markdown
## 0.6.0 — <date>

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
- Tests: `bridge-test.sh` (fan-out + pi flags), `pi-smoke.sh` (P1–P4, T1–T5). Smoke result: <fill
  from the Task 8 run — pi version, pi-subagents version, P1 exit code, P3c verdict>.
```

- [ ] **Step 3: README.md**

Install: add `### Pi` after `### Cursor`:

```markdown
### Pi

No install step for the plugin itself: the external driver passes `--skill <repo>/pi/skills` on
every headless run (or `pi install /path/to/superagent-plugin/pi` for interactive use). Install
superpowers as a Pi package and, recommended, `pi-subagents`:

    npm install -g @earendil-works/pi-coding-agent
    pi install git:github.com/obra/superpowers
    pi install npm:pi-subagents        # ≥ 0.58.0 — recommended; see the Pi section below
```

Configuration key table: add `| SUPER_PI_SUBAGENTS | recommended | Pi harness only: recommended (WARN if pi-subagents is missing/old; SDD children then run sequentially without pins) · required (init aborts) · off. |`; in the effort-domain sentence change the Pi list to `off | minimal | low | medium | high | xhigh | max`; where `role-bridge.sh` `--tools` is described add `planner`.

New section (before `## Cutting over an existing repo`):

```markdown
## Pi (experimental)

A generated Pi build lives in [`pi/`](pi/README.md) — external (unattended) driver only, laid out
as a Pi package but delivered per run by `--skill`. `scripts/build-pi-skills.sh` derives it from
the same markers as the other builds plus a `pi-only` marker.

**Dispatch is hybrid.** The supervisor never uses a subagent tool: `superplan` and `superrun` are
blocking `bash` calls to `scripts/role-bridge.sh` (child `pi -p` — or `codex`/`claude`/`agent` for a
bridged role — with `--tools planner` / `--tools executor`), and the L7 panel is one blocking call
to `scripts/bridge-fanout.sh` (three concurrent bridge runs, 1800 s timeout, framed output).
superrun's SDD children go through superpowers' own Pi mapping — the `pi-subagents` `subagent`
tool with `async: false` — and their model/thinking pins ride `.pi/agents/super-<role>.md`
definitions `init` generates (native: `templates/super-role-pi-agent.md`; a role bridged to
another harness: `templates/super-role-pi-bridge-agent.md`, a relay). Without `pi-subagents`,
SDD runs sequentially in-context and pins are not applied (`SUPER_PI_SUBAGENTS=required` makes
init abort instead).

Every headless run passes `--approve` (the operator armed the loop on this repo — Cursor `--trust`
parity). Auth is the CLI's `~/.pi/agent/auth.json` or provider keys in the target repo's `.env`.
Model keys are `pi:<provider>/<model>` (or a bare `<provider>/<model>`); effort keys
`off | minimal | low | medium | high | xhigh | max` — the tick passes `--thinking`, the bridge the
`:<level>` suffix (or `--thinking` when the model is `inherit`).

**Status:** <fill from pi-smoke: date, pi version, pi-subagents version, pass counts; P1 exit
code; P3c nested-wait verdict>. Remaining gaps: no multi-tick loop driven to DONE on Pi; S3 with
`pi-subagents` not exercised inside a real superrun. Re-run: `bash scripts/pi-smoke.sh`
(`PI_SMOKE_MODEL=<provider>/<id>` to pin a model).
```

- [ ] **Step 4: scripts/README.md**

Harness heading → `## Harness (Claude CLI vs Cursor CLI vs Codex CLI vs Pi CLI)`; add a `- **pi:**` bullet: skills via `--skill <plugin-repo>/pi/skills` (build with `scripts/build-pi-skills.sh`); auth `~/.pi/agent/auth.json` or `.env` keys; model values `<provider>/<model>`, `inherit` omits `--model`; effort → `--thinking`; `--approve` on every run; exports `SUPERAGENT_FANOUT`, `SUPERAGENT_PI_SKILLS`. `--harness claude|cursor|codex|pi` in the usage sentence. Exit-code rows: 5 add `pi`; 6 `claude/cursor/codex/pi`; 7 add `pi/`; 8 → `… or, on the pi harness, SUPER_MODEL_SUPERVISOR is not a <provider>/<model> string.` Files list: add `bridge-fanout.sh …`, `build-pi-skills.sh [--check]`, `pi-smoke.sh`; extend the `role-bridge.sh` entry with `--tools role|planner|executor|<list>`.

- [ ] **Step 5: `pi/README.md` Validated section**

In `build-pi-skills.sh`'s README heredoc replace the `## Validated` placeholder line with the Task 8 results (pi version, pi-subagents version, which of P1–P4/T1–T5 passed, the P1 exit-code mapping the bridge relies on, the P3c verdict and what it means for a future S1/S4 promotion).

- [ ] **Step 6: Rebuild everything and verify**

Run: `bash scripts/build-codex-skills.sh && bash scripts/build-cursor-skills.sh && bash scripts/build-pi-skills.sh && for b in codex cursor pi; do bash scripts/build-$b-skills.sh --check; done && bash scripts/bridge-test.sh | tail -1 && grep -rn '"version"' .claude-plugin/plugin.json codex/plugins/superagent/.codex-plugin/plugin.json cursor/.cursor-plugin/plugin.json pi/package.json`
Expected: three `up to date`; `bridge-test: 0 failure(s)`; four `0.6.0` lines.

- [ ] **Step 7: Commit**

```bash
git add .claude-plugin/plugin.json CHANGELOG.md README.md scripts/README.md scripts/build-pi-skills.sh codex cursor pi
git commit -m "docs: Pi harness section, scripts README, changelog; bump to 0.6.0; rebuild generated trees"
```

---

### Task 10: End-to-end verification (manual, needs keys) and PR

**Files:** none new (findings go into `CHANGELOG.md` / `pi/README.md` "Known gaps" if anything changes).

- [ ] **Step 1: Init on a throwaway repo under Pi**

In a scratch git repo with a remote and `gh` auth: write `.superenv` with `SUPER_HARNESS=pi`, `SUPER_MODEL_SUPERVISOR=pi:openai-codex/gpt-5.5`, `SUPER_MODEL_IMPLEMENTER=pi:openai-codex/gpt-5.5`, `SUPER_EFFORT_IMPLEMENTER=low`, `SUPER_MODEL_TASK_REVIEWER=codex:gpt-5.6-sol`. Run: `pi --approve --skill <repo>/pi/skills "Read <repo>/pi/skills/init/SKILL.md and run it."`
Expected: summary rows show `implementer · pi · openai-codex/gpt-5.5 · low · native (definition: generated)`, `task-reviewer · codex · gpt-5.6-sol · inherit · bridge(codex)`, planner/executor/panel `bridge(pi)`; files `.pi/agents/super-implementer.md` (model + thinking lines) and `.pi/agents/super-task-reviewer.md` (relay, no `model:` line since `SUPER_BRIDGE_RELAY_MODEL=inherit`).

- [ ] **Step 2: One attended tick**

`bash scripts/launch.sh <PLAN.md> --harness pi --dry-run` then the real `superagent-tick.sh` once with `LOG_FILE` set. Expected: the log shows `harness=pi`, a `superplan` bridge dispatch (`role-bridge: log=…planner-…`), status advancing `WAITING FOR PLAN → WAITING FOR RUN`, lock released, `exit=0`.

- [ ] **Step 3: One `superrun` tick**

Run the next tick. Expected: `role-bridge: log=…executor-…`; inside that log, SDD dispatches via `subagent` with `agent: super-implementer` and the relay `super-task-reviewer` producing a codex-side `implementer`/`task-reviewer` log under `$TMPDIR/superagent-bridge/`; a PR opened. If `pi-subagents` short-circuits the relay (answers instead of bridging — the haiku failure mode), record it and set `SUPER_BRIDGE_RELAY_MODEL` to a stronger model in `pi/templates/superenv.default`.

- [ ] **Step 4: Record and ship**

Update `pi/README.md` Validated/Known gaps and the README status line with what actually ran (via the build script; rebuild; `--check`). Then:

```bash
git push -u origin spec/pi-harness
gh pr create --title "feat: Pi harness (SUPER_HARNESS=pi) with hybrid dispatch; 0.6.0" --body-file - <<'EOF'
Implements docs/superpowers/specs/2026-08-29-pi-harness-design.md (plan: docs/superpowers/plans/2026-08-30-pi-harness.md).

- pi tick branch (--skill delivery, --approve, --thinking, --mode json); pi in launch/install-timer/bootstrap
- role-bridge.sh pi branch: tools sets (role|planner|executor), --approve/--no-session, --skill, --thinking
- bridge-fanout.sh: L7 panel primitive (concurrent bridge runs, timeout, framed output)
- pi-only skill blocks; build-pi-skills.sh → pi/; codex/cursor builds drop pi-only
- pi-subagents recommended (SUPER_PI_SUBAGENTS), .pi/agents definitions from two new templates
- bridge-test.sh extended; pi-smoke.sh (P1–P4, T1–T5); docs; 0.6.0

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
```

---

## Self-review

**Spec coverage.** §1 architecture table → Tasks 2, 3, 6. §2 `_common.sh` → Task 1; `superagent-tick.sh` (build check, model/effort, `--approve`, `--skill`, exports, auth note, exit 8) → Task 4; `role-bridge.sh` (tools sets, `--approve --no-session`, `--skill`, `--thinking`) → Task 2; `bridge-fanout.sh` → Task 3; `launch.sh`/`install-timer.sh` → Task 4. §3 build (`pi/` layout, markers, substitutions, banner, probe skill, model-name guard, `--check`) → Task 7 (the model-name guard is `init`'s `pi-only` validation text, Task 6); dispatch rules (S1/S2, L7, S3) → Task 6. §4 `superenv.default` + `SUPER_PI_SUBAGENTS` → Task 5; `init` prerequisites/validation/definitions → Task 6; templates → Task 5; docs → Task 9. §5 probes P1–P4 and tests T1–T5 → Task 8 (spec's T3 `--thinking` argv assertion is offline in Task 2; spec's T6 build check is Task 8 T5 + Task 7). Error-handling summary → Tasks 3, 4, 6. Decisions 1–6 are all encoded; decision 7 (commit) is done.

**Placeholder scan.** The only intentionally unfilled values are the smoke-result blanks in Task 9 (`<fill from …>`), which depend on Task 8's live run — the plan says exactly which numbers go there.

**Type consistency.** Bridge flags: `--tools role|planner|executor|<list>` (Tasks 2, 3, 6, 8). Env: `SUPERAGENT_BRIDGE`, `SUPERAGENT_FANOUT`, `SUPERAGENT_PI_SKILLS` (Tasks 2, 4, 6). Fan-out framing `=== PANELIST <n> exit=<rc> ===` / `=== END <n> ===` and `BRIDGE-FAILED exit=… harness=… role=<role>-<n> log=…` (Tasks 3, 6, 8). Template placeholders `<role> <KEY> <model> <effort> <harness> <relay-model> <bridge-path>` (Tasks 5, 6, 8). Key `SUPER_PI_SUBAGENTS=recommended|required|off` (Tasks 5, 6, 7, 9). Definition path `.pi/agents/super-<role>.md` (Tasks 6, 8, 10). Exit codes: bridge 0/2/3/4/64, fan-out 0/3/64, tick 7/8/11 (Tasks 1–4, 9).
