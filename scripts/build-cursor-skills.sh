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
    -e 's/ANTHROPIC_API_KEY/CURSOR_API_KEY/g' \
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
>   not available — use an OS scheduler.
> - `${SUPER_PLUGIN_ROOT}` in commands and paths = this plugin's installed root directory (the one
>   containing `skills/` and `templates/`, two levels above this SKILL.md). Substitute its absolute
>   path wherever it appears.
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
3. Check whether `<plugin_root>/skills/superloop/SKILL.md` exists, and whether that file contains
   the string "CronCreate" (a correct Cursor build must NOT contain it; this probe file does not
   count).
4. Report the CLAUDE_PLUGIN_ROOT environment variable: `echo "${CLAUDE_PLUGIN_ROOT:-unset}"`.

Report block (fill every value):

    PROBE-BEGIN
    plugin_root: <absolute path, or unknown>
    superenv_default_readable: <yes|no>
    superenv_first_line: <the line, or n/a>
    superloop_skill_present: <yes|no>
    superloop_contains_croncreate: <yes|no>
    env_claude_plugin_root: <value, or unset>
    PROBE-END
EOF

# ── Templates ────────────────────────────────────────────────────────────────
mkdir -p "$TMP/templates"
cp "$ROOT/templates/super-role-agent.md" "$TMP/templates/"
cp "$ROOT/templates/vault-root.md" "$TMP/templates/"

# superenv.default: same seds as skills, then Cursor-specific header + model defaults.
substitute <"$ROOT/templates/superenv.default" | awk '
  # Replace the Claude model-values header block (lines from "# Model values:" through the
  # "(SUPER_MODEL_SUPERVISOR ..." comment line) with the Cursor wording.
  /^# Model values:/ { inhdr=1
    print "# Model values (Cursor build): a Cursor model name (see `agent --list-models`) or"
    print "# \"inherit\". \"inherit\" = omit the model override; the subagent runs on the session"
    print "# model. Any non-inherit value needs the per-role agent definition in .cursor/agents/"
    print "# — re-run superagent:init after changing one."
    print "# (SUPER_MODEL_SUPERVISOR goes straight to `agent --model`, which takes any listed name.)"
    next }
  inhdr && /^# \(SUPER_MODEL_SUPERVISOR/ { inhdr=0; next }
  inhdr && /^#/ { next }
  { inhdr=0 }
  { print }
' | sed \
  -e 's/^SUPER_MODEL_IMPLEMENTER=sonnet/SUPER_MODEL_IMPLEMENTER=inherit/' \
  -e 's/^SUPER_MODEL_FIX_APPLIER=sonnet/SUPER_MODEL_FIX_APPLIER=inherit/' \
  -e 's/^SUPER_MODEL_TASK_REVIEWER=opus/SUPER_MODEL_TASK_REVIEWER=inherit/' \
  -e 's/^SUPER_MODEL_RE_REVIEWER=opus/SUPER_MODEL_RE_REVIEWER=inherit/' \
  -e 's/^SUPER_MODEL_BRANCH_REVIEWER=opus/SUPER_MODEL_BRANCH_REVIEWER=inherit/' \
  -e 's/^SUPER_MODEL_FIX_PLANNER=opus/SUPER_MODEL_FIX_PLANNER=inherit/' \
  -e 's/(headless tick: opus)/(headless tick: the CLI default model)/' \
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
- **Model keys** (`SUPER_MODEL_*` in `.superenv`) take Cursor model names (`agent --list-models`)
  or `inherit` — Claude tier names are not valid here.

Install (local): `agent --plugin-dir <repo>/cursor …` — or add the repository as a Cursor
marketplace (the root `.cursor-plugin/marketplace.json` points at this directory).

## Known gaps (pending smoke-test validation)

- The external-driver shell scripts (`scripts/superagent-tick.sh`, `bootstrap.sh`,
  `install-timer.sh`, …) still invoke the **Claude** CLI. Until they are ported, schedule the
  `agent -p` tick recipe from `skills/superloop/SKILL.md` (Driver B) directly.
- `superrun` requires `superpowers:subagent-driven-development`; whether the superpowers plugin
  loads under Cursor is unverified. Planning skills (`supergoal`/`superplan`) work without it.
- Headless skill-invocation semantics under `agent -p` are unverified — run
  `scripts/cursor-smoke.sh` (from the repository root, on a machine with the Cursor CLI) and
  report the generated `cursor-smoke-report.md` back.
EOF

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
