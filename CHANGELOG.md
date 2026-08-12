# Changelog

## Unreleased

Experimental Cursor support (stage 1 — packaging + smoke test; not yet validated on a Cursor host):

- **Build-time strip.** Canonical skills now carry conditional markers (`cc-only` blocks/lines
  dropped in the Cursor build; `cursor-only` blocks HTML-commented in the canonical files and
  activated by the build). `scripts/build-cursor-skills.sh` derives the committed `cursor/` package
  from them: external driver only (in-session cron driver, `CronCreate`/`Monitor`/`AskUserQuestion`
  machinery stripped; superloop L4 and superagent Step 0.5 become documented no-ops), harness
  substitutions (`${CLAUDE_PLUGIN_ROOT}` → `${SUPER_PLUGIN_ROOT}`, `.claude/agents/` →
  `.cursor/agents/`, `claude -p` → `agent -p`, `ANTHROPIC_API_KEY` → `CURSOR_API_KEY`), a
  generated-file banner with tool-mapping notes on every skill, and a Cursor-specialized
  `superenv.default` (model values = Cursor model names or `inherit`). `--check` mode diffs the
  committed tree for CI/pre-release staleness.
- **Packaging.** Root `.cursor-plugin/marketplace.json` points at the self-contained `cursor/`
  plugin directory (own `.cursor-plugin/plugin.json`); also loadable via `agent --plugin-dir`.
- **Harness guard.** `superagent:init` now opens with a belt-and-suspenders harness check in both
  builds (wrong-build detection via `CLAUDE_PLUGIN_ROOT`; warns against double-loading through
  Cursor's third-party compat setting).
- **Smoke test.** `scripts/cursor-smoke.sh` (run on a machine with the Cursor CLI) exercises
  headless print mode, model listing, plugin skill discovery, a generated `cursor-smoke-probe`
  skill (plugin-root/relative-path resolution, strip verification), and the `superagent` hard gate —
  writing everything to `cursor-smoke-report.md` for reporting back.
- **Known gaps** (recorded in `cursor/README.md`): the external-driver shell scripts still invoke
  the Claude CLI; superpowers-under-Cursor is unverified (`superrun` needs it); headless skill
  invocation semantics under `agent -p` are what the smoke test exists to verify.

## 0.3.0 — 2026-08-11

`SUPER_MODEL_*` keys now accept full model IDs (`claude-<family>-<version>`, e.g. `claude-fable-5`;
no date stamp needed) alongside the tier names and `inherit`. The Agent tool's `model:` parameter is
tier-enum-only (verified empirically on this build — a full ID fails schema validation), so for the
nine subagent role keys the pin rides a per-role agent definition (`.claude/agents/super-<role>.md`,
`model:` frontmatter — verified to accept undated full IDs via a headless smoke test) that a new
`superagent:init` Step 3 generates, refreshes, and removes as derived artifacts. Dispatch rules
updated in `superagent` (canonical **Model resolution** block under Subagent dispatch), `superrun`
(SDD model policy), and `superloop` (L7 panel). `SUPER_MODEL_SUPERVISOR` needs no definition — the
tick already passes it verbatim to `claude --model`.

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
