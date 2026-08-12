# Codex harness support (`SUPER_HARNESS=codex`) — design

**Date:** 2026-08-12
**Status:** approved (user), pending implementation plan
**Scope decision:** per-loop harness selection now; per-role model mixing is a later,
separate goal — this design only leaves the seam for it.

## Goal

Let the external driver fire supervisor ticks through the OpenAI Codex CLI's headless
mode (`codex exec`) as a third harness beside `claude` and `cursor`, so different
loops on one host can run different models/CLIs concurrently. Follow the proven
Cursor port pattern end to end: harness dispatch in `scripts/_common.sh`, a harness
branch in `scripts/superagent-tick.sh`, and a generated skills build directory.

## Non-goals (YAGNI)

- Per-role model mixing within a tick (implementer on Codex while supervisor is on
  Claude, etc.). The seam is noted (§ Subagent mapping) but nothing is built.
- Per-tick harness alternation within one loop.
- An in-session (cron) driver on Codex — external driver only, like the Cursor build.
- Porting the superpowers plugin to Codex. `superrun`'s dependency on
  `subagent-driven-development` is a documented install prerequisite, not solved here.

## Codex CLI facts this design relies on

Verified against current Codex docs (context7, /openai/codex):

- Headless entry point: `codex exec [OPTIONS] [PROMPT]`. Approval policy is forced to
  `never` in headless mode; on server error or failed/interrupted turn the process
  exits 1, else 0.
- Flags: `-m/--model`, `-s/--sandbox <read-only|workspace-write|danger-full-access>`,
  `--dangerously-bypass-approvals-and-sandbox` (`--yolo`), `-C/--cd <dir>`,
  `--json` (JSONL event stream to stdout), `-o/--output-last-message <file>`,
  `-c key=value` config overrides (e.g. `sandbox_workspace_write.network_access=true`).
- Auth: stored ChatGPT login or API key (`OPENAI_API_KEY` / `codex login` with key).
- Skills: repo-scoped `.codex/skills/` / `.agents/skills/`, user-scoped
  `~/.agents/skills/`, or an installed **plugin** (marketplace machinery:
  `codex plugin marketplace add <root>` + `codex plugin add <name>@<marketplace>`);
  a plugin's `skills/` subdirectory is discovered automatically. There is no
  per-invocation `--plugin-dir` analog.
- Subagents: in-process `spawn_agent` tool (multi-agent v2) with per-spawn
  `model`, `agent_type`, `reasoning_effort` overrides. Availability inside plain
  `codex exec` sessions may be feature-gated — a smoke-test assertion, not an
  assumption.

## 1. Architecture

`codex` becomes a third value of `SUPER_HARNESS`, resolved through the existing
three-layer precedence (process env > repo `.superenv` > plugin default). Only the
supervisor tick's CLI changes per loop; all loop state stays in the gitignored
loop-status file, so ticks remain stateless and Claude-, Cursor- and Codex-driven
loops coexist on one host.

Per-role seam for later: Codex's `spawn_agent` takes a per-spawn `model` override,
so the `SUPER_MODEL_*` role keys have a natural mapping target when per-role mixing
is designed.

## 2. Driver changes (`scripts/`)

### `_common.sh`

- `superagent_harness()`: accept `codex` (error message becomes
  `want claude|cursor|codex`).
- New `ensure_codex_bin()`: after `_superagent_augment_path`, require `codex` on
  PATH; fail loud with an install hint. No legacy binary names.
- `ensure_cli_bin()`: dispatch `codex` → `ensure_codex_bin`.

### `superagent-tick.sh`

New `codex` branch, parallel to the `cursor` branch:

- `SKILLS_ROOT=$PLUGIN_ROOT/codex`; fail loud (exit 7) if
  `$SKILLS_ROOT/plugins/superagent/skills/superagent/SKILL.md` is missing
  ("run scripts/build-codex-skills.sh").
- Model: `TICK_MODEL > SUPER_MODEL_SUPERVISOR`; values are Codex model names;
  `inherit` → empty → omit `-m` (the CLI's configured default applies).
- Prompt: same file-read entry point (read the supervisor SKILL.md path, execute
  exactly ONE --tick, unattended wording: never ask the user; on a needed decision
  write `## Pending decision`, set WAITING FOR INPUT, exit). Codex phrasing —
  no AskUserQuestion tool exists there.
- Sandbox from `SUPER_CODEX_SANDBOX` (default `workspace-write`):
  - `workspace-write` → `--sandbox workspace-write -c sandbox_workspace_write.network_access=true`
  - `danger-full-access` → `--dangerously-bypass-approvals-and-sandbox`
  - anything else → fail loud.
- Invocation, from `cd "$REPO"` under the existing optional `timeout` wrapper:
  - stream (default): `codex exec "$PROMPT" [sandbox flags] [-m MODEL] --json`
  - text: same without `--json`.
  Output appended to `$LOG_FILE`, exit code propagated — identical logging framing
  to the other harnesses.
- Auth: if `OPENAI_API_KEY` is unset after sourcing `$REPO/.env`, log the
  "relying on the CLI's stored login" note (warn, don't abort), matching the
  cursor/claude branches.
- The `gh` preflight (`ensure_gh_auth` + exported `GH_TOKEN`) is unchanged and
  runs for all harnesses.

### `launch.sh` / `install-timer.sh`

Accept `--harness codex` wherever `claude|cursor` is validated today; the value
flows into the scheduler unit environment exactly like `cursor` does.

Other lifecycle scripts (`status.sh`, `stop.sh`, `force-stop.sh`,
`uninstall-timer.sh`) are scheduler-facing and harness-agnostic; audit for
hardcoded harness validation during implementation, expected no-op.

## 3. Codex build (`scripts/build-codex-skills.sh` → `codex/`)

Generated from the canonical skills, committed to the repo, regenerated after any
canonical edit — the Cursor pattern. Laid out as a Codex **marketplace root** so
install is:

```
codex plugin marketplace add <plugin-repo>/codex
codex plugin add superagent@superagent
```

The marketplace's `name` field is `superagent` (so the qualified install spec is
`superagent@superagent`); if validation forbids the collision, fall back to
`superagent-marketplace` and record the change in `codex/README.md`.

Layout:

```
codex/marketplace.json                              marketplace index; source.path ./plugins/superagent
codex/plugins/superagent/.codex-plugin/plugin.json  plugin manifest
codex/plugins/superagent/skills/<name>/SKILL.md     filtered + substituted skills
codex/templates/superenv.default                    specialized: SUPER_HARNESS=codex, codex model names
codex/README.md                                     install notes + validated/known-gaps sections
```

- Marker system reused from the cursor build: `cc-only` blocks/lines dropped; new
  `codex-only:start` / `codex-only:end` activation markers in canonical skills
  (inert HTML comments there, activated here). The cursor build script must also
  learn to DROP `codex-only` blocks (and this script drops `cursor-only` blocks) —
  each build strips the other harness's markers.
- Substitutions (extend as discovered during implementation):
  `claude -p` → `codex exec`, `claude --model` → `codex exec -m`,
  `ANTHROPIC_API_KEY` → `OPENAI_API_KEY`, `${CLAUDE_PLUGIN_ROOT}` →
  `${SUPER_PLUGIN_ROOT}`, `Claude CLI` → `Codex CLI`, driver line → external-only,
  cron_id line → unused.
- Generated banner after each SKILL.md frontmatter, with the tool mapping:
  - "Agent tool / spawn a subagent" → `spawn_agent` (multi-agent v2); wait for the
    child's result.
  - "Skill tool / invoke skill X" → reference the skill by name in the message
    (`$skill-name` mention); names are plugin-scoped — verify actual naming in the
    smoke run (the Cursor port found names unprefixed; Codex may differ).
  - `CronCreate`/`CronList`/`CronDelete`/`Monitor` → do not exist; never attempt.
- `--check` mode: rebuild to a temp dir and diff against `codex/`, exit 1 if stale
  (CI / pre-release guard) — same contract as `build-cursor-skills.sh --check`.

### Subagent mapping (and the per-role seam)

Skills that dispatch subagents (superrun's SDD roles, the L7 panel) map to
`spawn_agent` calls. For now the role model keys resolve exactly as on the other
harnesses (values must be Codex model names when the harness is codex; `inherit`
= don't override the child's model). No new routing logic — but this is the seam
where per-role Claude/Codex mixing would later plug in.

## 4. Config & docs

- `templates/superenv.default`:
  - `SUPER_HARNESS` comment: `claude | cursor | codex`.
  - New key: `SUPER_CODEX_SANDBOX=workspace-write`
    (`workspace-write | danger-full-access`; ignored by other harnesses).
- `codex/templates/superenv.default` (generated): `SUPER_HARNESS=codex`, model-key
  comment says Codex model names, includes `SUPER_CODEX_SANDBOX`.
- `README.md`: codex harness section (install, auth, sandbox knob).
- `CHANGELOG.md` entry.

## 5. Verification

`scripts/codex-smoke.sh`, mirroring `cursor-smoke.sh` (neutral workspace, probe
skill, numbered T-assertions):

- T1: `codex exec` headless print works at all (trivial prompt, exit 0).
- T2: after marketplace install, plugin skills are enumerable from a headless
  session in a neutral workspace; record the actual skill names (prefixed or not).
- T3: a skill can resolve the plugin root and read a bundled template by relative
  path (the `SUPER_PLUGIN_ROOT` question).
- T4: `spawn_agent` is available in a plain `codex exec` session (or record the
  feature flag needed to enable it).
- T5: one real tick fires end-to-end on a throwaway loop file via
  `superagent-tick.sh` with `SUPER_HARNESS=codex` (tick-style assertion, as in the
  cursor smoke v2).

Failure of T2 or T4 is a design-input change (skill delivery or subagent mapping
would need rework) — stop and reassess rather than patch around it.

Known gap to carry in `codex/README.md` until exercised: no end-to-end multi-tick
loop driven to DONE on Codex (same caveat the Cursor build carries).

## Error handling summary

- Unknown `SUPER_HARNESS` / `SUPER_CODEX_SANDBOX` value: fail loud before invoking
  anything (exit 6 / new distinct message).
- Missing `codex` binary: exit 5 via `ensure_cli_bin` with install hint.
- Missing codex build: exit 7 with "run scripts/build-codex-skills.sh".
- `codex exec` failures surface as nonzero tick exit (Codex exits 1 on
  failed/interrupted turns), logged in the driver log with the standard framing.
