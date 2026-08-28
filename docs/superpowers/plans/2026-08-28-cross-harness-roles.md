# Cross-Harness Role Mixing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let one `.superenv` pin each agent role to a different harness CLI (`claude`, `codex`, `cursor`, `pi`) inside a single loop, with foreign roles executed through a shared bridge script behind the existing per-role subagent hook.

**Architecture:** Role values gain a `[harness:]<model>` grammar parsed by a new `_common.sh` helper. A bridged role is dispatched exactly as today (`subagent_type: super-<role>` on Claude/Cursor, `spawn_agent` on Codex) but the answering subagent is a thin relay — a generated agent definition (Claude/Cursor) or a rendered preamble (Codex) — that writes its prompt to a file, runs `scripts/role-bridge.sh --harness <h> …`, and returns the foreign CLI's last message verbatim. `superagent:init` validates the grammar, checks foreign binaries, and generates the relay definitions.

**Tech Stack:** bash (scripts, tests with PATH shims), Markdown skill files with `cc-only` / `cursor-only` / `codex-only` build markers, `scripts/build-codex-skills.sh` / `scripts/build-cursor-skills.sh` generators.

**Spec:** `docs/superpowers/specs/2026-08-28-cross-harness-roles-design.md`

## Global Constraints

- Version bump to **0.5.0** in `.claude-plugin/plugin.json`; both generated builds pick it up from there.
- Harness vocabulary is exactly `claude | codex | cursor | pi` — the same words as `SUPER_HARNESS`.
- `SUPER_MODEL_SUPERVISOR` must be native to `SUPER_HARNESS` (hard error otherwise).
- Bridge exit codes: `0` ok · `2` binary not found · `3` CLI exited non-zero · `4` empty result.
- `inherit` always omits the corresponding CLI flag; out-of-domain effort → WARN → `inherit`.
- Never `${N:?}` in `_common.sh` (it is sourced by scripts running under `set -u`; use `${1:-}` + explicit checks). Never set `CLAUDE_CODE_EFFORT_LEVEL`.
- Generated builds (`codex/`, `cursor/`) are committed artifacts: after any change to a canonical skill, template, or build script, re-run both build scripts and commit the regenerated trees; `scripts/build-codex-skills.sh --check` must exit 0.
- Commit after every task; all work on branch `cross-harness-roles`; PR into `main` at the end (protected main).

---

## File map

| Path | Responsibility |
|---|---|
| `scripts/role-bridge.sh` (new) | Run one foreign-harness CLI headless with a prompt file; print last message. |
| `scripts/bridge-test.sh` (new) | Offline tests: PATH shims for the four CLIs; also tests the `_common.sh` role parser. |
| `scripts/bridge-smoke.sh` (new) | Live probes T1–T7 against real CLIs; writes `bridge-smoke-report.md`. |
| `scripts/_common.sh` | `superagent_role_harness`, `superagent_role_model`, `superagent_effort_valid`, harness `pi` in bridge context. |
| `scripts/superagent-tick.sh` | Supervisor prefix strip/native check; export `SUPERAGENT_BRIDGE`. |
| `templates/superenv.default` | Grammar header; `SUPER_BRIDGE_RELAY_MODEL`. |
| `templates/super-role-bridge-agent.md` (new) | Relay agent definition rendered by init for bridged roles (Claude/Cursor). |
| `templates/relay-preamble.md` (new) | Relay instructions prepended to a `spawn_agent` message on Codex. |
| `skills/init/SKILL.md` | Validation of the grammar/effort domains; binary checks; relay generation; report table. |
| `skills/superrun/SKILL.md`, `skills/superagent/SKILL.md`, `skills/superloop/SKILL.md` | Dispatch rule for bridged roles (one sentence per block). |
| `scripts/build-codex-skills.sh`, `scripts/build-cursor-skills.sh` | Ship `scripts/role-bridge.sh` + new templates; superenv header; banner; probe skill. |
| `README.md`, `scripts/README.md`, `codex/README.md`, `CHANGELOG.md` | Docs. |

---

### Task 1: Nested `claude -p` probe (decides one bridge flag)

**Files:**
- Create: `scripts/bridge-smoke.sh` (skeleton with T5 only; later tasks add T1–T4, T6, T7)

**Interfaces:**
- Produces: the decision `BRIDGE_UNSET_CLAUDECODE=true|false` recorded as a comment at the top of `scripts/role-bridge.sh` in Task 2, and the `bridge-smoke.sh` harness (`run_test` helper) reused by Task 8.

- [ ] **Step 1: Write the smoke skeleton with the nested-claude probe**

```bash
#!/usr/bin/env bash
# bridge-smoke.sh — live probes for scripts/role-bridge.sh against real CLIs.
# Run on a machine with the CLIs installed; missing CLIs are reported as SKIP.
# Always exits 0; writes bridge-smoke-report.md at the repo root — failures are the data.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT="$ROOT/bridge-smoke-report.md"
BRIDGE="$ROOT/scripts/role-bridge.sh"
WORK="$(mktemp -d)"
TIMEOUT_SECS=240
TCMD=()
if command -v timeout >/dev/null 2>&1; then TCMD=(timeout "$TIMEOUT_SECS")
elif command -v gtimeout >/dev/null 2>&1; then TCMD=(gtimeout "$TIMEOUT_SECS"); fi

{
  echo "# superagent bridge smoke report"
  echo
  echo "- date: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
  echo "- host: $(uname -a)"
  echo "- repo: $ROOT ($(cd "$ROOT" && git rev-parse --short HEAD 2>/dev/null || echo 'no git'))"
  for b in claude codex agent pi; do
    if command -v "$b" >/dev/null 2>&1; then echo "- $b: $("$b" --version 2>&1 | head -1)"; else echo "- $b: NOT FOUND"; fi
  done
  echo
} >"$REPORT"

PASS=0; FAIL=0; SKIP=0
# run_test <name> <required-binary-or-empty> <expected-substring> <cmd...>
run_test() {
  local name="$1" need="$2" expect="$3"; shift 3
  echo "## $name" >>"$REPORT"
  if [ -n "$need" ] && ! command -v "$need" >/dev/null 2>&1; then
    echo "SKIP (no $need on PATH)" >>"$REPORT"; echo >>"$REPORT"; SKIP=$((SKIP+1)); return
  fi
  local out rc
  out="$("${TCMD[@]+"${TCMD[@]}"}" "$@" 2>&1)"; rc=$?
  { echo; echo '```'; printf '$ %q ' "$@"; echo; echo "$out" | tail -40; echo "exit=$rc"; echo '```'; } >>"$REPORT"
  if [ "$rc" -eq 0 ] && [[ "$out" == *"$expect"* ]]; then echo "PASS" >>"$REPORT"; PASS=$((PASS+1))
  else echo "FAIL (expected substring: $expect)" >>"$REPORT"; FAIL=$((FAIL+1)); fi
  echo >>"$REPORT"
}

# T5 — nested claude: can `claude -p` run while CLAUDECODE is set (as it is inside a Claude Code
# session's Bash tool)? Both variants are recorded; the bridge unsets CLAUDECODE iff plain fails.
printf 'Reply with exactly: NESTED-OK\n' >"$WORK/nested.txt"
run_test "T5a nested claude -p (CLAUDECODE=1, plain)" claude "NESTED-OK" \
  env CLAUDECODE=1 claude -p --model haiku "$(cat "$WORK/nested.txt")"
run_test "T5b nested claude -p (CLAUDECODE unset)" claude "NESTED-OK" \
  env -u CLAUDECODE claude -p --model haiku "$(cat "$WORK/nested.txt")"

{ echo "---"; echo "PASS=$PASS FAIL=$FAIL SKIP=$SKIP"; } >>"$REPORT"
echo "bridge-smoke: PASS=$PASS FAIL=$FAIL SKIP=$SKIP — report: $REPORT"
```

- [ ] **Step 2: Run it**

Run: `bash scripts/bridge-smoke.sh && sed -n '/T5a/,$p' bridge-smoke-report.md`
Expected: T5b PASS. T5a either PASS (→ `BRIDGE_UNSET_CLAUDECODE=false`) or FAIL with Claude Code's nested-session refusal (→ `BRIDGE_UNSET_CLAUDECODE=true`). Record the outcome; Task 2 Step 3 uses it.

- [ ] **Step 3: Add the report to `.gitignore` and commit the skeleton**

```bash
echo 'bridge-smoke-report.md' >> .gitignore
git add scripts/bridge-smoke.sh .gitignore
git commit -m "test: bridge-smoke skeleton with nested-claude probe (T5)"
```

---

### Task 2: `scripts/role-bridge.sh` with offline shim tests

**Files:**
- Create: `scripts/role-bridge.sh`
- Create: `scripts/bridge-test.sh`

**Interfaces:**
- Produces: `role-bridge.sh --harness claude|codex|cursor|pi --model <m|inherit> --effort <e|inherit> --cwd <dir> --prompt-file <file> [--role <name>]`; stdout = final message; stderr = one line `role-bridge: log=<path>`; exit codes 0/2/3/4. Honors `SUPER_CODEX_SANDBOX` (env; default `danger-full-access`).

- [ ] **Step 1: Write the failing shim test**

```bash
#!/usr/bin/env bash
# bridge-test.sh — offline tests for scripts/role-bridge.sh (PATH shims) and the
# _common.sh role parser. No network, no real CLIs. Exit 1 on any failure.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRIDGE="$ROOT/scripts/role-bridge.sh"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
SHIM="$T/bin"; mkdir -p "$SHIM" "$T/cwd"
export PATH="$SHIM:$PATH"
export TMPDIR="$T/tmp"; mkdir -p "$TMPDIR"
FAILS=0
ok()   { echo "ok   - $1"; }
fail() { echo "FAIL - $1"; FAILS=$((FAILS+1)); }
check() { local name="$1"; shift; if "$@" >/dev/null 2>&1; then ok "$name"; else fail "$name"; fi; }

# Each shim records argv (one per line) to $T/<name>.argv, stdin to $T/<name>.stdin, then
# behaves per $SHIM_MODE: ok (print/write result) | fail (exit 9) | empty (exit 0, nothing).
mkshim() {
  local name="$1"
  cat >"$SHIM/$name" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$@" >"$T/$name.argv"
cat >"$T/$name.stdin"
case "\${SHIM_MODE:-ok}" in
  fail) echo "boom" >&2; exit 9 ;;
  empty) exit 0 ;;
esac
# codex writes -o <file>; everything else prints to stdout
out=""; prev=""
for a in "\$@"; do [ "\$prev" = "-o" ] && out="\$a"; prev="\$a"; done
if [ -n "\$out" ]; then echo "RESULT-$name" >"\$out"; echo "progress chatter" ; else echo "RESULT-$name"; fi
EOF
  chmod +x "$SHIM/$name"
}
for b in claude codex agent pi; do mkshim "$b"; done
printf 'hello prompt\nline two\n' >"$T/prompt.txt"
argv() { cat "$T/$1.argv" | tr '\n' ' '; }

# ── claude ──
out="$(SUPER_CODEX_SANDBOX= "$BRIDGE" --harness claude --model sonnet --effort high --cwd "$T/cwd" --prompt-file "$T/prompt.txt" --role implementer 2>"$T/err")"; rc=$?
check "claude: exit 0"            [ "$rc" -eq 0 ]
check "claude: stdout is result"  [ "$out" = "RESULT-claude" ]
check "claude: argv"              [ "$(argv claude)" = "-p --model sonnet --effort high --allowedTools Read,Edit,Write,Bash,Grep,Glob " ]
check "claude: prompt on stdin"   cmp -s "$T/claude.stdin" "$T/prompt.txt"
check "claude: log path on stderr" grep -q '^role-bridge: log=' "$T/err"
"$BRIDGE" --harness claude --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1
check "claude: inherit omits flags" [ "$(argv claude)" = "-p --allowedTools Read,Edit,Write,Bash,Grep,Glob " ]

# ── codex ──
out="$("$BRIDGE" --harness codex --model gpt-5.6-terra --effort medium --cwd "$T/cwd" --prompt-file "$T/prompt.txt" 2>/dev/null)"
check "codex: stdout is -o file content" [ "$out" = "RESULT-codex" ]
check "codex: default sandbox flag" grep -q -- '--dangerously-bypass-approvals-and-sandbox' "$T/codex.argv"
check "codex: model/effort/cwd flags" bash -c "a=\"\$(cat '$T/codex.argv' | tr '\n' ' ')\"; [[ \"\$a\" == *'-m gpt-5.6-terra '* && \"\$a\" == *'-c model_reasoning_effort=medium '* && \"\$a\" == *'-C $T/cwd '* && \"\$a\" == *'--skip-git-git-repo-check'* || \"\$a\" == *'--skip-git-repo-check '* ]]"
check "codex: prompt via stdin (-)" bash -c "tail -1 '$T/codex.argv' | grep -qx -- '-' && cmp -s '$T/codex.stdin' '$T/prompt.txt'"
SUPER_CODEX_SANDBOX=workspace-write "$BRIDGE" --harness codex --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1
check "codex: workspace-write flags" bash -c "a=\"\$(cat '$T/codex.argv' | tr '\n' ' ')\"; [[ \"\$a\" == *'--sandbox workspace-write -c sandbox_workspace_write.network_access=true '* && \"\$a\" != *' -m '* ]]"

# ── cursor ──
out="$("$BRIDGE" --harness cursor --model auto --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" 2>/dev/null)"
check "cursor: stdout"  [ "$out" = "RESULT-agent" ]
check "cursor: argv"    bash -c "a=\"\$(cat '$T/agent.argv' | tr '\n' ' ')\"; [[ \"\$a\" == '-p hello prompt'* && \"\$a\" == *'--trust --force --model auto --output-format text '* ]]"

# ── pi ──
out="$("$BRIDGE" --harness pi --model openai/gpt-5 --effort high --cwd "$T/cwd" --prompt-file "$T/prompt.txt" 2>/dev/null)"
check "pi: stdout"  [ "$out" = "RESULT-pi" ]
check "pi: model with level suffix" [ "$(argv pi)" = "-p --model openai/gpt-5:high " ]
"$BRIDGE" --harness pi --model openai/gpt-5 --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1
check "pi: no suffix when effort inherit" [ "$(argv pi)" = "-p --model openai/gpt-5 " ]

# ── exit codes ──
SHIM_MODE=fail "$BRIDGE" --harness claude --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1; rc=$?
check "exit 3 when CLI fails" [ "$rc" -eq 3 ]
SHIM_MODE=empty "$BRIDGE" --harness claude --model inherit --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1; rc=$?
check "exit 4 on empty result" [ "$rc" -eq 4 ]
PATH="/usr/bin:/bin" "$BRIDGE" --harness pi --model x/y --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1; rc=$?
check "exit 2 when binary missing" [ "$rc" -eq 2 ]
"$BRIDGE" --harness nope --model x --effort inherit --cwd "$T/cwd" --prompt-file "$T/prompt.txt" >/dev/null 2>&1; rc=$?
check "usage error on bad harness" [ "$rc" -eq 64 ]

echo "bridge-test: $FAILS failure(s)"
[ "$FAILS" -eq 0 ]
```

(Fix the obvious typo in the codex flags check before running: the alternation should test only `'--skip-git-repo-check '`.)

- [ ] **Step 2: Run it to verify it fails**

Run: `bash scripts/bridge-test.sh`
Expected: every check FAILs (bridge does not exist) and exit 1.

- [ ] **Step 3: Write the bridge**

```bash
#!/usr/bin/env bash
# role-bridge.sh — run ONE agent role on a foreign harness CLI, headless.
#
#   role-bridge.sh --harness claude|codex|cursor|pi --model <m|inherit> --effort <e|inherit>
#                  --cwd <dir> --prompt-file <file> [--role <name>]
#
# Reads the prompt from <file>, runs the harness CLI in <dir>, prints the CLI's final message on
# stdout and NOTHING else. CLI chatter/stderr goes to $TMPDIR/superagent-bridge/<role>-<stamp>.log
# (path printed on stderr as "role-bridge: log=<path>").
# Exit: 0 ok · 2 CLI binary not found · 3 CLI exited non-zero · 4 CLI exited 0 with empty result ·
#       64 usage. "inherit" omits the corresponding flag.
# Env: SUPER_CODEX_SANDBOX (danger-full-access default | workspace-write) for --harness codex.
# BRIDGE_UNSET_CLAUDECODE=<true|false>  — set from Task 1's T5 probe result: true if a plain
# nested `claude -p` was refused under CLAUDECODE=1.
set -uo pipefail

BRIDGE_UNSET_CLAUDECODE=false   # <- replace with Task 1's finding

harness=""; model="inherit"; effort="inherit"; cwd=""; prompt_file=""; role="role"
while [ $# -gt 0 ]; do
  case "$1" in
    --harness)     harness="${2:-}"; shift 2 ;;
    --model)       model="${2:-inherit}"; shift 2 ;;
    --effort)      effort="${2:-inherit}"; shift 2 ;;
    --cwd)         cwd="${2:-}"; shift 2 ;;
    --prompt-file) prompt_file="${2:-}"; shift 2 ;;
    --role)        role="${2:-role}"; shift 2 ;;
    *) echo "role-bridge: unknown argument '$1'" >&2; exit 64 ;;
  esac
done
case "$harness" in claude|codex|cursor|pi) ;; *) echo "role-bridge: --harness must be claude|codex|cursor|pi (got '$harness')" >&2; exit 64 ;; esac
[ -d "$cwd" ] || { echo "role-bridge: --cwd '$cwd' is not a directory" >&2; exit 64; }
[ -f "$prompt_file" ] || { echo "role-bridge: --prompt-file '$prompt_file' not found" >&2; exit 64; }

logdir="${TMPDIR:-/tmp}/superagent-bridge"; mkdir -p "$logdir"
stamp="$(date -u '+%Y%m%dT%H%M%SZ')-$$"
log="$logdir/${role}-${stamp}.log"
echo "role-bridge: log=$log" >&2

bin=""; case "$harness" in claude) bin=claude ;; codex) bin=codex ;; cursor) bin=agent ;; pi) bin=pi ;; esac
command -v "$bin" >/dev/null 2>&1 || { echo "role-bridge: '$bin' not found on PATH (harness=$harness)" >&2; exit 2; }

result=""; rc=0
case "$harness" in
  claude)
    args=(-p)
    [ "$model"  != inherit ] && args+=(--model "$model")
    [ "$effort" != inherit ] && args+=(--effort "$effort")
    args+=(--allowedTools "Read,Edit,Write,Bash,Grep,Glob")
    envargs=(-u CLAUDE_CODE_EFFORT_LEVEL)
    [ "$BRIDGE_UNSET_CLAUDECODE" = true ] && envargs+=(-u CLAUDECODE)
    result="$(cd "$cwd" && env "${envargs[@]}" claude "${args[@]}" <"$prompt_file" 2>>"$log")" || rc=$?
    ;;
  codex)
    args=(exec)
    if [ "${SUPER_CODEX_SANDBOX:-danger-full-access}" = workspace-write ]; then
      args+=(--sandbox workspace-write -c sandbox_workspace_write.network_access=true)
    else
      args+=(--dangerously-bypass-approvals-and-sandbox)
    fi
    out="$logdir/${role}-${stamp}.last"
    args+=(--skip-git-repo-check -C "$cwd")
    [ "$model"  != inherit ] && args+=(-m "$model")
    [ "$effort" != inherit ] && args+=(-c "model_reasoning_effort=$effort")
    args+=(-o "$out" -)
    (cd "$cwd" && codex "${args[@]}" <"$prompt_file" >>"$log" 2>&1) || rc=$?
    [ -f "$out" ] && result="$(cat "$out")"
    ;;
  cursor)
    args=(-p "$(cat "$prompt_file")" --trust --force)
    [ "$model" != inherit ] && args+=(--model "$model")
    args+=(--output-format text)
    result="$(cd "$cwd" && agent "${args[@]}" 2>>"$log")" || rc=$?
    ;;
  pi)
    args=(-p)
    m="$model"; [ "$effort" != inherit ] && m="${m}:${effort}"
    [ "$model" != inherit ] && args+=(--model "$m")
    result="$(cd "$cwd" && pi "${args[@]}" <"$prompt_file" 2>>"$log")" || rc=$?
    ;;
esac

if [ "$rc" -ne 0 ]; then echo "role-bridge: $bin exited $rc (see $log)" >&2; exit 3; fi
if [ -z "$result" ]; then echo "role-bridge: $bin returned an empty result (see $log)" >&2; exit 4; fi
printf '%s\n' "$result"
```

Set `BRIDGE_UNSET_CLAUDECODE` per Task 1's outcome. Note the cursor case passes the prompt as an argument (the Cursor CLI has no documented stdin prompt mode) — the shim test expects that.

- [ ] **Step 4: Run tests**

Run: `chmod +x scripts/role-bridge.sh scripts/bridge-test.sh scripts/bridge-smoke.sh && bash scripts/bridge-test.sh`
Expected: `bridge-test: 0 failure(s)`, exit 0.

- [ ] **Step 5: Commit**

```bash
git add scripts/role-bridge.sh scripts/bridge-test.sh
git commit -m "feat: role-bridge.sh — run one role on a foreign harness CLI (claude/codex/cursor/pi)"
```

---

### Task 3: Role-value parser in `_common.sh`, supervisor guard and `SUPERAGENT_BRIDGE` export in the tick

**Files:**
- Modify: `scripts/_common.sh:76-92` (harness section) — add three helpers after `superagent_harness`
- Modify: `scripts/superagent-tick.sh:145-181` (model resolution) and the export block near line 319
- Modify: `scripts/bridge-test.sh` — append a parser section

**Interfaces:**
- Produces:
  - `superagent_role_harness <value>` → prints `claude|codex|cursor|pi|inherit|unknown` (prefix wins; inference: tiers/`^claude-`→claude; `^gpt-|^o[0-9]|^codex`→codex; contains `/`→pi).
  - `superagent_role_model <value>` → prints the value with any `<harness>:` prefix stripped.
  - `superagent_effort_valid <harness> <effort>` → exit 0 iff in domain (claude `low|medium|high|xhigh|max|inherit`; codex `none|minimal|low|medium|high|xhigh|inherit`; pi `off|minimal|low|medium|high|inherit`; cursor `inherit`).
  - Tick env: `SUPERAGENT_BRIDGE=<abs path to scripts/role-bridge.sh>`.

- [ ] **Step 1: Append failing parser tests to `scripts/bridge-test.sh`** (before the final summary lines)

```bash
# ── _common.sh role parser ──
. "$ROOT/scripts/_common.sh"
ph() { [ "$(superagent_role_harness "$1")" = "$2" ]; }
check "parse: tier → claude"          ph sonnet claude
check "parse: claude- id → claude"    ph claude-fable-5 claude
check "parse: gpt- → codex"           ph gpt-5.6-terra codex
check "parse: o-series → codex"       ph o4-mini codex
check "parse: codex- → codex"         ph codex-mini codex
check "parse: slash → pi"             ph openai/gpt-5 pi
check "parse: prefix wins"            ph pi:sonnet pi
check "parse: cursor prefix"          ph cursor:auto cursor
check "parse: inherit"                ph inherit inherit
check "parse: unknown"                ph sonet unknown
check "parse: model strip"            [ "$(superagent_role_model codex:gpt-5.6-sol)" = gpt-5.6-sol ]
check "parse: model no prefix"        [ "$(superagent_role_model opus)" = opus ]
check "effort: claude max ok"         superagent_effort_valid claude max
check "effort: codex max rejected"    bash -c '! superagent_effort_valid codex max' 
check "effort: pi off ok"             superagent_effort_valid pi off
check "effort: cursor high rejected"  bash -c '! superagent_effort_valid cursor high'
check "effort: inherit always ok"     superagent_effort_valid cursor inherit
```

(`bash -c '! …'` needs the function: replace those two with `if superagent_effort_valid codex max; then fail "…"; else ok "…"; fi` style lines.)

- [ ] **Step 2: Run to verify it fails**

Run: `bash scripts/bridge-test.sh 2>&1 | grep -c '^FAIL'`
Expected: 17 (the parser checks).

- [ ] **Step 3: Implement the helpers in `_common.sh`** (after `superagent_harness`)

```bash
# Role model value grammar: "inherit" | [harness ":"] model, harness = claude|codex|cursor|pi.
# superagent_role_harness <value> -> claude|codex|cursor|pi|inherit|unknown  (prefix wins;
# otherwise inferred: tier names / claude-* -> claude; gpt-* / o<digit>* / codex* -> codex;
# a "/" (provider/model) -> pi). superagent_role_model <value> -> value minus any prefix.
superagent_role_harness() {
  local v="${1:-}"
  case "$v" in
    inherit|"") echo inherit; return ;;
    claude:*|codex:*|cursor:*|pi:*) echo "${v%%:*}"; return ;;
  esac
  case "$v" in
    sonnet|opus|haiku|fable|claude-*) echo claude ;;
    gpt-*|o[0-9]*|codex*)             echo codex ;;
    */*)                              echo pi ;;
    *)                                echo unknown ;;
  esac
}
superagent_role_model() {
  local v="${1:-}"
  case "$v" in claude:*|codex:*|cursor:*|pi:*) echo "${v#*:}" ;; *) echo "$v" ;; esac
}
# superagent_effort_valid <harness> <effort> -> 0 iff effort is in that harness's domain.
superagent_effort_valid() {
  local h="${1:-}" e="${2:-inherit}"
  [ "$e" = inherit ] && return 0
  case "$h" in
    claude) case "$e" in low|medium|high|xhigh|max) return 0 ;; esac ;;
    codex)  case "$e" in none|minimal|low|medium|high|xhigh) return 0 ;; esac ;;
    pi)     case "$e" in off|minimal|low|medium|high) return 0 ;; esac ;;
  esac
  return 1
}
```

- [ ] **Step 4: Run tests**

Run: `bash scripts/bridge-test.sh`
Expected: `bridge-test: 0 failure(s)`.

- [ ] **Step 5: Supervisor guard + bridge export in the tick**

In `scripts/superagent-tick.sh`, immediately after the `if/elif/else` block that sets `TICK_MODEL` (ends at line 181 `fi`), add:

```bash
# Role-value grammar ([harness:]<model>) — the supervisor must be native to this harness:
# strip a matching prefix, abort on a foreign one (a bridged supervisor is not a thing).
if [[ -n "$TICK_MODEL" ]]; then
  _sup_h="$(superagent_role_harness "$TICK_MODEL")"
  if [[ "$_sup_h" != "$HARNESS" && "$_sup_h" != inherit && "$_sup_h" != unknown ]]; then
    echo "superagent-tick: SUPER_MODEL_SUPERVISOR='$TICK_MODEL' names harness '$_sup_h' but SUPER_HARNESS=$HARNESS — the supervisor cannot be bridged" >&2
    exit 8
  fi
  TICK_MODEL="$(superagent_role_model "$TICK_MODEL")"
fi
# Bridged roles (a role key naming another harness) run through this script; export its
# path so relay agents never depend on a plugin-cache path baked at init time.
export SUPERAGENT_BRIDGE="$PLUGIN_ROOT/scripts/role-bridge.sh"
```

Add exit code `8` to the exit-code table in `scripts/README.md` ("supervisor model names a foreign harness").

- [ ] **Step 6: Verify the tick still parses and the guard fires**

Run: `bash -n scripts/superagent-tick.sh && SUPER_MODEL_SUPERVISOR=codex:gpt-5 LOOP_FILE=/nonexistent REPO=. bash scripts/superagent-tick.sh; echo "exit=$?"`
Expected: syntax ok; the run fails — either with `exit=8` and the foreign-harness message, or earlier on the missing loop file (in which case set `LOOP_FILE` to any existing loop-status file or a temp file with `status: DONE` and re-run until the exit-8 path is exercised — record which in the commit body).

- [ ] **Step 7: Commit**

```bash
git add scripts/_common.sh scripts/superagent-tick.sh scripts/bridge-test.sh scripts/README.md
git commit -m "feat: [harness:]<model> role grammar helpers; supervisor native guard; export SUPERAGENT_BRIDGE"
```

---

### Task 4: Templates — relay agent definition, relay preamble, `superenv.default`

**Files:**
- Create: `templates/super-role-bridge-agent.md`
- Create: `templates/relay-preamble.md`
- Modify: `templates/superenv.default:1-13` (header) and the `# ── Model per agent role` block (add `SUPER_BRIDGE_RELAY_MODEL`)

**Interfaces:**
- Produces: placeholders used by `init` (Task 5): `<role>`, `<KEY>`, `<harness>`, `<model>`, `<effort>`, `<relay-model>`, `<bridge-path>`.

- [ ] **Step 1: Write `templates/super-role-bridge-agent.md`**

```markdown
---
name: super-<role>
description: superagent <role> role agent — BRIDGED to the <harness> harness (<KEY>). Relays the task prompt to `<harness>` via role-bridge.sh and returns its result verbatim. Generated by superagent:init; do not edit by hand.
model: <relay-model>
---

<!-- generated-by: superagent:init (from .superenv <KEY>) — bridged role; re-run superagent:init after changing the key; do not edit by hand -->

You are the superagent `<role>` relay. You do NOT perform the task yourself. Your entire job:

1. Write the COMPLETE prompt you received — every line, verbatim, nothing added or summarized —
   to a new temp file: `f="$(mktemp "${TMPDIR:-/tmp}/super-<role>.XXXXXX")"` (use Bash with a
   quoted heredoc, `cat >"$f" <<'PROMPT' … PROMPT`).
2. Run, from your current working directory (the same checkout/worktree the prompt refers to):
   `"${SUPERAGENT_BRIDGE:-<bridge-path>}" --harness <harness> --model "<model>" --effort "<effort>" --cwd "$PWD" --prompt-file "$f" --role <role>`
   Wait for it to finish; it may take many minutes. Never modify files yourself.
3. If it exited 0: reply with its stdout **verbatim** as your final message — no preamble, no
   commentary, no summary.
4. If it exited non-zero: reply with exactly
   `BRIDGE-FAILED exit=<code> harness=<harness> role=<role> log=<the log= path it printed on stderr>`
   followed by the last 40 lines of that log file. Do not retry.
```

- [ ] **Step 2: Write `templates/relay-preamble.md`** (same contract, addressed to a `spawn_agent` child; the dispatcher appends the task prompt after the marker line)

```markdown
You are the superagent `<role>` relay. You do NOT perform the task yourself. Your entire job:

1. Write everything below the line `=== TASK PROMPT ===` — every line, verbatim, nothing added or
   summarized — to a new temp file: `f="$(mktemp "${TMPDIR:-/tmp}/super-<role>.XXXXXX")"` (shell,
   quoted heredoc).
2. Run, from your current working directory:
   `"<bridge-path>" --harness <harness> --model "<model>" --effort "<effort>" --cwd "$PWD" --prompt-file "$f" --role <role>`
   Wait for it to finish; it may take many minutes. Never modify files yourself.
3. If it exited 0: reply with its stdout **verbatim** as your final message — nothing else.
4. If it exited non-zero: reply with exactly
   `BRIDGE-FAILED exit=<code> harness=<harness> role=<role> log=<the log= path it printed on stderr>`
   followed by the last 40 lines of that log file. Do not retry.

=== TASK PROMPT ===
```

- [ ] **Step 3: Update `templates/superenv.default`**

Replace the header lines 3–8 (`# Model values: … takes any form.)`) with:

```
# Model values: "inherit", or [<harness>:]<model> where <harness> is claude | codex | cursor | pi
# and <model> is that harness's native model string — claude: a tier (sonnet|opus|haiku|fable) or
# full ID (claude-fable-5); codex: a Codex model (gpt-5.6-sol); cursor: `agent --list-models`;
# pi: <provider>/<model> (openai/gpt-5, anthropic/claude-opus-5). The prefix is optional when the
# model is recognizable (tiers/claude-* → claude, gpt-*/o<n>/codex* → codex, a "/" → pi).
# A role whose harness differs from SUPER_HARNESS is BRIDGED: dispatched through the same
# per-role subagent hook, executed by that harness's CLI via scripts/role-bridge.sh (the CLI must
# be installed and logged in). SUPER_MODEL_SUPERVISOR must be native to SUPER_HARNESS.
# "inherit" = omit the model override. On claude, a full ID, a non-inherit effort, or a bridged
# harness on any role key except SUPER_MODEL_SUPERVISOR needs the per-role agent definition in
# .claude/agents/ — re-run superagent:init after setting one.
```

After the `SUPER_PANEL_AGENT_TYPE` line add:

```
SUPER_BRIDGE_RELAY_MODEL=haiku          # model of the thin relay subagent that runs role-bridge.sh for a BRIDGED role (native value or inherit)
```

In the effort header, after the `cursor:` line, add `#   pi:     off | minimal | low | medium | high (applied as the :<level> model suffix)` and change the sentence `Values are harness-native effort names` to `Values are effort names in the ROLE's harness (see the model grammar above)`.

- [ ] **Step 4: Verify the file still sources cleanly**

Run: `bash -c 'set -euo pipefail; . templates/superenv.default; echo "$SUPER_BRIDGE_RELAY_MODEL"'`
Expected: `haiku`.

- [ ] **Step 5: Commit**

```bash
git add templates/super-role-bridge-agent.md templates/relay-preamble.md templates/superenv.default
git commit -m "feat(templates): relay agent + preamble templates; [harness:]<model> grammar and SUPER_BRIDGE_RELAY_MODEL in superenv.default"
```

---

### Task 5: `superagent:init` — validate the grammar, check binaries, generate relay definitions

**Files:**
- Modify: `skills/init/SKILL.md:118-140` (validation items 5–6), `:157-235` (Step 3 generation rules), Step 1 prerequisite list (`:76-97`)

**Interfaces:**
- Consumes: `superagent_role_harness` semantics (Task 3) — restated in prose since skills don't source `_common.sh`; templates from Task 4.
- Produces: `.claude/agents/super-<role>.md` rendered from `super-role-bridge-agent.md` for bridged roles; an init report table `role · harness · model · effort · dispatch`.

- [ ] **Step 1: Rewrite validation item 5 (model keys)** — replace the three harness-specific blocks with one harness-neutral block followed by the native-domain blocks:

```markdown
5. **Model keys** (each `SUPER_MODEL_*`): grammar `inherit | [<harness>:]<model>`, `<harness>` ∈
   `claude|codex|cursor|pi`. Resolve each key's **harness**: an explicit prefix wins; otherwise infer —
   `sonnet|opus|haiku|fable|claude-*` → `claude`; `gpt-*|o<digit>*|codex*` → `codex`; a value
   containing `/` → `pi`; anything else → WARN "unrecognized model value", treat as `inherit`.
   Strip the prefix to get the **model**. The role is **native** when its harness equals
   `SUPER_HARNESS`, else **bridged**. `SUPER_MODEL_SUPERVISOR` must be native: a foreign harness
   there is a **hard error** (stop and report; the tick refuses it too).
   Native model values are further validated per build:
<!-- cc-only:start -->
   a tier name (`sonnet|opus|haiku|fable`), `inherit`, or a full Claude model ID (`^claude-`).
<!-- cc-only:end -->
<!-- cursor-only:start
   a Cursor model name (`agent --list-models`) or `inherit`.
cursor-only:end -->
<!-- codex-only:start
   a Codex model name or `inherit`.
codex-only:end -->
   Bridged model values are not validated beyond the grammar (the foreign CLI owns its names), except
   `pi`, whose model must contain exactly one `/` (`<provider>/<model>`).
   `SUPER_BRIDGE_RELAY_MODEL` is validated as a native model value.
```

- [ ] **Step 2: Rewrite validation item 6 (effort keys)** to validate in the **role's harness** domain:

```markdown
6. **Effort keys** (each `SUPER_EFFORT_<ROLE>`): valid in the domain of the ROLE's harness (from
   item 5; the supervisor's harness is `SUPER_HARNESS`): claude `low|medium|high|xhigh|max`;
   codex `none|minimal|low|medium|high|xhigh` (no `max`); pi `off|minimal|low|medium|high`;
   cursor: `inherit` only. `inherit` is always valid. Out of domain → WARN, treat as `inherit`.
```

- [ ] **Step 3: Add the bridge-target prerequisite check** as Step 1 item 5 (after the scheduler note):

```markdown
5. **Bridge targets.** For every harness that appears as a *bridged* role harness in the resolved
   config (item 5 of the validation below): its CLI must be on PATH — `claude`, `codex`, `agent`
   (Cursor), `pi` — else **ABORT** with an install hint (claude: `npm install -g
   @anthropic-ai/claude-code`; codex: `npm install -g @openai/codex`; cursor: the Cursor CLI
   installer; pi: `npm install -g @earendil-works/pi-coding-agent`). Auth is WARN-only: codex →
   `OPENAI_API_KEY` set or `~/.codex/auth.json` present; pi → for a `<provider>/` of `openai` or
   `anthropic`, `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` set; claude/cursor → binary only.
   Also run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/role-bridge.sh" 2>&1 | head -1` — a usage line
   proves the bridge shipped with this build; a "not found" is a broken install: ABORT.
```

- [ ] **Step 4: Step 3 generation rules for bridged roles.** In the `cc-only` block starting `- **Generate when:**`, insert BEFORE it:

```markdown
- **Bridged role (its harness ≠ `SUPER_HARNESS`):** render
  `${CLAUDE_PLUGIN_ROOT}/templates/super-role-bridge-agent.md` to the listed path, substituting
  `<role>`, `<KEY>` (both keys), `<harness>`, `<model>` (prefix stripped), `<effort>` (`inherit`
  when unset/invalid), `<relay-model>` = `SUPER_BRIDGE_RELAY_MODEL` (drop the `model:` line when
  `inherit`), and `<bridge-path>` = the absolute path of
  `${CLAUDE_PLUGIN_ROOT}/scripts/role-bridge.sh`. Same marker/ownership rules as below. A bridged
  panel role ignores `SUPER_PANEL_AGENT_TYPE` (WARN once).
```

Add the identical block (with `super-role-bridge-agent.md` from this build's `templates/`) at the top of the `cursor-only` generation block. In the `codex-only` block, replace the first bullet's tail with: "…`inherit` = omit the parameter. For a **bridged** role, the loop instead spawns a relay: `model` = `SUPER_BRIDGE_RELAY_MODEL` (omit when `inherit`) and a message built from `${SUPER_PLUGIN_ROOT}/templates/relay-preamble.md` (substituting `<role>`, `<harness>`, `<model>`, `<effort>`, `<bridge-path>` = `${SUPER_PLUGIN_ROOT}/scripts/role-bridge.sh`) followed by the task prompt. Record `dispatch=bridge(<harness>)` in the summary."

- [ ] **Step 5: Report table.** Replace the sentence `Report per-key results (…) as one summary row.` with:

```markdown
Report one summary row per role: `role · harness · model · effort · dispatch` where dispatch is
`native`, `native (definition: generated|regenerated|unchanged|removed (stale)|conflict)`, or
`bridge(<harness>)`.
```

- [ ] **Step 6: Build check** (the markers must still balance)

Run: `bash scripts/build-codex-skills.sh --check; bash scripts/build-cursor-skills.sh --check; echo "exit=$?"`
Expected: both report the tree is stale (non-zero) but with no awk/marker errors; regenerate: `bash scripts/build-codex-skills.sh && bash scripts/build-cursor-skills.sh`, then `grep -c "cc-only\|cursor-only" codex/plugins/superagent/skills/init/SKILL.md` → `0`.

- [ ] **Step 7: Commit**

```bash
git add skills/init/SKILL.md codex cursor
git commit -m "feat(init): validate [harness:]<model> role grammar, check bridge-target CLIs, generate relay definitions for bridged roles"
```

---

### Task 6: Dispatch rules in `superrun`, `superagent`, `superloop`, and the Codex build banner

**Files:**
- Modify: `skills/superrun/SKILL.md:119-150` (Model policy)
- Modify: `skills/superagent/SKILL.md:177-186` (Model resolution)
- Modify: `skills/superloop/SKILL.md:689-715` (Rung 1 panel, all three blocks)
- Modify: `scripts/build-codex-skills.sh:90-96` (banner tool mapping)

**Interfaces:**
- Consumes: relay definitions / preamble from Tasks 4–5.

- [ ] **Step 1: `superrun` Model policy** — after the sentence ending `never silently substitute a cheaper tier.` add:

```markdown
   **Bridged roles:** a value naming a harness other than `SUPER_HARNESS` (explicit
   `codex:`/`pi:`/`cursor:`/`claude:` prefix, or inferred — `gpt-*`→codex, `<provider>/<model>`→pi)
   is dispatched with `subagent_type: super-<role>` and no `model:`, exactly like a full-ID pin;
   the definition `superagent:init` generated is a relay that runs the foreign CLI and returns its
   result verbatim. A reply beginning `BRIDGE-FAILED` is a failed subagent: treat it as you would an
   implementer/reviewer that crashed (retry once, then the skill's normal escalation), and quote the
   `log=` path in the BLOCKED report. Missing definition = hard error (re-run `superagent:init`).
```

In the `codex-only` effort block append: "A **bridged** role (harness ≠ codex) is spawned as a relay: `model` = `SUPER_BRIDGE_RELAY_MODEL` (omit when `inherit`), message = `${SUPER_PLUGIN_ROOT}/templates/relay-preamble.md` rendered for the role + the full task prompt; a `BRIDGE-FAILED` reply is a failed subagent."

- [ ] **Step 2: `superagent` Model resolution** — add a fourth bullet:

```markdown
- A **bridged** value (harness prefix or inference ≠ `SUPER_HARNESS`, e.g. `codex:gpt-5.6-sol`,
  `openai/gpt-5`) → dispatch with `subagent_type: super-planner` / `super-executor` and omit
  `model:`; the generated definition is a relay to that harness's CLI. A Final Report that begins
  `BRIDGE-FAILED` is a failed dispatch — route it through the escalation ladder like any other
  crashed subagent, quoting its `log=` path.
```

(The `codex-only` counterpart, if this section has one, gets the `spawn_agent` relay sentence from Step 1.)

- [ ] **Step 3: `superloop` Rung 1** — in the `cc-only` and `cursor-only` blocks, extend the "dispatch with `subagent_type: super-panel` instead" condition with "**or `SUPER_MODEL_PANEL` is bridged (names another harness)**". In the `codex-only` block add: "If `SUPER_MODEL_PANEL` is bridged, each panelist is a relay spawn (`model` = `SUPER_BRIDGE_RELAY_MODEL`, message = rendered `relay-preamble.md` + the packet)."

- [ ] **Step 4: Codex build banner** — in `scripts/build-codex-skills.sh` after the sentence `pass the role's resolved model/effort as spawn parameters instead.` add: `A role whose value names another harness (\`claude:sonnet\`, \`pi:openai/gpt-5\`, …) is BRIDGED: spawn a relay child (model = SUPER_BRIDGE_RELAY_MODEL) whose message is \`${SUPER_PLUGIN_ROOT}/templates/relay-preamble.md\` rendered for that role followed by the task prompt; the relay runs \`${SUPER_PLUGIN_ROOT}/scripts/role-bridge.sh\` and returns the foreign CLI's result verbatim.`

- [ ] **Step 5: Rebuild and verify marker hygiene**

Run: `bash scripts/build-codex-skills.sh && bash scripts/build-cursor-skills.sh && grep -rl "cc-only\|cursor-only" codex/plugins/superagent/skills cursor/skills; echo "leaks=$?"`
Expected: no files listed (`leaks=1`).

- [ ] **Step 6: Commit**

```bash
git add skills/superrun/SKILL.md skills/superagent/SKILL.md skills/superloop/SKILL.md scripts/build-codex-skills.sh codex cursor
git commit -m "feat(skills): dispatch bridged roles via relay definitions / relay spawns; BRIDGE-FAILED handling"
```

---

### Task 7: Ship the bridge and templates in the generated builds

**Files:**
- Modify: `scripts/build-codex-skills.sh:170-176` (templates copy) and the probe skill `:134-170`; superenv awk `:178-220`
- Modify: `scripts/build-cursor-skills.sh:159-161` (templates copy) and the probe skill `:124-158`; superenv awk `:164-213`

**Interfaces:**
- Produces: `codex/plugins/superagent/scripts/role-bridge.sh`, `cursor/scripts/role-bridge.sh`, both templates in each build's `templates/`; probe report line `role_bridge_present: <yes|no>`.

- [ ] **Step 1: Copy steps** — in both build scripts, next to the existing `cp "$ROOT/templates/super-role-agent.md" …` lines add:

```bash
cp "$ROOT/templates/super-role-bridge-agent.md" "$TMP/plugins/superagent/templates/"   # codex build
cp "$ROOT/templates/relay-preamble.md"          "$TMP/plugins/superagent/templates/"
mkdir -p "$TMP/plugins/superagent/scripts"
cp "$ROOT/scripts/role-bridge.sh" "$TMP/plugins/superagent/scripts/"
chmod +x "$TMP/plugins/superagent/scripts/role-bridge.sh"
```

(cursor build: same with `$TMP/templates/` and `$TMP/scripts/`.)

- [ ] **Step 2: Probe skill** — add to each probe's check list `Check whether <plugin_root>/scripts/role-bridge.sh exists and is executable` and to the report block `role_bridge_present: <yes|no>`.

- [ ] **Step 3: superenv header** — in both awk blocks that rewrite the `# Model values:` header, replace the printed lines with the harness-neutral grammar text from Task 4 Step 3 (with the build's native line first), and add a sed `-e 's/^SUPER_BRIDGE_RELAY_MODEL=haiku\([[:space:]]*\)#.*/SUPER_BRIDGE_RELAY_MODEL=inherit\1# relay subagent model for BRIDGED roles; inherit = the CLI default subagent model/'`.

- [ ] **Step 4: Rebuild, check, run offline tests against the shipped copy**

Run: `bash scripts/build-codex-skills.sh && bash scripts/build-cursor-skills.sh && bash scripts/build-codex-skills.sh --check && cmp scripts/role-bridge.sh codex/plugins/superagent/scripts/role-bridge.sh && cmp scripts/role-bridge.sh cursor/scripts/role-bridge.sh && grep -n "SUPER_BRIDGE_RELAY_MODEL" codex/plugins/superagent/templates/superenv.default cursor/templates/superenv.default`
Expected: `--check` exit 0, both `cmp` silent, both grep hits show `=inherit`.

- [ ] **Step 5: Commit**

```bash
git add scripts/build-codex-skills.sh scripts/build-cursor-skills.sh codex cursor
git commit -m "build: ship role-bridge.sh and relay templates in the codex and cursor builds; probe reports role_bridge_present"
```

---

### Task 8: Live smoke probes T1–T4, T6, T7

**Files:**
- Modify: `scripts/bridge-smoke.sh` (from Task 1)

**Interfaces:**
- Consumes: `role-bridge.sh` (Task 2), relay definition template (Task 4).

- [ ] **Step 1: Add the probes** before the summary lines:

```bash
printf 'Reply with exactly: BRIDGE-ECHO-OK\n' >"$WORK/echo.txt"
run_test "T1 bridge → claude"  claude "BRIDGE-ECHO-OK" "$BRIDGE" --harness claude --model haiku        --effort low     --cwd "$WORK" --prompt-file "$WORK/echo.txt" --role smoke
run_test "T2 bridge → codex"   codex  "BRIDGE-ECHO-OK" "$BRIDGE" --harness codex  --model inherit      --effort low     --cwd "$WORK" --prompt-file "$WORK/echo.txt" --role smoke
run_test "T3 bridge → cursor"  agent  "BRIDGE-ECHO-OK" "$BRIDGE" --harness cursor --model inherit      --effort inherit --cwd "$WORK" --prompt-file "$WORK/echo.txt" --role smoke
run_test "T4 bridge → pi"      pi     "BRIDGE-ECHO-OK" "$BRIDGE" --harness pi     --model "${PI_SMOKE_MODEL:-openai/gpt-5}" --effort low --cwd "$WORK" --prompt-file "$WORK/echo.txt" --role smoke

# T6 — relay definition round trip under Claude Code: a throwaway repo with a generated
# super-implementer.md bridged to codex; the session must return the sentinel.
if command -v claude >/dev/null 2>&1 && command -v codex >/dev/null 2>&1; then
  R="$WORK/t6"; mkdir -p "$R/.claude/agents"; (cd "$R" && git init -q)
  sed -e 's/<role>/implementer/g' -e 's/<KEY>/SUPER_MODEL_IMPLEMENTER/g' -e 's/<harness>/codex/g' \
      -e 's/<model>/inherit/g' -e 's/<effort>/low/g' -e 's/<relay-model>/haiku/g' \
      -e "s#<bridge-path>#$BRIDGE#g" "$ROOT/templates/super-role-bridge-agent.md" >"$R/.claude/agents/super-implementer.md"
  run_test "T6 relay definition round trip (claude→codex)" claude "RELAY-OK" \
    env SUPERAGENT_BRIDGE="$BRIDGE" claude -p --model haiku --allowedTools "Bash,Task" \
      "Dispatch ONE subagent with subagent_type: super-implementer and the prompt 'Reply with exactly: RELAY-OK'. Output its reply verbatim." \
      2>&1
fi

# T7 — spawn_agent relay round trip under Codex (codex→claude).
if command -v codex >/dev/null 2>&1 && command -v claude >/dev/null 2>&1; then
  pre="$(sed -e 's/<role>/implementer/g' -e 's/<harness>/claude/g' -e 's/<model>/haiku/g' -e 's/<effort>/low/g' -e "s#<bridge-path>#$BRIDGE#g" "$ROOT/templates/relay-preamble.md")"
  run_test "T7 spawn_agent relay round trip (codex→claude)" codex "RELAY-OK" \
    codex exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox -C "$WORK" \
      "Spawn ONE agent (spawn_agent) with this exact message, then output its reply verbatim: $(printf '%s\nReply with exactly: RELAY-OK' "$pre")"
fi
```

- [ ] **Step 2: Run**

Run: `bash scripts/bridge-smoke.sh; sed -n '/^---/,$p' bridge-smoke-report.md`
Expected: every probe whose CLI is installed and authenticated → PASS; others SKIP. Any FAIL is a finding: fix the bridge (argv/stdin handling) or the template wording, re-run `scripts/bridge-test.sh`, and re-run the smoke until the installed set passes. Paste the summary line into the commit body.

- [ ] **Step 3: Commit**

```bash
git add scripts/bridge-smoke.sh
git commit -m "test: bridge-smoke T1–T7 — per-harness echo probes and relay round trips"
```

---

### Task 9: Docs, changelog, version 0.5.0, rebuild

**Files:**
- Modify: `README.md:123-148` (Configuration prose) and the key table; `README.md` Codex/Cursor sections
- Modify: `scripts/README.md:43-70` (Model/Effort/Harness sections), `:197-262` (Files list), exit-code table
- Modify: `codex/README.md` (via `scripts/build-codex-skills.sh` if generated — check the header; else edit directly)
- Modify: `CHANGELOG.md`, `.claude-plugin/plugin.json`

- [ ] **Step 1: README Configuration** — replace the two paragraphs starting `` `SUPER_MODEL_*` keys accept …`` and `` `SUPER_EFFORT_*` keys set …`` with prose covering: the `[harness:]<model>` grammar and inference table; native vs bridged; that a bridged role runs through a relay + `scripts/role-bridge.sh` on that harness's CLI (must be installed and authenticated on the host); effort domains per role harness (claude/codex/pi/cursor); `SUPER_MODEL_SUPERVISOR` native-only; `SUPER_BRIDGE_RELAY_MODEL`. Add a row to the key table:

```markdown
| SUPER_BRIDGE_RELAY_MODEL | `haiku` (Codex/Cursor builds: `inherit`) | Model of the thin relay subagent that runs `role-bridge.sh` for a bridged role — it only copies a prompt and returns a result, so keep it cheap. |
```

Add a worked example under the table:

```markdown
Mixing example — Claude supervisor, OpenAI implementer, Pi-hosted panel:

    SUPER_HARNESS=claude
    SUPER_MODEL_IMPLEMENTER=codex:gpt-5.6-terra   SUPER_EFFORT_IMPLEMENTER=medium
    SUPER_MODEL_PANEL=pi:openai/gpt-5             SUPER_EFFORT_PANEL=high
```

- [ ] **Step 2: `scripts/README.md`** — Model section: the grammar; Files list: add `role-bridge.sh`, `bridge-test.sh`, `bridge-smoke.sh` entries (one line each, mirroring the existing style); exit-code table: `8` (added in Task 3 — verify present).

- [ ] **Step 3: `codex/README.md`** — the "Model keys" bullet: `[harness:]<model>`; bridged roles spawn a relay; the plugin now ships `scripts/role-bridge.sh`. If `codex/README.md` is emitted by the build script, edit the heredoc in `scripts/build-codex-skills.sh` instead and rebuild.

- [ ] **Step 4: CHANGELOG + version**

```markdown
## 0.5.0 — <today's date>

- **Cross-harness role mixing.** Role keys accept `[<harness>:]<model>` (`claude|codex|cursor|pi`); a
  role naming a harness other than `SUPER_HARNESS` is *bridged*: dispatched through the existing
  per-role subagent hook, executed by that harness's CLI via new `scripts/role-bridge.sh`, result
  returned verbatim. Relay definitions (`templates/super-role-bridge-agent.md`) are generated by
  `superagent:init` on Claude/Cursor; Codex spawns a relay from `templates/relay-preamble.md`.
  New key `SUPER_BRIDGE_RELAY_MODEL`. Effort keys validate in the role's harness domain (pi:
  `off|minimal|low|medium|high`). `SUPER_MODEL_SUPERVISOR` must stay native (tick exit 8).
- Tests: `scripts/bridge-test.sh` (offline shims), `scripts/bridge-smoke.sh` (live T1–T7).
- Pi as a *supervisor* harness is not included — see the spec's follow-up note.
```

`sed -i '' 's/"version": "0.4.10"/"version": "0.5.0"/' .claude-plugin/plugin.json`

- [ ] **Step 5: Rebuild, final checks**

Run: `bash scripts/build-codex-skills.sh && bash scripts/build-cursor-skills.sh && bash scripts/build-codex-skills.sh --check && bash scripts/bridge-test.sh && grep -n '"version"' codex/plugins/superagent/.codex-plugin/plugin.json cursor/.cursor-plugin/plugin.json`
Expected: check exit 0, `bridge-test: 0 failure(s)`, both manifests `0.5.0`.

- [ ] **Step 6: Commit and open the PR**

```bash
git add README.md scripts/README.md codex cursor CHANGELOG.md .claude-plugin/plugin.json docs/superpowers/plans/2026-08-28-cross-harness-roles.md
git commit -m "docs: cross-harness role mixing; bump to 0.5.0"
git push -u origin cross-harness-roles
gh pr create --title "feat: cross-harness role mixing ([harness:]<model>, role-bridge.sh, relay agents); bump to 0.5.0" --body-file - <<'EOF'
Implements docs/superpowers/specs/2026-08-28-cross-harness-roles-design.md.

- `[harness:]<model>` role grammar (claude|codex|cursor|pi), inferred when unambiguous
- `scripts/role-bridge.sh` + offline shim tests + live smoke (T1–T7)
- relay agent definitions (Claude/Cursor) and relay spawns (Codex)
- init validation/binary checks; docs; 0.5.0

Smoke summary: <paste the PASS/FAIL/SKIP line from bridge-smoke-report.md>

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
```

---

### Task 10: End-to-end verification (manual, needs keys)

**Files:** none in the plugin; a scratch target repo.

- [ ] **Step 1: Claude supervisor, Codex implementer.** In a scratch repo with a trivial goal (one plan, one task: add a file), set `SUPER_HARNESS=claude`, `SUPER_MODEL_IMPLEMENTER=codex:<model>`, run `superagent:init` (confirm the report shows `implementer · codex · … · bridge(codex)` and `.claude/agents/super-implementer.md` contains `--harness codex`), then invoke `superagent:superrun` on the plan. Expected: the task's file is created by the bridged implementer, the reviewer (native) reviews it, the PR merges. Check `${TMPDIR:-/tmp}/superagent-bridge/implementer-*.log` exists.
- [ ] **Step 2: Mirror on Codex.** Same repo, `SUPER_HARNESS=codex`, `SUPER_MODEL_IMPLEMENTER=claude:sonnet`; run one external tick (`scripts/launch.sh <PLAN.md> --dry-run` then a real tick). Expected: the tick log shows the relay spawn and a `RESULT`-bearing reply; no `BRIDGE-FAILED`.
- [ ] **Step 3: Record outcomes** in the PR description (both runs: pass/fail + log paths), then merge per `superpowers:finishing-a-development-branch`.

---

## Self-review

- **Spec coverage:** §1 grammar/effort/new key/init validation → Tasks 3, 4, 5. §2 bridge script + build shipping + probe → Tasks 2, 7. §3 relay definitions, `SUPERAGENT_BRIDGE` export, dispatch rule, panel → Tasks 3, 4, 5, 6. §4 Codex/Cursor relay → Tasks 4, 5, 6, 7. §5 error handling → Tasks 2 (exit codes), 6 (`BRIDGE-FAILED` routing), 5 (init abort on missing binary). §6 testing → Tasks 1, 2, 8, 10. §7 docs/version → Task 9. Pi follow-up note → CHANGELOG line in Task 9.
- **Placeholder scan:** none; every step has its content. Two spots intentionally depend on an observed result (Task 1 → `BRIDGE_UNSET_CLAUDECODE`; Task 8 smoke fixes) and say what to do in each case.
- **Type consistency:** helper names `superagent_role_harness` / `superagent_role_model` / `superagent_effort_valid` are used identically in Tasks 3 and 5's prose; template placeholders `<role> <KEY> <harness> <model> <effort> <relay-model> <bridge-path>` match between Task 4 and Tasks 5/8; bridge flags `--harness --model --effort --cwd --prompt-file --role` match across Tasks 2, 4, 8.
