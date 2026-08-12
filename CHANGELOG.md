# Changelog

## 0.4.1 — 2026-08-12

- **Default tick interval 30m → 10m** in the `.superenv` default templates (canonical
  `templates/superenv.default` plus the generated Codex and Cursor copies). Script-level
  fallbacks when no `.superenv` is present (`launch.sh` / `install-timer.sh`) remain 30m.

## 0.4.0 — 2026-08-12

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
- **Smoke-validated** (runs 1–2, Linux, agent 2026.08.11): headless `agent -p`, `--plugin-dir`
  loading, plugin-root resolution and relative template reads, the file-read tick entry
  (hard gate fires), and superpowers availability under Cursor. Two facts encoded into the
  generated banner: skill names are unprefixed on Cursor, and `disable-model-invocation` skills
  are invisible to model-driven lookup (the tick's file-read entry is therefore mandatory there).
- **Harness-aware driver scripts.** `SUPER_HARNESS=claude|cursor` (new `.superenv` key, flipped to
  `cursor` in the generated template; `--harness` flag on `launch.sh`/`install-timer.sh`, pinned
  into the per-goal registry env) selects which CLI a tick fires: `claude -p …` as before, or
  `agent -p --trust --force --plugin-dir <repo>/cursor` with `CURSOR_API_KEY`/stored-login auth
  and Cursor model names (`inherit` → the CLI's `auto`). `_common.sh` gains
  `superagent_harness` / `ensure_cursor_bin` / `ensure_cli_bin`; `superagent-tick.sh` and
  `bootstrap.sh` branch per harness.
- **Known gap** (recorded in `cursor/README.md`): no end-to-end multi-tick loop run on Cursor yet.

Experimental Codex support (stage 1 — packaging + smoke test; **smoke-validated 8/8 on
2026-08-12**, codex CLI 0.147.0 on macOS: marketplace manifest moved to
`.agents/plugins/marketplace.json` with `source.source="local"` + `AVAILABLE`/`ON_INSTALL` policy
enums per the CLI's real schema; templates moved inside `plugins/superagent/` because
`codex plugin add` copies only `source.path` into the install cache; a root-level
`.agents/plugins/marketplace.json` now makes the repo itself installable as a marketplace;
`spawn_agent` confirmed available in plain `codex exec`; README reframed as a
Claude Code + Cursor + Codex plugin with per-harness install instructions),
plus per-role reasoning effort for every harness:

- **`SUPER_HARNESS=codex` driver.** `superagent-tick.sh` gains a third harness branch alongside
  `claude`/`cursor`: fires `codex exec <prompt>` per tick against the generated Codex
  plugin-marketplace build (skills load via the *installed* plugin — `codex plugin marketplace add
  <repo>/codex && codex plugin add superagent@superagent` — not `--plugin-dir`). Auth:
  `OPENAI_API_KEY` in the target repo's `.env`, else the CLI's own stored `codex login`.
  `_common.sh` gains `ensure_codex_bin`; `superagent_harness` now accepts `claude|cursor|codex`;
  `--harness codex` works on `launch.sh`/`install-timer.sh`.
- **`SUPER_CODEX_SANDBOX`.** New `.superenv` knob (codex harness only): `workspace-write` (default
  — `--sandbox workspace-write -c sandbox_workspace_write.network_access=true`) or
  `danger-full-access` (`--dangerously-bypass-approvals-and-sandbox`). An out-of-domain value now
  aborts the tick with a new exit code, 8, rather than silently picking a posture.
- **`SUPER_EFFORT_*` keys.** Ten new per-role reasoning-effort keys (mirroring the `SUPER_MODEL_*`
  role table) resolved the same three-layer way (env > `.superenv` > plugin default). Domain is
  harness-native: claude `low|medium|high|xhigh|max`, codex `none|minimal|low|medium|high|xhigh`
  (no `max`); the Cursor CLI has no effort control (any non-`inherit` value WARNs and falls back to
  `inherit`). Every shipped build defaults the four dispatch-only roles
  (supervisor/planner/executor/panel) to `inherit` and the SDD worker roles to a nonzero effort
  (`medium` implementer/fix-applier, `high` reviewers/fix-planner, `xhigh` branch-reviewer).
- **`--effort` on claude ticks.** `superagent-tick.sh` now passes `--effort <value>` to `claude -p`
  whenever `SUPER_EFFORT_SUPERVISOR` (or `TICK_EFFORT`) resolves non-`inherit`. The driver never
  sets `CLAUDE_CODE_EFFORT_LEVEL` itself (it outranks both `--effort` and per-role agent-definition
  effort pins) and warns if the scheduler environment already carries it.
- **`.superenv` validation pass.** `superagent:init` Step 2 now lints the resolved configuration
  (unknown `SUPER_*`/`TICK_*` keys, enum/boolean/numeric domains, and model/effort key domains per
  harness) and reports one WARN + effective-fallback row per finding — report-only, never rewrites
  the user's `.superenv`.
- **Codex build + smoke harness.** `scripts/build-codex-skills.sh` derives a generated Codex
  plugin-marketplace tree (`codex/`) from the canonical skills, reusing the Cursor build's
  conditional-marker mechanism plus a new `codex-only` marker (content inert as an HTML comment in
  the canonical files, activated only in this build); `--check` mode diffs a fresh rebuild against
  the committed tree and exits 1 if stale. `scripts/codex-smoke.sh` runs T1–T6 against a live Codex
  CLI (headless exec, marketplace + plugin install, skill enumeration, a generated
  `codex-smoke-probe` skill, `spawn_agent` availability, the real tick file-read entry + hard gate,
  and effort-flag pass-through), always exits 0, and writes `codex-smoke-report.md`.
- **Known gap** (recorded in `codex/README.md`): no end-to-end multi-tick loop run on Codex yet;
  `spawn_agent` availability in plain `codex exec` sessions is unverified (smoke T4b).

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
