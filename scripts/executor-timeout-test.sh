#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
mkdir -p "$T/repo"
. "$ROOT/scripts/_common.sh"

load_superenv "$T/repo"
[[ "$(superagent_executor_timeout_ms)" == 7200000 ]] || exit 1

printf 'SUPER_EXECUTOR_TIMEOUT_MIN=180\n' >"$T/repo/.superenv"
[[ "$(env -u SUPER_EXECUTOR_TIMEOUT_MIN ROOT="$ROOT" REPO="$T/repo" bash -c '. "$ROOT/scripts/_common.sh"; load_superenv "$REPO"; superagent_executor_timeout_ms')" == 10800000 ]] || exit 1

SUPER_EXECUTOR_TIMEOUT_MIN=180
[[ "$(superagent_executor_timeout_ms)" == 10800000 ]] || exit 1

SUPER_EXECUTOR_TIMEOUT_MIN=invalid
if superagent_executor_timeout_ms >"$T/out" 2>"$T/err"; then exit 1; fi
grep -q 'SUPER_EXECUTOR_TIMEOUT_MIN' "$T/err" || exit 1
SUPER_EXECUTOR_TIMEOUT_MIN=0
if superagent_executor_timeout_ms >"$T/out" 2>"$T/err"; then exit 1; fi
# role-bridge.sh exports the executor deadline to an executor child (superrun's CHECKPOINT yield),
# keeps a caller-set deadline, and exports nothing to other roles.
mkdir -p "$T/bin" "$T/cwd"
printf '#!/bin/sh\ncat >/dev/null\necho "deadline=${SUPER_EXECUTOR_DEADLINE_EPOCH:-none} min=${SUPER_EXECUTOR_TIMEOUT_MIN:-none}"\n' >"$T/bin/claude"
chmod +x "$T/bin/claude"; echo prompt >"$T/prompt"
# bridge <tools> [VAR=value...] — run role-bridge.sh with a stub claude; prints the child's view.
bridge() {
  local tools="$1"; shift
  ( unset SUPER_EXECUTOR_DEADLINE_EPOCH SUPER_EXECUTOR_TIMEOUT_MIN
    env PATH="$T/bin:$PATH" TMPDIR="$T" "$@" "$ROOT/scripts/role-bridge.sh" --harness claude --tools "$tools" \
      --role "$tools" --cwd "$T/cwd" --prompt-file "$T/prompt" 2>/dev/null </dev/null )
}
before="$(date +%s)"
out="$(bridge executor SUPER_EXECUTOR_TIMEOUT_MIN=90)" || exit 1
d="${out#deadline=}"; d="${d%% *}"
[[ "$d" =~ ^[0-9]+$ ]] && (( d >= before + 5400 && d <= $(date +%s) + 5400 )) || { echo "executor deadline: $out" >&2; exit 1; }
[[ "$out" == *" min=90" ]] || exit 1
out="$(bridge executor)" || exit 1
d="${out#deadline=}"; d="${d%% *}"
(( d >= before + 7200 )) && [[ "$out" == *" min=120" ]] || { echo "default deadline: $out" >&2; exit 1; }
out="$(bridge executor SUPER_EXECUTOR_DEADLINE_EPOCH=12345)" || exit 1
[[ "$out" == "deadline=12345 "* ]] || { echo "caller deadline not kept: $out" >&2; exit 1; }
out="$(bridge executor SUPERAGENT_TICK_DEADLINE_EPOCH=1000)" || exit 1
[[ "$out" == "deadline=1000 "* ]] || { echo "earlier tick deadline not applied: $out" >&2; exit 1; }
out="$(bridge executor SUPERAGENT_TICK_DEADLINE_EPOCH=99999999999)" || exit 1
d="${out#deadline=}"; d="${d%% *}"
(( d < 99999999999 )) || { echo "later tick deadline wrongly applied: $out" >&2; exit 1; }
out="$(bridge role)" || exit 1
[[ "$out" == "deadline=none min=none" ]] || { echo "non-executor got a deadline: $out" >&2; exit 1; }
out="$(bridge executor SUPER_EXECUTOR_TIMEOUT_MIN=bogus)" || exit 1
[[ "$out" == "deadline=none "* ]] || { echo "invalid timeout exported a deadline: $out" >&2; exit 1; }

echo 'executor timeout config: PASS'
