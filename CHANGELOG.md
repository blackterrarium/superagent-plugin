# Changelog

## 0.2.0 — 2026-08-11

launchd (macOS) support for the external driver: every lifecycle script auto-dispatches by OS
(systemd user timers on Linux, launchd LaunchAgents on Darwin), with a per-goal plist rendered
from `scripts/launchd/com.superagent.tick.plist.template` and the same `~/.config/superagent/<slug>.env`
registry on both schedulers. Auth fallbacks: the tick no longer hard-requires `ANTHROPIC_API_KEY`
(falls through to the claude CLI's stored login) and `GH_TOKEN` loading falls back to `gh auth token`
(OS-keyring hosts). Also fixes three latent `set -e`/`pipefail` crashes in `status.sh`/`_common.sh`
probe paths, and adds `/opt/homebrew/bin` to the scheduler-PATH augmentation.

Smoke-validated 2026-08-11 on macOS (external/launchd mode): install / idempotent re-install /
status / stop dry-run / graceful drain / force-stop with stale lock on a throwaway slug, plus an
end-to-end migration of a live loop off a hand-rolled plist. External (systemd) driver mode still
NOT smoke-tested on Linux.

## 0.1.0 — 2026-08-06

Initial extraction from network-compose at 5f234bae: 12 ported skills, external driver
scripts, `.superenv` config contract, new `superagent:init` bootstrap skill.

Smoke-validated 2026-08-06 on macOS (attended/cron mode): init idempotency, supergoal, full loop to
two-signal DONE in 4 ticks (superplan → superrun/SDD → exhaustion signals) on a no-remote
SUPER_PROTECTED_MAIN=false scratch repo; direct-commit and direct-merge landing paths exercised.
External (systemd) driver mode NOT yet smoke-tested — validate on a Linux host before first
unattended use.
