#!/usr/bin/env bash
# build-cursor-skills.sh — generate the Cursor build of the superagent plugin into cursor/.
#
# The canonical skills under skills/ are the single source of truth. This script derives the
# Cursor variant (external driver only; Claude Code-specific tooling stripped) from conditional
# markers embedded in the canonical SKILL.md files:
#
#   <!-- cc-only:start --> ... <!-- cc-only:end -->    block kept in the Claude Code build,
#                                                      DROPPED here (marker lines too)
#   <some line> <!-- cc-only -->                       single line DROPPED here
#   <!-- cursor-only:start                             block is an inert HTML comment in the
#     ...content...                                    canonical file; here the wrapper lines are
#   cursor-only:end -->                                dropped and the content is ACTIVATED
#   <!-- codex-only:start --> ... <!-- codex-only:end --> block kept in the Codex build, DROPPED
#                                                      here (wrapper AND content, like cc-only)
#
# After marker filtering, harness-specific text substitutions are applied (see seds below), and a
# generated-file banner is inserted after each SKILL.md's frontmatter.
#
# Output layout (committed to the repo; re-run this script after editing skills/):
#   cursor/.cursor-plugin/plugin.json   Cursor plugin manifest
#   cursor/skills/<name>/SKILL.md       stripped + substituted skills
#   cursor/skills/cursor-smoke-probe/   smoke-test probe skill (generated here, no canonical copy)
#   cursor/templates/                   templates (superenv.default specialized for Cursor)
#   cursor/README.md                    install notes + known gaps
#
# Usage:
#   scripts/build-cursor-skills.sh           rebuild cursor/ in place
#   scripts/build-cursor-skills.sh --check   rebuild to a temp dir and diff against cursor/
#                                            (exit 1 if stale — for CI / pre-release)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/cursor"
CHECK=false
[ "${1:-}" = "--check" ] && CHECK=true

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
TMP="$WORK/out"
mkdir -p "$TMP"

# ── Marker filter ────────────────────────────────────────────────────────────
filter_markers() {
  awk '
    /<!-- cc-only:start -->/  { drop=1; next }
    /<!-- cc-only:end -->/    { drop=0; next }
    drop                      { next }
    /<!-- cc-only -->/        { next }
    /^[[:space:]]*<!-- codex-only:start[[:space:]]*$/ { cdrop=1; next }
    /^[[:space:]]*codex-only:end -->[[:space:]]*$/    { cdrop=0; next }
    cdrop                     { next }
    /^[[:space:]]*<!-- cursor-only:start[[:space:]]*$/ { next }
    /^[[:space:]]*cursor-only:end -->[[:space:]]*$/    { next }
    { print }
  '
}

# ── Harness substitutions ────────────────────────────────────────────────────
substitute() {
  sed \
    -e 's/\${CLAUDE_PLUGIN_ROOT}/\${SUPER_PLUGIN_ROOT}/g' \
    -e 's|\.claude/agents/|.cursor/agents/|g' \
    -e 's|`\.claude/`|`.cursor/`|g' \
    -e 's/claude -p/agent -p/g' \
    -e 's/claude --model/agent --model/g' \
    -e '/OPENAI_API_KEY` \/ `ANTHROPIC_API_KEY/!s/ANTHROPIC_API_KEY/CURSOR_API_KEY/g' \
    -e 's/Claude CLI/Cursor CLI/g' \
    -e 's/^driver: cron  .*/driver: external                  # the only driver in this build (external scheduler — fresh context per tick)/' \
    -e 's/^cron_id:  .*# CronCreate job id.*/cron_id:                          # unused in this build (Claude Code in-session driver only); leave empty/'
}

# ── Banner (inserted after the SKILL.md frontmatter) ─────────────────────────
banner_file="$WORK/banner"
cat >"$banner_file" <<'EOF'

<!-- GENERATED FILE — Cursor build. Do not edit by hand: edit the canonical skill under skills/
     in the plugin repository and re-run scripts/build-cursor-skills.sh. -->

> **Cursor build notes.**
> - Only the **external** driver exists in this build. Claude Code's in-session cron driver and its
>   `CronCreate` / `CronList` / `CronDelete` and `Monitor` tools do **not** exist on Cursor — treat
>   any residual mention of them as inapplicable and NEVER attempt those tool calls.
> - Tool mapping: "Agent tool" = spawn a subagent (synchronously — wait for its result). "Skill
>   tool" = invoke a skill. `AskUserQuestion` / `AskQuestion` = ask the user in chat (attended
>   sessions only — never in a headless tick). `EnterWorktree` = not available; where a skill
>   manages worktrees, use `git worktree` via shell. "Desktop routine" = a Claude Desktop feature,
>   not available — use an OS scheduler. A role whose `.superenv` value names another harness
>   (`codex:gpt-5.6-sol`, `pi:openai/gpt-5`, …) is BRIDGED: dispatch it with
>   `subagent_type: super-<role>` — the relay definition `superagent:init` generates — and treat a
>   reply beginning `BRIDGE-FAILED` as a failed subagent.
> - `${SUPER_PLUGIN_ROOT}` in commands and paths = this plugin's installed root directory (the one
>   containing `skills/` and `templates/`, two levels above this SKILL.md). Substitute its absolute
>   path wherever it appears.
> - Skill names are **unprefixed** on Cursor: `superagent:superplan` means the `superplan` skill
>   from this plugin, `superpowers:subagent-driven-development` means `subagent-driven-development`,
>   and so on — strip the `<plugin>:` prefix when looking a skill up. The `superagent` supervisor
>   skill itself carries `disable-model-invocation` and is invisible to model-driven skill lookup —
>   it is driven by reading its SKILL.md directly (the external tick's file-read prompt), never
>   invoked by name.
EOF

insert_banner() {
  # Insert the banner after the 2nd '---' line (end of YAML frontmatter).
  local src="$1"
  local fmline
  fmline="$(awk '/^---$/{c++; if(c==2){print NR; exit}}' "$src")"
  if [ -z "$fmline" ]; then
    cat "$src"
    return
  fi
  head -n "$fmline" "$src"
  cat "$banner_file"
  tail -n +"$((fmline + 1))" "$src"
}

# ── Skills ───────────────────────────────────────────────────────────────────
for dir in "$ROOT"/skills/*/; do
  name="$(basename "$dir")"
  mkdir -p "$TMP/skills/$name"
  filter_markers <"$dir/SKILL.md" | substitute >"$WORK/pre"
  insert_banner "$WORK/pre" >"$TMP/skills/$name/SKILL.md"
done

# ── Smoke-probe skill (generated only; no canonical counterpart) ─────────────
mkdir -p "$TMP/skills/cursor-smoke-probe"
cat >"$TMP/skills/cursor-smoke-probe/SKILL.md" <<'EOF'
---
name: cursor-smoke-probe
description: Use when asked to run the cursor smoke probe (or "superagent cursor probe") — verifies the Cursor build of the superagent plugin is loaded and reports environment facts for the port smoke test.
---

# Cursor smoke probe

Perform these checks with your file/shell tools, then output ONLY the report block below —
no extra prose before or after it.

1. Determine this skill file's own location and derive `plugin_root` = the directory two levels
   above it (the directory containing `skills/` and `templates/`). If you cannot determine the
   file's location, report `unknown`.
2. Check whether `<plugin_root>/templates/superenv.default` is readable; capture its first line.
3. Check `<plugin_root>/skills/superloop/SKILL.md`: does it exist; does it contain the string
   "GENERATED FILE — Cursor build" (a correct Cursor build MUST); does it contain the string
   "cc-only" (a correct Cursor build must NOT — that would be marker leakage from the build).
4. Report the CLAUDE_PLUGIN_ROOT environment variable: `echo "${CLAUDE_PLUGIN_ROOT:-unset}"`.
5. Check whether `<plugin_root>/scripts/role-bridge.sh` exists and is executable.

Report block (fill every value):

    PROBE-BEGIN
    plugin_root: <absolute path, or unknown>
    superenv_default_readable: <yes|no>
    superenv_first_line: <the line, or n/a>
    superloop_skill_present: <yes|no>
    superloop_has_cursor_banner: <yes|no>
    superloop_marker_leakage: <yes|no>
    env_claude_plugin_root: <value, or unset>
    role_bridge_present: <yes|no>
    PROBE-END
EOF

# ── Templates ────────────────────────────────────────────────────────────────
mkdir -p "$TMP/templates"
cp "$ROOT/templates/super-role-agent.md" "$TMP/templates/"
cp "$ROOT/templates/super-role-bridge-agent.md" "$TMP/templates/"
cp "$ROOT/templates/relay-preamble.md" "$TMP/templates/"
cp "$ROOT/templates/vault-root.md" "$TMP/templates/"
mkdir -p "$TMP/scripts"
cp "$ROOT/scripts/role-bridge.sh" "$TMP/scripts/"
chmod +x "$TMP/scripts/role-bridge.sh"

# superenv.default: same seds as skills, then Cursor-specific header + model defaults.
substitute <"$ROOT/templates/superenv.default" | awk '
  # Replace the Claude model-values header block (lines from "# Model values:" through the
  # "(SUPER_MODEL_SUPERVISOR ..." comment line) with the Cursor wording.
  /^# Model values:/ { inhdr=1
    print "# Model values: \"inherit\", or [<harness>:]<model> where <harness> is claude | codex | cursor | pi"
    print "# and <model> is that harness'"'"'s native model string — cursor: `agent --list-models`; claude: a"
    print "# tier (sonnet|opus|haiku|fable) or full ID (claude-fable-5); codex: a Codex model (gpt-5.6-sol);"
    print "# pi: <provider>/<model> (openai/gpt-5, anthropic/claude-opus-5). The prefix is optional when the"
    print "# model is recognizable (tiers/claude-* → claude, gpt-*/o<n>/codex* → codex, a \"/\" → pi)."
    print "# A role whose harness differs from SUPER_HARNESS is BRIDGED: dispatched through the same"
    print "# per-role subagent hook, executed by that harness'"'"'s CLI via scripts/role-bridge.sh (the CLI must"
    print "# be installed and logged in). SUPER_MODEL_SUPERVISOR must be native to SUPER_HARNESS."
    print "# On Cursor a non-inherit or bridged value on any role key except SUPER_MODEL_SUPERVISOR needs"
    print "# the per-role agent definition in .cursor/agents/ — re-run superagent:init after setting one."
    print "# (SUPER_MODEL_SUPERVISOR must be native to SUPER_HARNESS; the tick refuses a foreign one.)"
    next }
  inhdr && /^# \(SUPER_MODEL_SUPERVISOR/ { inhdr=0; next }
  inhdr && /^#/ { next }
  { inhdr=0 }
  # Replace the Reasoning-effort header block (from "# ── Reasoning effort per agent role"
  # through the "# NOTE (claude): ... leave it unset in scheduler environments." continuation
  # line) with the Cursor wording.
  /^# ── Reasoning effort per agent role/ { inefh=1
    print "# ── Reasoning effort per agent role (NOT SUPPORTED on Cursor) ─────"
    print "# The Cursor CLI has no reasoning-effort control. Keys are kept for cross-harness"
    print "# .superenv portability; any non-inherit value is warned and treated as inherit."
    next }
  inefh && /^# NOTE \(claude\):/ { inefh=2; next }
  inefh==2 && /^#/ { inefh=0; next }
  inefh==1 && /^#/ { next }
  { inefh=0 }
  { print }
' | sed \
  -e 's/^SUPER_MODEL_SUPERVISOR=opus/SUPER_MODEL_SUPERVISOR=inherit/' \
  -e 's/^SUPER_MODEL_PLANNER=opus/SUPER_MODEL_PLANNER=inherit/' \
  -e 's/^SUPER_MODEL_EXECUTOR=opus/SUPER_MODEL_EXECUTOR=inherit/' \
  -e 's/^SUPER_MODEL_PANEL=opus/SUPER_MODEL_PANEL=inherit/' \
  -e 's/^SUPER_MODEL_IMPLEMENTER=sonnet/SUPER_MODEL_IMPLEMENTER=inherit/' \
  -e 's/^SUPER_MODEL_FIX_APPLIER=sonnet/SUPER_MODEL_FIX_APPLIER=inherit/' \
  -e 's/^SUPER_MODEL_TASK_REVIEWER=opus/SUPER_MODEL_TASK_REVIEWER=inherit/' \
  -e 's/^SUPER_MODEL_RE_REVIEWER=opus/SUPER_MODEL_RE_REVIEWER=inherit/' \
  -e 's/^SUPER_MODEL_BRANCH_REVIEWER=opus/SUPER_MODEL_BRANCH_REVIEWER=inherit/' \
  -e 's/^SUPER_MODEL_FIX_PLANNER=opus/SUPER_MODEL_FIX_PLANNER=inherit/' \
  -e 's/^SUPER_HARNESS=claude\([[:space:]]*\)#.*/SUPER_HARNESS=cursor\1# this is the Cursor build — the external driver fires the Cursor CLI (`agent`)/' \
  -e 's/^SUPER_EFFORT_SUPERVISOR=medium/SUPER_EFFORT_SUPERVISOR=inherit/' \
  -e 's/^SUPER_EFFORT_PLANNER=high/SUPER_EFFORT_PLANNER=inherit/' \
  -e 's/^SUPER_EFFORT_EXECUTOR=medium/SUPER_EFFORT_EXECUTOR=inherit/' \
  -e 's/^SUPER_EFFORT_PANEL=xhigh/SUPER_EFFORT_PANEL=inherit/' \
  -e 's/^SUPER_EFFORT_IMPLEMENTER=medium/SUPER_EFFORT_IMPLEMENTER=inherit/' \
  -e 's/^SUPER_EFFORT_FIX_APPLIER=medium/SUPER_EFFORT_FIX_APPLIER=inherit/' \
  -e 's/^SUPER_EFFORT_TASK_REVIEWER=high/SUPER_EFFORT_TASK_REVIEWER=inherit/' \
  -e 's/^SUPER_EFFORT_RE_REVIEWER=high/SUPER_EFFORT_RE_REVIEWER=inherit/' \
  -e 's/^SUPER_EFFORT_BRANCH_REVIEWER=xhigh/SUPER_EFFORT_BRANCH_REVIEWER=inherit/' \
  -e 's/^SUPER_EFFORT_FIX_PLANNER=high/SUPER_EFFORT_FIX_PLANNER=inherit/' \
  -e '/^SUPER_CODEX_SANDBOX=/d' \
  -e 's/^SUPER_BRIDGE_RELAY_MODEL=haiku\([[:space:]]*\)#.*/SUPER_BRIDGE_RELAY_MODEL=inherit\1# relay subagent model for BRIDGED roles; inherit = the CLI default subagent model/' \
  >"$TMP/templates/superenv.default"

# ── Manifest ─────────────────────────────────────────────────────────────────
version="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$ROOT/.claude-plugin/plugin.json" | head -1)"
mkdir -p "$TMP/.cursor-plugin"
cat >"$TMP/.cursor-plugin/plugin.json" <<EOF
{
  "name": "superagent",
  "description": "Plan-tree authoring (supergoal/superplan) and autonomy-loop execution (superagent/superrun) skills — Cursor build (external unattended driver only)",
  "version": "${version}",
  "author": { "name": "Eugene Chai", "email": "eugene.chai@gmail.com" },
  "repository": "https://github.com/blackterrarium/superagent-plugin",
  "keywords": ["planning", "autonomy-loop", "subagents", "workflows"]
}
EOF

# ── README ───────────────────────────────────────────────────────────────────
cat >"$TMP/README.md" <<'EOF'
# superagent — Cursor build (GENERATED)

Everything in this directory is generated by `scripts/build-cursor-skills.sh` from the canonical
Claude Code skills at the repository root. **Do not edit by hand** — edit the canonical skill and
re-run the build.

This build differs from the Claude Code plugin:

- **External driver only.** The in-session `cron` driver (Claude Code `CronCreate`/`Monitor`
  tooling) is stripped; loops run via an OS scheduler firing fresh headless `agent -p` sessions.
- **`WAITING FOR INPUT` is always answered via the loop file** (`answer: <option>`), or in chat in
  an attended session.
- **Model keys** (`SUPER_MODEL_*` in `.superenv`) take `[<harness>:]<model>` — a Cursor model name
  (`agent --list-models`) or `inherit` natively; a value naming another harness (`claude:sonnet`,
  `codex:gpt-5.6-sol`, …) is valid too but BRIDGED — dispatched through a relay that runs the
  shipped `scripts/role-bridge.sh`.
- **Ships the bridge.** This package includes `scripts/role-bridge.sh` and the two relay templates
  (`templates/super-role-bridge-agent.md`, `templates/relay-preamble.md`); `SUPER_BRIDGE_RELAY_MODEL`
  (default `inherit`) sets the relay subagent's model.

Install (local): `agent --plugin-dir <repo>/cursor …` — or add the repository as a Cursor
marketplace (the root `.cursor-plugin/marketplace.json` points at this directory).

## Validated (smoke runs 1–2, 2026-08-12, agent 2026.08.11 on Linux)

- Headless print mode (`agent -p`) and `--plugin-dir` loading work; plugin skills are enumerable
  and invocable from a neutral workspace; skills can resolve the plugin root and read bundled
  templates by relative path.
- Skill names are **unprefixed** on Cursor (`superplan`, not `superagent:superplan`) — the
  generated banner maps this. `disable-model-invocation` skills (the `superagent` supervisor) are
  invisible to model-driven lookup, which is fine: the external tick drives it by a file-read
  prompt, never by name.
- The superpowers plugin's skills load under Cursor (unprefixed, e.g.
  `subagent-driven-development`) on a host with it configured — `superrun`'s dependency resolves.

## Driving a loop with the Cursor CLI

The external-driver scripts are harness-aware: `SUPER_HARNESS=cursor` (in the environment, the
target repo's `.superenv` — this build's `templates/superenv.default` already sets it — or
`--harness cursor` on `launch.sh` / `install-timer.sh`) makes every tick fire the Cursor CLI
(`agent -p --trust --force --plugin-dir <repo>/cursor`) instead of `claude -p`. Auth: the CLI's
stored login, or `CURSOR_API_KEY` in the target repo's `.env`. Model: `SUPER_MODEL_SUPERVISOR`
(a Cursor model name; `inherit` = the CLI's `auto`).

## Known gaps

- No end-to-end loop run (a real goal driven to DONE by a scheduler) has been exercised on
  Cursor yet — the tick invocation itself is smoke-validated (T5), the full multi-tick loop is
  not.
EOF

# ── Post-generation sanity checks ─────────────────────────────────────────────
grep -q 'OPENAI_API_KEY` / `ANTHROPIC_API_KEY' "$TMP/skills/init/SKILL.md" \
  || { echo "build-cursor-skills: pi-auth carve-out no longer matches — fix the sed address" >&2; exit 1; }
[ -x "$TMP/scripts/role-bridge.sh" ] \
  || { echo "build-cursor-skills: role-bridge.sh not executable" >&2; exit 1; }

# ── Emit or check ────────────────────────────────────────────────────────────
if $CHECK; then
  if [ ! -d "$OUT" ]; then
    echo "build-cursor-skills: --check: $OUT does not exist (run the build first)" >&2
    exit 1
  fi
  if diff -r "$TMP" "$OUT" >/dev/null 2>&1; then
    echo "build-cursor-skills: cursor/ is up to date"
  else
    echo "build-cursor-skills: cursor/ is STALE — re-run scripts/build-cursor-skills.sh:" >&2
    diff -r "$TMP" "$OUT" >&2 || true
    exit 1
  fi
else
  rm -rf "$OUT"
  mkdir -p "$OUT"
  cp -R "$TMP"/. "$OUT"/
  
  echo "build-cursor-skills: wrote $OUT"
fi
