#!/usr/bin/env bash
# _common.sh — shared helpers for scripts/*. SOURCE this, do not execute.
#
# gh authentication in the loop: the driver runs each tick inside the claude
# CLI tool sandbox, which blocks gh from reading its own config
# (~/.config/gh/hosts.yml) and keyring. gh therefore only authenticates when a
# token is present in the environment as GH_TOKEN. superrun/superplan need gh for
# CI/PR operations (gh pr create / run watch / pr merge --admin), so the wrapper
# must ensure GH_TOKEN is exported before invoking the CLI — the child
# inherits it.

# Populate GH_TOKEN into the environment if not already set. Preference order:
#   1. an existing GH_TOKEN (e.g. sourced from .env — the canonical, repo-policy path)
#   2. GITHUB_TOKEN
#   3. the oauth_token in gh's config file (fallback for hosts where gh config is
#      readable by the wrapper but not by the sandboxed tick)
#   4. `gh auth token` (hosts where gh stores the token in the OS keyring — e.g.
#      the macOS keychain — which the wrapper context can read but hosts.yml
#      doesn't contain; the sandboxed tick child still can't, hence the export)
_superagent_load_gh_token() {
  if [[ -n "${GH_TOKEN:-}" ]]; then return 0; fi
  if [[ -n "${GITHUB_TOKEN:-}" ]]; then export GH_TOKEN="$GITHUB_TOKEN"; return 0; fi
  local cfg="${GH_CONFIG_DIR:-$HOME/.config/gh}/hosts.yml" tok=""
  if [[ -f "$cfg" ]]; then
    tok="$(sed -n 's/^[[:space:]]*oauth_token:[[:space:]]*//p' "$cfg" | head -1)"
  fi
  if [[ -z "$tok" ]] && command -v gh >/dev/null 2>&1; then
    tok="$(gh auth token 2>/dev/null || true)"
  fi
  [[ -n "$tok" ]] && export GH_TOKEN="$tok"
  return 0
}

# Fatal preflight: ensure gh is authenticated, else fail with a clear message.
# Returns non-zero when gh cannot authenticate — callers should abort the tick so
# a misconfigured host fails LOUDLY rather than silently breaking every PR/CI step.
ensure_gh_auth() {
  _superagent_load_gh_token
  if ! command -v gh >/dev/null 2>&1; then
    echo "superagent: gh CLI not found on PATH. superrun's CI/PR steps require it; aborting." >&2
    return 1
  fi
  if ! gh auth status >/dev/null 2>&1; then
    echo "superagent: gh is NOT authenticated. Set GH_TOKEN in .env (repo policy: API keys live in .env), export GH_TOKEN/GITHUB_TOKEN in the scheduler env, or make gh config readable. superrun's CI/PR steps (gh pr create / run watch / pr merge --admin) would fail; aborting tick." >&2
    return 1
  fi
  return 0
}

# Ensure the claude binary is findable. A systemd user service, launchd job, and
# cron all run with a minimal PATH that does NOT include the common user bin dirs,
# so a bare `claude` invocation fails with exit 127 ("No such file or directory").
# Prepend the common user bin dirs (incl. /opt/homebrew/bin for Apple Silicon
# Homebrew, where gh and claude commonly live) so the CLI is found under any
# scheduler.
_superagent_augment_path() {
  local extra="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin"
  case ":$PATH:" in
    *":$HOME/.local/bin:"*) ;;               # already present
    *) export PATH="$extra:$PATH" ;;
  esac
}

# Fatal check: ensure the claude CLI binary is on PATH (after augmentation).
# Returns non-zero with a clear message so a missing binary fails LOUDLY instead
# of the cryptic `timeout: failed to run command` exit 127.
ensure_claude_bin() {
  _superagent_augment_path
  if ! command -v claude >/dev/null 2>&1; then
    echo "superagent: 'claude' not found on PATH (checked incl. ~/.local/bin, /usr/local/bin). Install it or add its directory to PATH in the scheduler env; aborting." >&2
    return 1
  fi
  return 0
}

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

# Fatal check: ensure the Cursor CLI binary is findable; exports
# SUPERAGENT_CURSOR_BIN with the resolved name (`agent`, or legacy `cursor-agent`).
ensure_cursor_bin() {
  _superagent_augment_path
  local c
  for c in agent cursor-agent; do
    if command -v "$c" >/dev/null 2>&1; then
      export SUPERAGENT_CURSOR_BIN="$c"
      return 0
    fi
  done
  echo "superagent: Cursor CLI not found on PATH (tried: agent, cursor-agent; checked incl. ~/.local/bin, /usr/local/bin). Install it (curl https://cursor.com/install -fsS | bash) or add its directory to PATH in the scheduler env; aborting." >&2
  return 1
}

# Fatal check: ensure the OpenAI Codex CLI binary (`codex`) is findable.
ensure_codex_bin() {
  _superagent_augment_path
  if ! command -v codex >/dev/null 2>&1; then
    echo "superagent: Codex CLI not found on PATH (tried: codex; checked incl. ~/.local/bin, /usr/local/bin). Install it (npm install -g @openai/codex, or brew install codex) or add its directory to PATH in the scheduler env; aborting." >&2
    return 1
  fi
  return 0
}

# Fatal check for whichever CLI the resolved harness needs.
ensure_cli_bin() {
  local h; h="$(superagent_harness)" || return 1
  case "$h" in
    cursor) ensure_cursor_bin ;;
    codex)  ensure_codex_bin ;;
    *)      ensure_claude_bin ;;
  esac
}

# Non-fatal report: echoes "ok:<account>" (or "ok" if the account can't be parsed)
# when gh is authenticated, else "unauth". Used by status.sh.
gh_auth_state() {
  _superagent_load_gh_token
  command -v gh >/dev/null 2>&1 || { echo "no-gh"; return 0; }
  if gh auth status >/dev/null 2>&1; then
    local acct
    acct="$(gh auth status 2>/dev/null | sed -n 's/.*account \([^ ]*\).*/\1/p' | head -1)"
    echo "ok${acct:+:$acct}"
  else
    echo "unauth"
  fi
}

# ---------------------------------------------------------------------------
# Scheduler dispatch — systemd user timers on Linux, launchd LaunchAgents on
# macOS. Every lifecycle script (install/uninstall/launch/stop/force-stop/status)
# branches on superagent_scheduler(); the tick script itself is scheduler-agnostic.
# ---------------------------------------------------------------------------

superagent_scheduler() {
  if [[ "$(uname -s)" == "Darwin" ]]; then echo launchd; else echo systemd; fi
}

superagent_launchd_domain() { echo "gui/$(id -u)"; }
superagent_launchd_label()  { echo "com.superagent.tick.${1:?slug}"; }
superagent_launchd_plist()  { echo "$HOME/Library/LaunchAgents/com.superagent.tick.${1:?slug}.plist"; }

# Job state as launchd reports it: "running" while a tick process is executing,
# another value (e.g. "waiting") while loaded but idle, empty when not loaded.
# This is the launchd analog of systemctl is-active on BOTH units: non-empty ~
# timer active (job loaded), == running ~ service active (tick in flight).
superagent_launchd_state() {
  # launchctl exits 113 for a not-loaded job — swallow it inside the pipeline so
  # callers under `set -euo pipefail` see an empty string, not a fatal rc.
  { launchctl print "$(superagent_launchd_domain)/$(superagent_launchd_label "${1:?slug}")" 2>/dev/null || true; } \
    | sed -n 's/^[[:space:]]*state = //p' | head -1
}

# superagent_interval_secs <span> — systemd-style span (600, 90s, 30m, 15min, 2h)
# -> integer seconds, for launchd's StartInterval (which takes seconds only).
superagent_interval_secs() {
  local v="${1:?interval}" n unit
  if [[ "$v" =~ ^([0-9]+)[[:space:]]*(s|sec|seconds?|m|min|minutes?|h|hr|hours?|d|days?)?$ ]]; then
    n="${BASH_REMATCH[1]}"; unit="${BASH_REMATCH[2]:-s}"
    case "$unit" in
      s|sec|second|seconds) echo "$n" ;;
      m|min|minute|minutes) echo $((n * 60)) ;;
      h|hr|hour|hours)      echo $((n * 3600)) ;;
      d|day|days)           echo $((n * 86400)) ;;
    esac
  else
    echo "superagent: cannot parse interval '$v' (want e.g. 600, 90s, 30m, 15min, 2h)" >&2
    return 1
  fi
}

# load_superenv <repo-root> — three-layer SUPER_* resolution, highest wins:
#   process env  >  <repo-root>/.superenv  >  <plugin>/templates/superenv.default
# Bash cannot "source without overriding", so: snapshot pre-set SUPER_*/TICK_* vars,
# source defaults then repo file, then re-apply the snapshot.
load_superenv() {
  local repo="${1:?load_superenv needs the repo root}"
  local plugin_root; plugin_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  local snapshot; snapshot="$(mktemp)"
  { compgen -A variable | grep -E '^(SUPER_|TICK_)' | while read -r v; do
    printf '%s=%q\n' "$v" "${!v}"
  done ; } >"$snapshot" || true
  set -a
  [[ -f "$plugin_root/templates/superenv.default" ]] && . "$plugin_root/templates/superenv.default"
  [[ -f "$repo/.superenv" ]] && . "$repo/.superenv"
  . "$snapshot"
  set +a
  rm -f "$snapshot"
}

# ---------------------------------------------------------------------------
# Loop-status file readers — shared by the tick wrapper, answer.sh, status.sh.
# All are safe under a caller's `set -euo pipefail`: a missing/unreadable file,
# an absent field, or a missing/empty argument yields empty output, never a
# fatal rc and never an abort of the caller's shell (except where the rc IS
# the answer — superagent_pending_answer).
# ---------------------------------------------------------------------------

# superagent_loop_status <loop-file> — trimmed frontmatter `status:` value.
superagent_loop_status() {
  local f="${1:-}"
  [[ -n "$f" ]] || return 0
  { sed -n 's/^status:[[:space:]]*//p' "$f" 2>/dev/null | head -1 | sed 's/[[:space:]]*$//'; } || true
}

# superagent_pending_section <loop-file> — body of `## Pending decision`
# (heading excluded, up to the next `## ` heading).
superagent_pending_section() {
  local f="${1:-}"
  [[ -n "$f" ]] || return 0
  awk '/^## Pending decision/{f=1; next} /^## /{f=0} f' "$f" 2>/dev/null || true
}

# superagent_pending_answer <loop-file> — the first non-empty `answer: <x>` value
# INSIDE ## Pending decision (an answer: line elsewhere, e.g. under ## Decisions,
# never counts). Echoes the value and returns 0; returns 1 with no output if none.
superagent_pending_answer() {
  local f="${1:-}" a
  [[ -n "$f" ]] || return 1
  a="$({ superagent_pending_section "$f" \
        | sed -n 's/^[[:space:]]*answer:[[:space:]]*//p' | sed 's/[[:space:]]*$//' \
        | grep -v '^$' | head -1; } || true)"
  [[ -n "$a" ]] || return 1
  echo "$a"
}

# ---------------------------------------------------------------------------
# Operator notification — fired by the tick wrapper on a loop-status transition
# into WAITING FOR INPUT (a decision needs a human) or DONE. Unattended mode
# guarantees nobody is tailing the tick log, so this is the one signal the
# operator actually receives.
#   SUPER_NOTIFY_CMD  a shell snippet run via `bash -c` (e.g. a curl to ntfy.sh /
#                     Slack / Pushover) with SUPERAGENT_EVENT, SUPERAGENT_SLUG,
#                     LOOP_FILE, SUPERAGENT_TITLE, SUPERAGENT_BODY exported;
#   (unset/empty)     a desktop notification: osascript on macOS, notify-send on
#                     Linux, when available; otherwise log only.
# Never fails the caller (a broken notifier must not fail a healthy tick).
# ---------------------------------------------------------------------------
superagent_notify() {
  local event="${1:?event}" slug="${2:?slug}" loop="${3:?loop-file}" title body
  case "$event" in
    waiting-for-input)
      title="superagent: $slug needs a decision"
      body="$({ superagent_pending_section "$loop" | grep -v '^[[:space:]]*$' | head -3 \
                | tr '\n' ' ' | cut -c1-200; } || true)"
      [[ -n "$body" ]] || body="WAITING FOR INPUT: $loop"
      ;;
    done)
      title="superagent: $slug is DONE"; body="Loop reached DONE: $loop"
      ;;
    *)
      title="superagent: $slug $event"; body="$loop"
      ;;
  esac
  if [[ -n "${SUPER_NOTIFY_CMD:-}" ]]; then
    SUPERAGENT_EVENT="$event" SUPERAGENT_SLUG="$slug" LOOP_FILE="$loop" \
    SUPERAGENT_TITLE="$title" SUPERAGENT_BODY="$body" \
      bash -c "$SUPER_NOTIFY_CMD" || echo "superagent: SUPER_NOTIFY_CMD failed (rc=$?) for event=$event" >&2
  elif [[ "$(uname -s)" == Darwin ]] && command -v osascript >/dev/null 2>&1; then
    local t="${title//\"/}" b="${body//\"/}"; t="${t//\\/}"; b="${b//\\/}"
    osascript -e "display notification \"$b\" with title \"$t\"" >/dev/null 2>&1 || true
  elif command -v notify-send >/dev/null 2>&1; then
    notify-send "$title" "$body" >/dev/null 2>&1 || true
  fi
  echo "superagent: notified event=$event slug=$slug"
  return 0
}
