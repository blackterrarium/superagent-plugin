#!/usr/bin/env bash
# build-codex-skills.sh — generate the Codex build of the superagent plugin into codex/.
#
# The canonical skills under skills/ are the single source of truth. This script derives the
# Codex variant (external driver only; Claude Code-specific tooling stripped) from conditional
# markers embedded in the canonical SKILL.md files:
#
#   <!-- cc-only:start --> ... <!-- cc-only:end -->    block kept in the Claude Code build,
#                                                      DROPPED here (marker lines too)
#   <some line> <!-- cc-only -->                       single line DROPPED here
#   <!-- cursor-only:start                             block is an inert HTML comment in the
#     ...content...                                    canonical file; here the wrapper lines AND
#   cursor-only:end -->                                the content are DROPPED (like cc-only)
#   <!-- codex-only:start                              block is an inert HTML comment in the
#     ...content...                                    canonical file; here the wrapper lines are
#   codex-only:end -->                                 dropped and the content is ACTIVATED
#                                                      (note: NO closing --> on the start line —
#                                                      same form as cursor-only)
#   <!-- pi-only:start … pi-only:end -->   block DROPPED here (wrapper AND content)
#
# After marker filtering, harness-specific text substitutions are applied (see seds below), and a
# generated-file banner is inserted after each SKILL.md's frontmatter.
#
# Output layout (committed to the repo; re-run this script after editing skills/), laid out as a
# Codex plugin-marketplace root:
#   codex/.agents/plugins/marketplace.json              Codex plugin-marketplace manifest
#   codex/plugins/superagent/.codex-plugin/plugin.json   Codex plugin manifest
#   codex/plugins/superagent/skills/<name>/SKILL.md      stripped + substituted skills
#   codex/plugins/superagent/skills/codex-smoke-probe/   smoke-test probe skill (generated here,
#                                                         no canonical copy)
#   codex/plugins/superagent/templates/                  templates (superenv.default specialized
#                                                         for Codex; inside the plugin so installs ship them)
#   codex/README.md                                      install notes + known gaps
#
# Usage:
#   scripts/build-codex-skills.sh           rebuild codex/ in place
#   scripts/build-codex-skills.sh --check   rebuild to a temp dir and diff against codex/
#                                            (exit 1 if stale — for CI / pre-release)

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/codex"
CHECK=false
[ "${1:-}" = "--check" ] && CHECK=true

# The superenv.default header rewrite below is delimited by awk on this exact comment line —
# if it is ever reworded, the awk silently swallows the rest of the file. Fail loudly instead.
grep -q '^# (SUPER_MODEL_SUPERVISOR' "$ROOT/templates/superenv.default" \
  || { echo "build: superenv.default header end-marker missing" >&2; exit 1; }

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
    /^[[:space:]]*<!-- cursor-only:start[[:space:]]*$/ { udrop=1; next }
    /^[[:space:]]*cursor-only:end -->[[:space:]]*$/    { udrop=0; next }
    udrop                     { next }
    /^[[:space:]]*<!-- codex-only:start[[:space:]]*$/ { next }
    /^[[:space:]]*codex-only:end -->[[:space:]]*$/    { next }
    /^[[:space:]]*<!-- pi-only:start[[:space:]]*$/ { pdrop=1; next }
    /^[[:space:]]*pi-only:end -->[[:space:]]*$/    { pdrop=0; next }
    pdrop                     { next }
    { print }
  '
}

# ── Harness substitutions ────────────────────────────────────────────────────
substitute() {
  sed \
    -e 's/\${CLAUDE_PLUGIN_ROOT}/\${SUPER_PLUGIN_ROOT}/g' \
    -e 's/claude -p/codex exec/g' \
    -e 's/claude --model/codex exec -m/g' \
    -e '/OPENAI_API_KEY` \/ `ANTHROPIC_API_KEY/!s/ANTHROPIC_API_KEY/OPENAI_API_KEY/g' \
    -e 's/Claude CLI/Codex CLI/g' \
    -e 's/^driver: cron  .*/driver: external                  # the only driver in this build (external scheduler — fresh context per tick)/' \
    -e 's/^cron_id:  .*# CronCreate job id.*/cron_id:                          # unused in this build (Claude Code in-session driver only); leave empty/'
}

# ── Banner (inserted after the SKILL.md frontmatter) ─────────────────────────
banner_file="$WORK/banner"
cat >"$banner_file" <<'EOF'

<!-- GENERATED FILE — Codex build. Do not edit by hand: edit the canonical skill under skills/
     in the plugin repository and re-run scripts/build-codex-skills.sh. -->

> **Codex build notes.**
> - Only the **external** driver exists in this build. Claude Code's in-session cron driver and its
>   `CronCreate` / `CronList` / `CronDelete` and `Monitor` tools do **not** exist on Codex — treat
>   any residual mention of them as inapplicable and NEVER attempt those tool calls.
> - Tool mapping: "Agent tool" / "spawn a subagent" = the `spawn_agent` tool (multi-agent v2 —
>   wait for the child's result). Role pins from `.superenv` map to its parameters:
>   `SUPER_MODEL_<ROLE>` → `model`, `SUPER_EFFORT_<ROLE>` → `reasoning_effort`
>   (`inherit` = omit the parameter). There are NO `.claude/agents/` definition files in this
>   build — where a skill says "dispatch via subagent_type: super-<role>", pass the role's
>   resolved model/effort as spawn parameters instead — and any accompanying "missing definition =
>   hard error / re-run `superagent:init`" clause does not apply in this build (there is nothing to
>   generate; a bridged role's relay spawn needs no definition either). A role whose value names
>   another harness (`claude:sonnet`, `pi:openai/gpt-5`, …) is BRIDGED: spawn a relay child
>   (`model` = `SUPER_BRIDGE_RELAY_MODEL`, omit when `inherit`) whose message is
>   `${SUPER_PLUGIN_ROOT}/templates/relay-preamble.md` rendered for that role followed by the task
>   prompt; the relay runs `${SUPER_PLUGIN_ROOT}/scripts/role-bridge.sh` and returns the foreign
>   CLI's result verbatim. "Skill tool" = reference the skill by
>   name in the conversation. `AskUserQuestion` / `AskQuestion` = ask the user in chat (attended
>   sessions only — never in a headless tick). `EnterWorktree` = not available; use
>   `git worktree` via shell.
> - `${SUPER_PLUGIN_ROOT}` in commands and paths = this plugin's installed root (the directory
>   containing `skills/` and `templates/`, two levels above each SKILL.md — for a marketplace
>   install that is the plugin cache copy; in the source repository it is
>   `<repo>/codex/plugins/superagent`). Substitute its absolute path wherever it appears.
>   Exception: the external-driver `scripts/` helpers (`superagent-tick.sh`, `launch.sh`, …) are
>   not packaged inside the plugin — they live in the plugin source repository. Read
>   `${SUPER_PLUGIN_ROOT}/scripts/` as that repository's `scripts/` directory (the
>   `SUPERAGENT_SCRIPTS` convention in its scripts/README.md) — except `scripts/role-bridge.sh`,
>   which IS packaged inside the plugin at `${SUPER_PLUGIN_ROOT}/scripts/role-bridge.sh` — use that
>   path for it.
> - Skill lookup: this plugin installs via the Codex plugin marketplace; skills resolve by name
>   (e.g. `superplan`). The `superagent` supervisor skill is driven by reading its SKILL.md
>   directly (the external tick's file-read prompt), never invoked by name.
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
  mkdir -p "$TMP/plugins/superagent/skills/$name"
  filter_markers <"$dir/SKILL.md" | substitute >"$WORK/pre"
  insert_banner "$WORK/pre" >"$TMP/plugins/superagent/skills/$name/SKILL.md"
done

# ── Smoke-probe skill (generated only; no canonical counterpart) ─────────────
mkdir -p "$TMP/plugins/superagent/skills/codex-smoke-probe"
cat >"$TMP/plugins/superagent/skills/codex-smoke-probe/SKILL.md" <<'EOF'
---
name: codex-smoke-probe
description: Use when asked to run the codex smoke probe (or "superagent codex probe") — verifies the Codex build of the superagent plugin is loaded and reports environment facts for the port smoke test.
---

# Codex smoke probe

Perform these checks with your file/shell tools, then output ONLY the report block below —
no extra prose before or after it.

1. Determine this skill file's own location and derive `plugin_root` = the directory two levels
   above it (the directory containing `skills/` and `templates/`). If you cannot determine the
   file's location, report `unknown`.
2. Check whether `<plugin_root>/templates/superenv.default` is readable; capture its first line.
3. Check `<plugin_root>/skills/superloop/SKILL.md`: does it exist; does it
   contain the string "GENERATED FILE — Codex build" (a correct Codex build MUST); does it
   contain the string "cc-only" OR the string "cursor-only" (a correct Codex build must NOT —
   either would be marker leakage from the build).
4. Report the CODEX_HOME environment variable: `echo "${CODEX_HOME:-unset}"`.
5. Check whether `<plugin_root>/scripts/role-bridge.sh` exists and is executable.

Report block (fill every value):

    PROBE-BEGIN
    plugin_root: <absolute path, or unknown>
    superenv_default_readable: <yes|no>
    superenv_first_line: <the line, or n/a>
    superloop_skill_present: <yes|no>
    superloop_has_codex_banner: <yes|no>
    superloop_marker_leakage: <yes|no>
    env_codex_home: <value, or unset>
    role_bridge_present: <yes|no>
    PROBE-END
EOF

# ── Templates ────────────────────────────────────────────────────────────────
# Inside the plugin directory (NOT the marketplace root): `codex plugin add` copies only
# source.path (./plugins/superagent) into the install cache, so anything outside it —
# including a root-level templates/ — would not ship (verified against codex CLI 0.147.0).
mkdir -p "$TMP/plugins/superagent/templates"
cp "$ROOT/templates/super-role-agent.md" "$TMP/plugins/superagent/templates/"
cp "$ROOT/templates/super-role-bridge-agent.md" "$TMP/plugins/superagent/templates/"
cp "$ROOT/templates/relay-preamble.md" "$TMP/plugins/superagent/templates/"
cp "$ROOT/templates/vault-root.md" "$TMP/plugins/superagent/templates/"
mkdir -p "$TMP/plugins/superagent/scripts"
cp "$ROOT/scripts/role-bridge.sh" "$TMP/plugins/superagent/scripts/"
chmod +x "$TMP/plugins/superagent/scripts/role-bridge.sh"

# superenv.default: same seds as skills, then Codex-specific header + model defaults.
substitute <"$ROOT/templates/superenv.default" | awk '
  # Replace the Claude model-values header block (lines from "# Model values:" through the
  # "(SUPER_MODEL_SUPERVISOR ..." comment line) with the Codex wording.
  /^# Model values:/ { inhdr=1
    print "# Model values: \"inherit\", or [<harness>:]<model> where <harness> is claude | codex | cursor | pi"
    print "# and <model> is that harness'"'"'s native model string — codex: a Codex model (gpt-5.6-sol); claude:"
    print "# a tier (sonnet|opus|haiku|fable) or full ID (claude-fable-5); cursor: `agent --list-models`;"
    print "# pi: <provider>/<model> (openai/gpt-5, anthropic/claude-opus-5). The prefix is optional when the"
    print "# model is recognizable (tiers/claude-* → claude, gpt-*/o<n>/codex* → codex, a \"/\" → pi)."
    print "# A role whose harness differs from SUPER_HARNESS is BRIDGED: dispatched through the same"
    print "# per-role subagent hook, executed by that harness'"'"'s CLI via scripts/role-bridge.sh (the CLI must"
    print "# be installed and logged in). SUPER_MODEL_SUPERVISOR must be native to SUPER_HARNESS."
    print "# On Codex there are no agent-definition files: native pins ride spawn_agent parameters;"
    print "# bridged roles spawn a relay from templates/relay-preamble.md."
    print "# (SUPER_MODEL_SUPERVISOR must be native to SUPER_HARNESS; the tick refuses a foreign one.)"
    next }
  inhdr && /^# \(SUPER_MODEL_SUPERVISOR/ { inhdr=0; next }
  inhdr && /^#/ { next }
  { inhdr=0 }
  # Replace the Reasoning-effort header block (from "# ── Reasoning effort per agent role"
  # through the "# NOTE (claude): ... leave it unset in scheduler environments." continuation
  # line) with the Codex wording (drop the claude/cursor domain lines and the CLAUDE_CODE_EFFORT_LEVEL
  # note; keep the effort VALUES unchanged elsewhere in the file).
  /^# ── Reasoning effort per agent role/ { inefh=1
    print "# ── Reasoning effort per agent role ───────────────────────────────"
    print "# Values are Codex effort names, or \"inherit\" (= the CLI/model default)."
    print "#   codex: none | minimal | low | medium | high | xhigh"
    print "# SUPER_EFFORT_SUPERVISOR is passed at tick invocation (-c model_reasoning_effort)."
    print "# Any other non-inherit role key pins via the subagent-spawn parameter"
    print "# (reasoning_effort on spawn_agent)."
    next }
  inefh && /^# NOTE \(claude\):/ { inefh=2; next }
  inefh==2 && /^#/ { inefh=0; next }
  inefh==1 && /^#/ { next }
  { inefh=0 }
  { print }
' | sed \
  -e 's/^SUPER_MODEL_SUPERVISOR=claude:[^[:space:]]*/SUPER_MODEL_SUPERVISOR=codex:gpt-5.6-sol/' \
  -e 's/^SUPER_MODEL_PLANNER=claude:[^[:space:]]*/SUPER_MODEL_PLANNER=codex:gpt-5.6-sol/' \
  -e 's/^SUPER_MODEL_EXECUTOR=claude:[^[:space:]]*/SUPER_MODEL_EXECUTOR=codex:gpt-5.6-sol/' \
  -e 's/^SUPER_MODEL_PANEL=claude:[^[:space:]]*/SUPER_MODEL_PANEL=codex:gpt-5.6-sol/' \
  -e 's/^SUPER_MODEL_IMPLEMENTER=claude:[^[:space:]]*/SUPER_MODEL_IMPLEMENTER=codex:gpt-5.6-terra/' \
  -e 's/^SUPER_MODEL_FIX_APPLIER=claude:[^[:space:]]*/SUPER_MODEL_FIX_APPLIER=codex:gpt-5.6-terra/' \
  -e 's/^SUPER_MODEL_TASK_REVIEWER=claude:[^[:space:]]*/SUPER_MODEL_TASK_REVIEWER=codex:gpt-5.6-sol/' \
  -e 's/^SUPER_MODEL_RE_REVIEWER=claude:[^[:space:]]*/SUPER_MODEL_RE_REVIEWER=codex:gpt-5.6-sol/' \
  -e 's/^SUPER_MODEL_BRANCH_REVIEWER=claude:[^[:space:]]*/SUPER_MODEL_BRANCH_REVIEWER=codex:gpt-5.6-sol/' \
  -e 's/^SUPER_MODEL_FIX_PLANNER=claude:[^[:space:]]*/SUPER_MODEL_FIX_PLANNER=codex:gpt-5.6-sol/' \
  -e 's/^SUPER_HARNESS=claude\([[:space:]]*\)#.*/SUPER_HARNESS=codex\1# this is the Codex build — the external driver fires the Codex CLI (codex exec)/' \
  -e 's/^SUPER_BRIDGE_RELAY_MODEL=sonnet\([[:space:]]*\)#.*/SUPER_BRIDGE_RELAY_MODEL=inherit\1# relay subagent model for BRIDGED roles; inherit = the CLI default subagent model/' \
  >"$TMP/plugins/superagent/templates/superenv.default"

# ── Manifest ─────────────────────────────────────────────────────────────────
version="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$ROOT/.claude-plugin/plugin.json" | head -1)"
mkdir -p "$TMP/plugins/superagent/.codex-plugin"
cat >"$TMP/plugins/superagent/.codex-plugin/plugin.json" <<EOF
{
  "name": "superagent",
  "description": "Plan-tree authoring (supergoal/superplan) and autonomy-loop execution (superagent/superrun) skills — Codex build (external unattended driver only)",
  "version": "${version}",
  "author": { "name": "Eugene Chai", "email": "eugene.chai@gmail.com" },
  "repository": "https://github.com/blackterrarium/superagent-plugin",
  "keywords": ["planning", "autonomy-loop", "subagents", "workflows"]
}
EOF

# Manifest location + schema per codex-rs/core-plugins/src/marketplace.rs (verified against
# codex CLI 0.147.0, smoke run 2026-08-12): the CLI only discovers a marketplace manifest at
# .agents/plugins/marketplace.json (or the .claude-plugin/.cursor-plugin variants) under the
# root — NEVER a root-level marketplace.json. source.source is "local" and the policy enums
# are SCREAMING_CASE ("AVAILABLE" / "ON_INSTALL").
mkdir -p "$TMP/.agents/plugins"
cat >"$TMP/.agents/plugins/marketplace.json" <<EOF
{
  "name": "superagent",
  "interface": { "displayName": "superagent (Codex build)" },
  "plugins": [
    {
      "name": "superagent",
      "source": { "source": "local", "path": "./plugins/superagent" },
      "description": "Plan-tree authoring and autonomy-loop execution skills — Codex build",
      "category": "Productivity",
      "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" }
    }
  ]
}
EOF

# ── README ───────────────────────────────────────────────────────────────────
cat >"$TMP/README.md" <<'EOF'
# superagent — Codex build (GENERATED)

Everything in this directory is generated by `scripts/build-codex-skills.sh` from the canonical
Claude Code skills at the repository root. **Do not edit by hand** — edit the canonical skill and
re-run the build.

This build differs from the Claude Code plugin:

- **External driver only.** The in-session `cron` driver (Claude Code `CronCreate`/`Monitor`
  tooling) is stripped; loops run via an OS scheduler firing fresh headless `codex exec` sessions.
- **`WAITING FOR INPUT` is always answered via the loop file** (`answer: <option>`), or in chat in
  an attended session.
- **Model keys** (`SUPER_MODEL_*` in `.superenv`) take `[<harness>:]<model>` — a Codex model name
  (e.g. `gpt-5.1-codex`) or `inherit` natively; a value naming another harness (`claude:sonnet`,
  `pi:openai/gpt-5`, …) is valid too but BRIDGED — dispatched through a relay that runs the shipped
  `scripts/role-bridge.sh`.
- **Effort keys** (`SUPER_EFFORT_*`) take Codex effort names (`none | minimal | low | medium |
  high | xhigh`) or `inherit`.
- **No `.claude/agents/` definition files.** Native pins ride `spawn_agent` parameters; bridged
  roles spawn a relay from `templates/relay-preamble.md`.
- **Ships the bridge.** This package includes `scripts/role-bridge.sh` and the two relay templates
  (`templates/super-role-bridge-agent.md`, `templates/relay-preamble.md`); `SUPER_BRIDGE_RELAY_MODEL`
  (default `inherit`) sets the relay subagent's model.

Install: `codex plugin marketplace add blackterrarium/superagent-plugin` (the plugin repository's
root `.agents/plugins/marketplace.json` makes the repo itself the marketplace root; a local clone
path, or `<clone>/codex`, works the same) then `codex plugin add superagent@superagent`. The
install copies `plugins/superagent/` (skills + templates) into `~/.codex/plugins/cache/`.

Auth: `OPENAI_API_KEY` in the target repo's `.env`, else the CLI's own stored login (`codex
login`).

Sandbox: `SUPER_CODEX_SANDBOX` in `.superenv` — `danger-full-access` (default:
`--dangerously-bypass-approvals-and-sandbox`, claude-harness parity) or `workspace-write`
(repo + /tmp writable, network on — but the repo's top-level `.git/` stays read-only, so git
fetch/commit fail and the sync gate parks the loop).

## Validated (smoke run, 2026-08-12, codex CLI 0.147.0 on macOS)

- Headless mode (`codex exec`), the marketplace install path, and `-c model_reasoning_effort=<v>`
  all work (T1/T2/T2b/T6).
- Plugin skills are enumerable and model-invocable from a neutral workspace; the probe skill
  resolves its installed plugin root (the cache copy under `~/.codex/plugins/cache/…`) and reads
  bundled templates by relative path (T3/T4a). `codex plugin add` copies ONLY the plugin
  directory (`source.path`) into the cache — which is why `templates/` lives inside
  `plugins/superagent/`, not at the marketplace root.
- `spawn_agent` (multi-agent v2) IS available in plain `codex exec` sessions and returns child
  results (T4b) — the subagent mapping in the banner is exercisable.
- The external-tick entry point works: a file-read prompt drives the supervisor skill, and its
  no-plan hard gate fires with the expected message (T5).
- Marketplace manifest facts learned from the CLI (encoded in this build): the manifest must live
  at `.agents/plugins/marketplace.json` under the marketplace root (a root-level
  `marketplace.json` is NOT discovered), `source.source` is `"local"`, and the policy enums are
  `"AVAILABLE"` / `"ON_INSTALL"`.
- Codex CLI defaults observed: `codex exec` runs sandbox `read-only`, approval `never`, and the
  configured default model at reasoning effort `low` — which is why this build's shipped
  `superenv.default` pins `SUPER_MODEL_SUPERVISOR=codex:gpt-5.6-sol` / `SUPER_EFFORT_SUPERVISOR=medium`
  instead of leaving them `inherit`.

## Known gaps

- No end-to-end loop run (a real goal driven to DONE by a scheduler) has been exercised on Codex
  yet — the tick invocation itself is smoke-validated (T5), the full multi-tick loop is not.
- The `superagent-monitor` attended-tick recipe still shows canonical paths and a Claude-only
  flag (pre-existing in both generated builds; tracked for follow-up).
EOF

# ── Post-generation sanity checks ─────────────────────────────────────────────
grep -q 'OPENAI_API_KEY` / `ANTHROPIC_API_KEY' "$TMP/plugins/superagent/skills/init/SKILL.md" \
  || { echo "build-codex-skills: pi-auth carve-out no longer matches — fix the sed address" >&2; exit 1; }
[ -x "$TMP/plugins/superagent/scripts/role-bridge.sh" ] \
  || { echo "build-codex-skills: role-bridge.sh not executable" >&2; exit 1; }

# ── Emit or check ────────────────────────────────────────────────────────────
if $CHECK; then
  if [ ! -d "$OUT" ]; then
    echo "build-codex-skills: --check: $OUT does not exist (run the build first)" >&2
    exit 1
  fi
  [ -x "$OUT/plugins/superagent/scripts/role-bridge.sh" ] \
    || { echo "build-codex-skills: --check: $OUT/plugins/superagent/scripts/role-bridge.sh missing or not executable" >&2; exit 1; }
  if diff -r "$TMP" "$OUT" >/dev/null 2>&1; then
    echo "build-codex-skills: codex/ is up to date"
  else
    echo "build-codex-skills: codex/ is STALE — re-run scripts/build-codex-skills.sh:" >&2
    diff -r "$TMP" "$OUT" >&2 || true
    exit 1
  fi
else
  rm -rf "$OUT"
  mkdir -p "$OUT"
  cp -R "$TMP"/. "$OUT"/

  echo "build-codex-skills: wrote $OUT"
fi
