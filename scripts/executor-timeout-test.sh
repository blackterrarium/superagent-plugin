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
echo 'executor timeout config: PASS'
