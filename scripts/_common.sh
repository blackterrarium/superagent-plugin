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
  # CLI dirs recorded at install time (install-timer.sh writes SUPERAGENT_CLI_PATH into the
  # per-goal env file, from superagent_cli_path_dirs below). A CLI installed under a Node
  # version manager (nvm/fnm/volta) lives outside the fixed dirs above — e.g.
  # ~/.nvm/versions/node/<v>/bin/pi — and the scheduler never has the operator's shell PATH,
  # so without this the tick dies with exit 127 before any session starts. Prepend each once.
  local d
  local IFS=':'
  for d in ${SUPERAGENT_CLI_PATH:-}; do
    [[ -n "$d" ]] || continue
    case ":$PATH:" in *":$d:"*) ;; *) export PATH="$d:$PATH" ;; esac
  done
}

# Dirs of every harness CLI resolvable in the CURRENT shell (claude, codex, agent/cursor-agent,
# pi), colon-joined and deduped, omitting the dirs _superagent_augment_path adds anyway and the
# system defaults — i.e. exactly what a detached tick could NOT find on its own. install-timer.sh
# records it as SUPERAGENT_CLI_PATH. Every CLI is recorded, not only the harness's, because a
# tick also spawns bridged roles that run foreign CLIs. The UNresolved `command -v` dir is
# deliberate: under nvm the binary is a symlink into lib/node_modules/…, and it is the symlink's
# bin/ dir that also holds `node`.
superagent_cli_path_dirs() {
  local c p d out=""
  for c in claude codex agent cursor-agent pi; do
    p="$(command -v "$c" 2>/dev/null)" || continue
    [[ "$p" == /* ]] || continue          # a function/alias, not a file
    d="$(dirname "$p")"
    case "$d" in "$HOME/.local/bin"|/opt/homebrew/bin|/usr/local/bin|/usr/bin|/bin|/usr/sbin|/sbin) continue ;; esac
    case ":$out:" in *":$d:"*) ;; *) out="${out:+$out:}$d" ;; esac
  done
  printf '%s\n' "$out"
}

# Fatal check: ensure the claude CLI binary is on PATH (after augmentation).
# Returns non-zero with a clear message so a missing binary fails LOUDLY instead
# of the cryptic `timeout: failed to run command` exit 127.
ensure_claude_bin() {
  _superagent_augment_path
  if ! command -v claude >/dev/null 2>&1; then
    echo "superagent: 'claude' not found on PATH (checked incl. ~/.local/bin, /opt/homebrew/bin, /usr/local/bin and SUPERAGENT_CLI_PATH). Install it or, if it lives under a Node version manager (nvm/fnm/volta), re-arm the loop (install-timer.sh / superagent-external) from a shell where it resolves so its directory is recorded as SUPERAGENT_CLI_PATH in the per-goal env file; aborting." >&2
    return 1
  fi
  return 0
}

# ---------------------------------------------------------------------------
# Harness dispatch — which agent CLI the external driver fires per tick.
#   SUPER_HARNESS=claude (default) -> the Claude CLI (`claude`)
#   SUPER_HARNESS=cursor           -> the Cursor CLI (`agent`, older `cursor-agent`)
#   SUPER_HARNESS=codex            -> the OpenAI Codex CLI (`codex`)
#   SUPER_HARNESS=pi               -> the Pi CLI (`pi`)
# Resolution: process env > <repo>/.superenv > plugin default (via load_superenv).
# ---------------------------------------------------------------------------

superagent_harness() {
  local h="${SUPER_HARNESS:-claude}"
  case "$h" in
    claude|cursor|codex|pi) echo "$h" ;;
    *) echo "superagent: bad SUPER_HARNESS '$h' (want claude|cursor|codex|pi)" >&2; return 1 ;;
  esac
}

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
    pi)     case "$e" in off|minimal|low|medium|high|xhigh|max) return 0 ;; esac ;;
  esac
  return 1
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
  echo "superagent: Cursor CLI not found on PATH (tried: agent, cursor-agent; checked incl. ~/.local/bin, /opt/homebrew/bin, /usr/local/bin and SUPERAGENT_CLI_PATH). Install it (curl https://cursor.com/install -fsS | bash) or, if it lives under a Node version manager (nvm/fnm/volta), re-arm the loop (install-timer.sh / superagent-external) from a shell where it resolves so its directory is recorded as SUPERAGENT_CLI_PATH in the per-goal env file; aborting." >&2
  return 1
}

# Fatal check: ensure the OpenAI Codex CLI binary (`codex`) is findable.
ensure_codex_bin() {
  _superagent_augment_path
  if ! command -v codex >/dev/null 2>&1; then
    echo "superagent: Codex CLI not found on PATH (tried: codex; checked incl. ~/.local/bin, /opt/homebrew/bin, /usr/local/bin and SUPERAGENT_CLI_PATH). Install it (npm install -g @openai/codex, or brew install codex) or, if it lives under a Node version manager (nvm/fnm/volta), re-arm the loop (install-timer.sh / superagent-external) from a shell where it resolves so its directory is recorded as SUPERAGENT_CLI_PATH in the per-goal env file; aborting." >&2
    return 1
  fi
  return 0
}

# Fatal check: the Pi CLI (`pi`) must be findable.
ensure_pi_bin() {
  _superagent_augment_path
  if ! command -v pi >/dev/null 2>&1; then
    echo "superagent: Pi CLI not found on PATH (tried: pi; checked incl. ~/.local/bin, /opt/homebrew/bin, /usr/local/bin and SUPERAGENT_CLI_PATH). Install it (npm install -g @earendil-works/pi-coding-agent) or, if it lives under a Node version manager (nvm/fnm/volta), re-arm the loop (install-timer.sh / superagent-external) from a shell where it resolves so its directory is recorded as SUPERAGENT_CLI_PATH in the per-goal env file; aborting." >&2
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
    pi)     ensure_pi_bin ;;
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
  # Which harness this repo runs on — process env first, else the repo's .superenv — resolved
  # BEFORE the Claude template is sourced (it would set SUPER_HARNESS=claude and shadow it).
  local harness="${SUPER_HARNESS:-}"
  if [[ -z "$harness" && -f "$repo/.superenv" ]]; then
    harness="$(sed -n 's/^SUPER_HARNESS=[[:space:]]*\([a-z]*\).*/\1/p' "$repo/.superenv" | tail -1)"
  fi
  local harness_dir=""
  case "$harness" in pi) harness_dir=pi ;; cursor) harness_dir=cursor ;; codex) harness_dir=codex/plugins/superagent ;; esac
  set -a
  [[ -f "$plugin_root/templates/superenv.default" ]] && . "$plugin_root/templates/superenv.default"
  # The harness build's own template layers over the Claude default, so a repo whose .superenv
  # says only SUPER_HARNESS=pi gets that harness's defaults (SUPER_MODEL_SUPERVISOR=inherit, …)
  # instead of claude:opus — which the pi tick refuses with exit 11. When the tick already runs
  # from a harness build (plugin_root IS pi/), the nested path does not exist and this is a no-op.
  [[ -n "$harness_dir" && -f "$plugin_root/$harness_dir/templates/superenv.default" ]] && . "$plugin_root/$harness_dir/templates/superenv.default"
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

# superagent_ci_runs <loop-file> — the GitHub Actions run ids recorded under the
# frontmatter's `ci_wait:` → `runs:` while the loop is WAITING FOR CI, as a
# space-separated list. Accepts the canonical inline form `runs: [1, 2]` and a
# `- id` list. Only the frontmatter is read; only the runs: entry inside the
# ci_wait: block is scanned (pr:/iteration: numbers never leak in). Empty
# output, rc 0 when there are none, the file is unreadable, or the arg is empty.
superagent_ci_runs() {
  local f="${1:-}"
  [[ -n "$f" ]] || return 0
  { awk '
      NR==1 && /^---/ { fm=1; next }
      fm && /^---/ { exit }
      !fm { next }
      /^ci_wait:/ { blk=1; next }
      blk && /^[^[:space:]]/ { blk=0 }
      !blk { next }
      /^[[:space:]]+runs:/ { inruns=1; sub(/^[[:space:]]+runs:/, ""); print; next }
      inruns && /^[[:space:]]+-/ { print; next }
      inruns { inruns=0 }
    ' "$f" 2>/dev/null | grep -oE '[0-9]{5,}' | tr '\n' ' ' | sed 's/ $//'; } || true
}

# superagent_ci_field <loop-file> <key> — the scalar value of `<key>:` INSIDE
# the frontmatter's `ci_wait:` block (e.g. `since`, `repo`), trimmed, with
# surrounding quotes removed. Same block scanning as superagent_ci_runs; a
# top-level key of the same name never matches. Empty output, rc 0 when absent.
superagent_ci_field() {
  local f="${1:-}" k="${2:-}"
  [[ -n "$f" && -n "$k" ]] || return 0
  { K="$k" awk '
      NR==1 && /^---/ { fm=1; next }
      fm && /^---/ { exit }
      !fm { next }
      /^ci_wait:/ { blk=1; next }
      blk && /^[^[:space:]]/ { blk=0 }
      !blk { next }
      { line=$0; sub(/^[[:space:]]+/, "", line) }
      index(line, ENVIRON["K"] ":") == 1 {
        v=substr(line, length(ENVIRON["K"])+2); sub(/[[:space:]]+#.*$/, "", v)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", v); gsub(/^["'"'"']|["'"'"']$/, "", v)
        print v; exit
      }
    ' "$f" 2>/dev/null; } || true
}

# superagent_epoch_from_iso <timestamp> — seconds since epoch for an ISO-8601
# UTC timestamp (`2026-08-28T00:00:00Z`, `2026-08-28 00:00:00`, or a bare date;
# a `+00:00` suffix is accepted). Portable across BSD (`date -j -f`) and GNU
# (`date -d`). Empty output, rc 0 when the value cannot be parsed.
superagent_epoch_from_iso() {
  local t="${1:-}" e=""
  [[ -n "$t" ]] || return 0
  t="${t%Z}"; t="${t%+00:00}"; t="${t/T/ }"
  [[ "$t" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] && t="$t 00:00:00"
  [[ "$t" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2}$ ]] || return 0
  if date --version >/dev/null 2>&1; then
    e="$(date -u -d "$t" +%s 2>/dev/null || true)"
  else
    e="$(date -u -j -f '%Y-%m-%d %H:%M:%S' "$t" +%s 2>/dev/null || true)"
  fi
  [[ "$e" =~ ^[0-9]+$ ]] && echo "$e"
  return 0
}

# superagent_lock_owner_state <lockdir> — liveness of the L3 overlap lock's
# recorded owner, one line:
#   alive <pid>   owner is a bare PID that is running (a real in-flight tick)
#   dead <pid>    owner is a bare PID that is gone (crashed tick — reapable)
#   malformed     owner file exists but is not a bare PID (only age-stealable)
#   none          no lock dir, or no/empty owner file
# Shared by answer.sh (reap-or-refuse) and superagent-tick.sh (peer-shield);
# never fails the caller.
superagent_lock_owner_state() {
  local d="${1:-}" o=""
  [[ -n "$d" && -d "$d" ]] || { echo none; return 0; }
  o="$(cat "$d/owner" 2>/dev/null || true)"
  if [[ -z "$o" ]]; then echo none
  elif [[ ! "$o" =~ ^[0-9]+$ ]]; then echo malformed
  elif kill -0 "$o" 2>/dev/null; then echo "alive $o"
  else echo "dead $o"
  fi
  return 0
}

# ---------------------------------------------------------------------------
# Operator notification — fired by the tick wrapper on a loop-status transition
# into WAITING FOR INPUT (a decision needs a human), DONE, or a stale CI wait. Unattended mode
# guarantees nobody is tailing the tick log, so this is the one signal the
# operator actually receives.
#   SUPER_NOTIFY_CMD  a shell snippet run via `bash -c` (e.g. a curl to ntfy.sh /
#                     Slack / Pushover) with SUPERAGENT_EVENT, SUPERAGENT_SLUG,
#                     LOOP_FILE, SUPERAGENT_TITLE, SUPERAGENT_BODY exported;
#   (unset/empty)     a desktop notification: osascript on macOS, notify-send on
#                     Linux, when available; otherwise log only.
# Never fails the caller (a broken notifier must not fail a healthy tick) — this
# includes malformed/empty args: `${1:?}` on an empty positional aborts the
# WHOLE calling script under set -e (not just this function), so args are
# defaulted with `${n:-}`, never required, and a missing/empty slug falls back
# to "unknown" rather than aborting.
# ---------------------------------------------------------------------------
superagent_notify() {
  local event="${1:-}" slug="${2:-}" loop="${3:-}" title body
  [[ -n "$slug" ]] || slug="unknown"
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
    ci-stale)
      title="superagent: $slug CI wait is stale"
      body="WAITING FOR CI since $(superagent_ci_field "$loop" since) exceeds SUPER_CI_MAX_WAIT_MIN; runs: $(superagent_ci_runs "$loop") — the gate now falls open to the session each interval"
      ;;
    *)
      title="superagent: $slug $event"; body="$loop"
      ;;
  esac
  # `notified` is the success record only: on a SUPER_NOTIFY_CMD failure the
  # "failed (rc=N)" line above is the record, and claiming both would tell the
  # operator a message went out that did not.
  local ok=true
  if [[ -n "${SUPER_NOTIFY_CMD:-}" ]]; then
    SUPERAGENT_EVENT="$event" SUPERAGENT_SLUG="$slug" LOOP_FILE="$loop" \
    SUPERAGENT_TITLE="$title" SUPERAGENT_BODY="$body" \
      bash -c "$SUPER_NOTIFY_CMD" \
      || { echo "superagent: SUPER_NOTIFY_CMD failed (rc=$?) for event=$event" >&2; ok=false; }
  elif [[ "$(uname -s)" == Darwin ]] && command -v osascript >/dev/null 2>&1; then
    local t="${title//\"/}" b="${body//\"/}"; t="${t//\\/}"; b="${b//\\/}"
    osascript -e "display notification \"$b\" with title \"$t\"" >/dev/null 2>&1 || true
  elif command -v notify-send >/dev/null 2>&1; then
    notify-send "$title" "$body" >/dev/null 2>&1 || true
  fi
  [[ "$ok" == true ]] && echo "superagent: notified event=$event slug=$slug"
  return 0
}

# superagent_kick_tick <slug> — fire ONE tick now (non-blocking) through the
# registered scheduler entry, instead of waiting out the interval. Used by
# launch.sh (first tick) and answer.sh (resume right after an answer). rc is
# the scheduler's: non-zero when the entry is not loaded/armed.
superagent_kick_tick() {
  local slug="${1:-}"; [[ -n "$slug" ]] || { echo "superagent: kick_tick needs a slug" >&2; return 1; }
  if [[ "$(superagent_scheduler)" == launchd ]]; then
    launchctl kickstart "$(superagent_launchd_domain)/$(superagent_launchd_label "$slug")"
  else
    systemctl --user start --no-block "superagent-tick@$slug.service"
  fi
}
