#!/usr/bin/env bash
# build-pi-skills.sh — generate the Pi build of the superagent plugin into pi/.
#
# Canonical skills under skills/ are the single source of truth. Markers:
#   <!-- cc-only:start --> … <!-- cc-only:end -->   DROPPED (marker lines too)
#   <line> <!-- cc-only -->                         line DROPPED
#   <!-- cursor-only:start … cursor-only:end -->    DROPPED (wrapper AND content)
#   <!-- codex-only:start … codex-only:end -->      DROPPED (wrapper AND content)
#   <!-- pi-only:start … pi-only:end -->            wrapper dropped, content ACTIVATED
# Output layout (committed; re-run after editing skills/), a valid Pi package:
#   pi/package.json                          { "pi": { "skills": ["skills"] } }
#   pi/skills/<name>/SKILL.md                filtered + substituted skills
#   pi/skills/pi-smoke-probe/SKILL.md        smoke-test probe skill (generated only)
#   pi/templates/                            superenv.default (Pi-specialized), pi agent templates, vault-root.md
#   pi/scripts/                              role-bridge.sh, bridge-fanout.sh, _common.sh (so ${SUPER_PLUGIN_ROOT}/scripts/* resolves)
#   pi/README.md
# Usage: scripts/build-pi-skills.sh [--check]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/pi"
CHECK=false
[ "${1:-}" = "--check" ] && CHECK=true

grep -q '^# (SUPER_MODEL_SUPERVISOR' "$ROOT/templates/superenv.default" \
  || { echo "build: superenv.default header end-marker missing" >&2; exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
TMP="$WORK/out"
mkdir -p "$TMP"

filter_markers() {
  awk '
    /<!-- cc-only:start -->/  { drop=1; next }
    /<!-- cc-only:end -->/    { drop=0; next }
    drop                      { next }
    /<!-- cc-only -->/        { next }
    /^[[:space:]]*<!-- cursor-only:start[[:space:]]*$/ { udrop=1; next }
    /^[[:space:]]*cursor-only:end -->[[:space:]]*$/    { udrop=0; next }
    udrop                     { next }
    /^[[:space:]]*<!-- codex-only:start[[:space:]]*$/ { cdrop=1; next }
    /^[[:space:]]*codex-only:end -->[[:space:]]*$/    { cdrop=0; next }
    cdrop                     { next }
    /^[[:space:]]*<!-- pi-only:start[[:space:]]*$/ { next }
    /^[[:space:]]*pi-only:end -->[[:space:]]*$/    { next }
    { print }
  '
}

substitute() {
  sed \
    -e 's/\${CLAUDE_PLUGIN_ROOT}/\${SUPER_PLUGIN_ROOT}/g' \
    -e 's/claude -p/pi -p/g' \
    -e 's/claude --model/pi --model/g' \
    -e 's/Claude CLI/Pi CLI/g' \
    -e 's/`ANTHROPIC_API_KEY`\/`GH_TOKEN`/Pi provider credentials (`pi auth`) and `GH_TOKEN`/g' \
    -e '/OPENAI_API_KEY` \/ `ANTHROPIC_API_KEY/!s/`ANTHROPIC_API_KEY`/Pi provider credentials (`pi auth`)/g' \
    -e 's/^driver: cron  .*/driver: external                  # the only driver in this build (external scheduler — fresh context per tick)/' \
    -e 's/^cron_id:  .*# CronCreate job id.*/cron_id:                          # unused in this build (Claude Code in-session driver only); leave empty/'
}

banner_file="$WORK/banner"
cat >"$banner_file" <<'EOF'

<!-- GENERATED FILE — Pi build. Do not edit by hand: edit the canonical skill under skills/
     in the plugin repository and re-run scripts/build-pi-skills.sh. -->

> **Pi build notes.**
> - Only the **external** driver exists in this build. Claude Code's in-session cron driver and its
>   `CronCreate` / `CronList` / `CronDelete` / `Monitor` / `AskUserQuestion` tools do **not** exist
>   on Pi — treat any residual mention as inapplicable and NEVER attempt those tool calls.
> - Tool mapping in the SUPERVISOR (`superagent`, `superloop`): "Agent tool" / "dispatch a
>   subagent" = a blocking `bash` call to `${SUPER_PLUGIN_ROOT}/scripts/role-bridge.sh`
>   (`superplan`, `superrun`) or `${SUPER_PLUGIN_ROOT}/scripts/bridge-fanout.sh` (the L7 panel),
>   per the Pi-specific guidance embedded in those skills. The supervisor never uses a subagent tool.
> - Tool mapping in `superrun` (the SDD controller): "dispatch a subagent" = the `subagent` tool
>   from the `pi-subagents` package with `async: false`, one child per call; role pins ride the
>   `.pi/agents/super-<role>.md` definitions `init` generates. If the tool is absent, follow SDD's
>   sequential fallback and report it.
> - "Skill tool / invoke skill X" = `read` `${SUPER_PLUGIN_ROOT}/skills/X/SKILL.md` and follow it
>   (`/skill:` commands are interactive-only). Superpowers skills are listed by Pi from the
>   installed `superpowers` package — reference them by name.
> - `${SUPER_PLUGIN_ROOT}` = the plugin repository's `pi/` directory (two levels above each
>   SKILL.md). It contains `skills/`, `templates/`, and `scripts/` (`role-bridge.sh`,
>   `bridge-fanout.sh`, `_common.sh`). The external-driver wrappers (`superagent-tick.sh`,
>   `launch.sh`, …) live in the repository's top-level `scripts/` — one directory up.
> - `EnterWorktree` = not available; use `git worktree` via `bash`.
EOF

insert_banner() {
  local src="$1" fmline
  fmline="$(awk '/^---$/{c++; if(c==2){print NR; exit}}' "$src")"
  if [ -z "$fmline" ]; then cat "$src"; return; fi
  head -n "$fmline" "$src"; cat "$banner_file"; tail -n +"$((fmline + 1))" "$src"
}

for dir in "$ROOT"/skills/*/; do
  name="$(basename "$dir")"
  mkdir -p "$TMP/skills/$name"
  filter_markers <"$dir/SKILL.md" | substitute >"$WORK/pre"
  insert_banner "$WORK/pre" >"$TMP/skills/$name/SKILL.md"
done

mkdir -p "$TMP/skills/pi-smoke-probe"
cat >"$TMP/skills/pi-smoke-probe/SKILL.md" <<'EOF'
---
name: pi-smoke-probe
description: Use when asked to run the pi smoke probe (or "superagent pi probe") — verifies the Pi build of the superagent plugin is loaded and reports environment facts for the port smoke test.
---

# Pi smoke probe

Perform these checks with your file/shell tools, then output ONLY the report block below —
no extra prose before or after it.

1. Determine this skill file's own location and derive `plugin_root` = the directory two levels
   above it (the directory containing `skills/`, `templates/`, `scripts/`). If you cannot
   determine the file's location, report `unknown`.
2. Check whether `<plugin_root>/templates/superenv.default` is readable; capture its first line.
3. Check `<plugin_root>/skills/superloop/SKILL.md`: does it exist; does it contain the string
   "GENERATED FILE — Pi build" (a correct Pi build MUST); does it contain "cc-only", "cursor-only",
   or "codex-only" (a correct Pi build must NOT — marker leakage).
4. Do you have a tool named `subagent`? Report `yes` or `no`.
5. Check whether `<plugin_root>/scripts/role-bridge.sh` and `<plugin_root>/scripts/bridge-fanout.sh`
   exist and are executable.

Report block (fill every value):

    PROBE-BEGIN
    plugin_root: <absolute path, or unknown>
    superenv_default_readable: <yes|no>
    superenv_first_line: <the line, or n/a>
    superloop_skill_present: <yes|no>
    superloop_has_pi_banner: <yes|no>
    superloop_marker_leakage: <yes|no>
    subagent_tool: <yes|no>
    role_bridge_present: <yes|no>
    bridge_fanout_present: <yes|no>
    PROBE-END
EOF

mkdir -p "$TMP/templates" "$TMP/scripts"
cp "$ROOT/templates/super-role-pi-agent.md" "$ROOT/templates/super-role-pi-bridge-agent.md" "$ROOT/templates/vault-root.md" "$TMP/templates/"
cp "$ROOT/scripts/role-bridge.sh" "$ROOT/scripts/bridge-fanout.sh" "$ROOT/scripts/_common.sh" "$TMP/scripts/"
chmod +x "$TMP/scripts/role-bridge.sh" "$TMP/scripts/bridge-fanout.sh"

substitute <"$ROOT/templates/superenv.default" | awk '
  /^# Model values:/ { inhdr=1
    print "# Model values: \"inherit\", or [<harness>:]<model> where <harness> is claude | codex | cursor | pi"
    print "# and <model> is that harness'"'"'s native model string — pi: <provider>/<model> (openai/gpt-5,"
    print "# anthropic/claude-opus-5; optional :<level> suffix); claude: a tier (sonnet|opus|haiku|fable) or full"
    print "# ID; codex: a Codex model (gpt-5.6-sol); cursor: `agent --list-models`. The prefix is optional when"
    print "# the model is recognizable (a \"/\" → pi, tiers/claude-* → claude, gpt-*/o<n>/codex* → codex)."
    print "# On Pi the supervisor'"'"'s own dispatches (planner, executor, panel) are bridge PROCESSES for"
    print "# every harness including pi itself — pins ride CLI flags, no agent definition. superrun'"'"'s SDD"
    print "# roles dispatch through the pi-subagents `subagent` tool; their pins ride .pi/agents/super-<role>.md"
    print "# definitions generated by superagent:init (re-run it after changing one)."
    print "# (SUPER_MODEL_SUPERVISOR must be native to SUPER_HARNESS; the tick refuses a foreign one.)"
    next }
  inhdr && /^# \(SUPER_MODEL_SUPERVISOR/ { inhdr=0; next }
  inhdr && /^#/ { next }
  { inhdr=0 }
  /^# ── Reasoning effort per agent role/ { inefh=1
    print "# ── Reasoning effort per agent role ───────────────────────────────"
    print "# Values are effort names in the ROLE'"'"'s harness, or \"inherit\" (= the CLI/model default)."
    print "#   pi:     off | minimal | low | medium | high | xhigh | max"
    print "#   claude: low | medium | high | xhigh | max · codex: none | minimal | low | medium | high | xhigh"
    print "# SUPER_EFFORT_SUPERVISOR is passed at tick invocation (pi --thinking). Other roles: the"
    print "# bridge'"'"'s :<level> suffix (planner/executor/panel) or the definition'"'"'s thinking: line (SDD roles)."
    next }
  inefh && /^# NOTE \(claude\):/ { inefh=2; next }
  inefh==2 && /^#/ { inefh=0; next }
  inefh==1 && /^#/ { next }
  { inefh=0 }
  { print }
' | sed \
  -e 's/^SUPER_MODEL_\([A-Z_]*\)=claude:[a-z]*/SUPER_MODEL_\1=inherit/' \
  -e 's/^SUPER_HARNESS=claude\([[:space:]]*\)#.*/SUPER_HARNESS=pi\1# this is the Pi build — the external driver fires the Pi CLI (pi -p)/' \
  -e 's/^SUPER_BRIDGE_RELAY_MODEL=sonnet\([[:space:]]*\)#.*/SUPER_BRIDGE_RELAY_MODEL=inherit\1# relay agent model for a BRIDGED SDD role (.pi\/agents relay definition); inherit = the pi-subagents default; never a weak model — it answers instead of relaying/' \
  -e '/^SUPER_PANEL_AGENT_TYPE=/d' \
  >"$TMP/templates/superenv.default"

version="$(sed -n 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$ROOT/.claude-plugin/plugin.json" | head -1)"
cat >"$TMP/package.json" <<EOF
{
  "name": "superagent-pi",
  "version": "${version}",
  "description": "superagent plugin — Pi build (external unattended driver only)",
  "pi": { "skills": ["skills"] }
}
EOF

cat >"$TMP/README.md" <<'EOF'
# superagent — Pi build (GENERATED)

Everything here is generated by `scripts/build-pi-skills.sh` from the canonical skills at the
repository root. **Do not edit by hand.**

- **External driver only.** Loops run via an OS scheduler firing fresh headless `pi -p` sessions
  (`SUPER_HARNESS=pi` in `superagent-tick.sh`).
- **Skill delivery:** the tick passes `--skill <repo>/pi/skills` — no install step. For interactive
  use `pi install /path/to/superagent-plugin/pi` (this directory is a valid Pi package).
- **Prerequisites:** `pi` (`npm install -g @earendil-works/pi-coding-agent`), superpowers as a Pi
  package (`pi install git:github.com/obra/superpowers`), and — recommended — `pi-subagents`
  ≥ 0.58.0 (`pi install npm:pi-subagents`). Without it superrun's SDD children run sequentially
  in-context with no role pins (`SUPER_PI_SUBAGENTS=required` makes init abort instead).
- **Dispatch:** the supervisor runs `superplan`/`superrun` through `scripts/role-bridge.sh` and the
  L7 panel through `scripts/bridge-fanout.sh` — child CLI processes, every harness including Pi.
  superrun's SDD roles use `pi-subagents`' `subagent` tool (`async: false`); their pins ride
  `.pi/agents/super-<role>.md` definitions generated by `init`.
- **Trust:** every headless run passes `--approve` (the operator armed the loop on this repo).
- **Model keys** are `[<harness>:]<model>`; Pi-native values are `<provider>/<model>`; effort keys
  in Pi's domain `off | minimal | low | medium | high | xhigh | max`.

## Validated

**Live smoke, 2026-08-29** (`scripts/pi-smoke.sh`, pi CLI 0.84.3; `pi-subagents` NOT installed on
the build host): **PASS 7 / FAIL 1 (informational) / SKIPPED 3.**

- **P1** (bad-model exit status, informational): **FAIL — exit 1.** pi collapses a bad model and a
  failed turn into the same plain `1`, not a distinct code. This is the exit-code mapping
  `role-bridge.sh` relies on for its own exit-3 ("CLI exited non-zero") bucket.
- **P2** (`--skill` delivery): **PASS.**
- **P4a** (`--tools` role-set hides extension tools, informational): **PASS.**
- **P4b** (no-`--tools` shows extension tools, informational): **inconclusive** — no extension
  tools were installed on the smoke host, so the probe came back with only the base tool set and
  never actually exercised the case it's meant to check.
- **T1** (bridge → pi, role tools + `--skill`): **PASS.**
- **T2** (bridge-fanout ×3): **PASS.**
- **T3** (tick file-read + superagent hard gate): **PASS.**
- **T5** (`build-pi-skills.sh --check`): **PASS.**
- **P3a/P3c** (`pi-subagents` probes) and **T4** (relay round trip): **SKIPPED** —
  `pi-subagents` was not installed on this host. In particular, **P3c (the nested-wait verdict) is
  unverified**, not confirmed passing — do not treat it as validated. Re-run
  `scripts/pi-smoke.sh` on a host with `pi-subagents ≥0.58.0` before promoting the pinned-subagent
  SDD path (S1/S4) further.

Note on numbering: this smoke's T1–T5 are not the spec's T1–T6. Spec T3 (a `--thinking` argv
check) runs offline in `bridge-test.sh` instead, not here; spec T4 (a live multi-tick loop) is
deferred to Task 10; the spec's T5 (relay round trip) and T6 (`build-pi-skills.sh --check`) shift
down to this smoke's T4 and T5 above.

## Known gaps

- No tick — single or multi — has been driven end-to-end against a real loop file on Pi: T3 above
  only verified the file-read + hard-gate rejection path with no `PLAN.md`/loop file supplied.
- superpowers was NOT installed as a Pi package on the smoke host (`pi-smoke-report.md`:
  `superpowers package: 0`), so Pi skill listing and superpowers' own Pi SDD mapping are
  unverified.
- `superagent:init` has not been run on Pi, and no `superagent-tick.sh` has run against a real
  loop file on Pi — both pending the deferred Task 10.
- S3 with `pi-subagents` not exercised inside a real superrun.
EOF

grep -q 'GENERATED FILE — Pi build' "$TMP/skills/superloop/SKILL.md" || { echo "build-pi-skills: banner missing" >&2; exit 1; }
# NOTE: match actual unprocessed marker SYNTAX (an HTML-comment open, or a bare ":start"/":end"
# tag), not the bare words — those legitimately appear in pi-smoke-probe's own descriptive prose
# (step 3 of its generated skill body: 'does it contain "cc-only", "cursor-only", or "codex-only"
# (a correct Pi build must NOT — marker leakage)'), which quotes the strings it checks a
# *deployed* build for.
if grep -rqE '<!--[[:space:]]*(cc|cursor|codex|pi)-only|(cc|cursor|codex|pi)-only:(start|end)' "$TMP/skills"; then
  echo "build-pi-skills: marker leakage" >&2; exit 1
fi

if $CHECK; then
  [ -d "$OUT" ] || { echo "build-pi-skills: --check: $OUT does not exist (run the build first)" >&2; exit 1; }
  if diff -r "$TMP" "$OUT" >/dev/null 2>&1; then echo "build-pi-skills: pi/ is up to date"
  else echo "build-pi-skills: pi/ is STALE — re-run scripts/build-pi-skills.sh:" >&2; diff -r "$TMP" "$OUT" >&2 || true; exit 1; fi
else
  rm -rf "$OUT"; mkdir -p "$OUT"; cp -R "$TMP"/. "$OUT"/
  echo "build-pi-skills: wrote $OUT"
fi
