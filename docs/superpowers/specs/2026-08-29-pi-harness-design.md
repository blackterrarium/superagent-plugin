# Pi harness support (`SUPER_HARNESS=pi`) — design

**Date:** 2026-08-29
**Status:** draft for review
**Builds on:** `2026-08-12-codex-harness-design.md` (the port pattern), `2026-08-28-cross-harness-roles-design.md` (the bridge; its "Pi follow-up" note is what this spec resolves), issue #25 / 0.5.1 (superrun as its own CLI process).

## Goal

Let a Pi CLI session drive the superagent external loop: `SUPER_HARNESS=pi` selects `pi -p` as the
supervisor tick, the plugin's skills are delivered to that session, and every role the loop
dispatches — planner, executor, the L7 panel, and superrun's SDD children — runs with its
`.superenv` model/effort pins honoured, on Pi or on any other harness.

The **hybrid dispatch decision** (the open question in the cross-harness spec's follow-up note):

- The supervisor's own dispatches — S1 `superplan`, S2 `superrun`, S4 the L7 panel — go through
  `scripts/role-bridge.sh` as child CLI processes. No in-process subagent tool is needed for the
  loop's control plane, so bare Pi core is sufficient to run a loop.
- superrun's SDD children (S3: implementer, fix-applier, task-reviewer, re-reviewer,
  branch-reviewer, fix-planner) are dispatched by superpowers' `subagent-driven-development`,
  which on Pi resolves "dispatch a subagent" to the **`pi-subagents`** package if installed and to
  its documented sequential fallback otherwise. `pi-subagents` is therefore a **recommended,
  not required** companion: `init` WARNs when it is absent or too old, never aborts.

Why hybrid and not one of the two pure options:

- Pure bridge would have to override superpowers' own Pi dispatch policy inside superrun (a fork
  of SDD behaviour we would then own); pure `pi-subagents` would put a third-party package with
  daily releases and no 1.0 in the loop's critical path, and since its 0.51.0 release
  parallel/multi-child runs are **async-only** — exactly the poll-and-wait shape the chassis
  forbids — so it is a poor fit for the panel anyway.
- The bridge already runs S2 this way on the Claude harness (0.5.1), is smoke-tested for every
  harness (T1–T4), and gives blocking parallelism for free with a `wait`.

## Non-goals (YAGNI)

- Requiring `pi-subagents`. A loop must run to DONE on Pi core + superpowers alone (with SDD's
  sequential fallback for S3).
- Bridging the supervisor. `SUPER_MODEL_SUPERVISOR` must be native (`pi:…`); tick exit 11 stands.
- `--mode rpc`. The tick uses `-p` with `text` or `--mode json` output, like the other harnesses.
- Pi-specific input gate / WatchPaths wake, interactive `/superagent` on Pi (external driver only,
  as for Codex and Cursor), per-tick harness alternation.
- Verifying Cursor bridging (still unverified; unchanged by this work).
- Any change to how the Claude, Codex, or Cursor harnesses dispatch roles. This spec adds a
  harness; it does not re-open their designs. Pi *as a bridged role target* from those harnesses
  keeps working exactly as in 0.5.x.

## Pi CLI facts this design relies on

Verified against the installed `@earendil-works/pi-coding-agent` 0.84.3 (`pi --help`, `docs/`):

- Headless: `pi -p [--mode text|json] [--model <provider>/<id>[:<thinking>]] [--thinking <level>]
  [--tools <list>] [--skill <path>]… [--approve] [--no-session]`. Prompt is read from stdin or given
  as trailing message args. `--mode json` streams session events as JSON lines.
- Model strings are `provider/id`, optionally `:thinking` suffixed. `--thinking` accepts
  `off|minimal|low|medium|high|xhigh|max`. The default provider/model come from
  `~/.pi/agent/settings.json` (`defaultProvider`/`defaultModel`).
- Built-in tools: `read`, `bash`, `edit`, `write`, `grep`, `find`, `ls`. `--tools` is an allowlist
  over built-in **and** extension tools; there are no ask-the-user tools.
- Skills follow the Agent Skills standard. Discovery: `~/.pi/agent/skills/`, `~/.agents/skills/`,
  project `.pi/skills/` / `.agents/skills/` (**only after project trust**), packages, the
  `skills` array in settings, and `--skill <path>` (repeatable; directories are scanned
  recursively for `SKILL.md`). Skills are loaded on demand by `read`ing their `SKILL.md`.
- Packages: `pi install npm:<pkg>@<ver>` / `git:…` / `<local path>`; `-l` writes to project
  `.pi/settings.json` instead of the global one; `pi list` enumerates installed packages.
- Project trust: non-interactive modes never prompt; without a saved decision they follow
  `defaultProjectTrust` (`ask` default ⇒ project-local `.pi/*` resources are **ignored**).
  `--approve`/`-a` trusts the project for one run. Global packages/skills load regardless.
- Sessions are saved per cwd under `~/.pi/agent/sessions/` unless `--no-session`.
- Auth lives in `~/.pi/agent/auth.json`; `pi auth check --provider <p>` reports readiness.
- **Unverified (probe P1):** `pi -p`'s exit status on a failed/aborted turn.

Superpowers on Pi (superpowers 6.3.0 README + `references/pi-tools.md`): installed as a Pi package
(`pi install git:github.com/obra/superpowers`); Pi has native skills so no `Skill` tool shim;
"dispatch a subagent" ⇒ `pi-subagents`' `subagent` tool if installed, else "execute sequentially in
the current session"; task lists ⇒ plan-file checklists.

`pi-subagents` (npm, 0.59.0 on 2026-08-28; ~1 release/day; peer dep `pi-ai >=0.80.0`, others
`*`; no stability statement): `pi install npm:pi-subagents`; agents are frontmatter files with
`model: provider/id[:thinking]`, `thinking:`, `tools:`, optional model allow-lists (0.54) and
`inheritGlobalContext` (default **false** since 0.58.0 — a breaking change); a single run with
`async: false` blocks and returns the child's final output; parallel/chain/workflow runs are
**background-only** since 0.51.0; nested spawning is allowed under `maxSubagentSpawnsPerRun`
(default 64). Floor for this design: **`>=0.58.0`**, verified against 0.59.0.

## 1. Architecture

`pi` becomes the fourth value of `SUPER_HARNESS`, resolved through the existing precedence
(process env > repo `.superenv` > plugin default). Loop state stays in the gitignored loop-status
file; Pi-driven loops coexist with the others on one host.

Dispatch sites on the Pi harness:

| Site | Who dispatches | Mechanism on Pi | Model/effort pin |
|---|---|---|---|
| S1 `superplan` | supervisor tick | `role-bridge.sh --harness <h> --tools planner` (blocking `bash`) | `SUPER_MODEL/EFFORT_PLANNER`, any harness |
| S2 `superrun` | supervisor tick | `role-bridge.sh --harness <h> --tools executor` — identical to Claude 0.5.1 | `…_EXECUTOR`, any harness |
| S3 SDD children | superrun (superpowers SDD) | `pi-subagents` `subagent` tool (`async:false`) if installed; else SDD's sequential fallback | `…_IMPLEMENTER` etc. via generated agent definitions; foreign harness ⇒ relay definition |
| S4 L7 panel | supervisor tick | `scripts/bridge-fanout.sh` — 3 concurrent bridge runs, one blocking `bash` call | `…_PANEL`, any harness |

Two consequences worth stating plainly:

1. On Pi the *supervisor never uses a subagent tool at all*. Foreign-harness roles at S1/S2/S4
   need **no relay agent**: the supervisor calls the bridge with `--harness codex` directly. The
   relay pattern (and `SUPER_BRIDGE_RELAY_MODEL`) survives only for S3 under `pi-subagents`.
2. A Pi-native role at S1/S2/S4 is *also* a bridge run (`--harness pi`). Native and bridged are
   the same code path on this harness; the only difference is the `--harness` argument.

## 2. Driver changes (`scripts/`)

### `_common.sh`

- `superagent_harness()`: accept `pi` (`want claude|cursor|codex|pi`).
- New `ensure_pi_bin()`: require `pi` on PATH after `_superagent_augment_path`; install hint
  `npm install -g @earendil-works/pi-coding-agent`. `ensure_cli_bin()` dispatches `pi` → it.
- `superagent_role_harness()` / `superagent_role_model()` already handle the `pi:` prefix and the
  `/` inference; unchanged.

### `superagent-tick.sh`

New `pi` branch parallel to `codex`:

- `SKILLS_ROOT=$PLUGIN_ROOT/pi`; exit 7 if `$SKILLS_ROOT/skills/superagent/SKILL.md` is missing
  ("run scripts/build-pi-skills.sh").
- Model: `TICK_MODEL > SUPER_MODEL_SUPERVISOR`; `inherit` → empty → omit `--model` (Pi's
  settings default applies). The existing supervisor-native check (exit 11) applies; the stripped
  value must be `<provider>/<id>` — validated by `init`, re-checked here as the runtime backstop
  (exit 8 on a value without exactly one `/`, mirroring the `SUPER_CODEX_SANDBOX` fail-loud style).
- Effort: `TICK_EFFORT > SUPER_EFFORT_SUPERVISOR`; non-`inherit` → `--thinking <v>`, domain
  `off|minimal|low|medium|high|xhigh|max`. (The 0.5.0 bridge/`init` domain for `pi:` roles was
  `off…high`; this spec widens it to the CLI's full list everywhere — `init`, bridge, tick.)
- Prompt: the same file-read entry point as Codex/Cursor, unattended wording, no Ask* tools.
  Passed on **stdin** (`<<<"$PROMPT"`), not as an argument, so no `</dev/null` dance.
- Invocation, from `cd "$REPO"` under the optional `timeout` wrapper:
  `pi -p --approve --skill "$SKILLS_ROOT/skills" [--model M] [--thinking E] [--mode json]`,
  output appended to `$LOG_FILE`, exit code propagated.
  - `--approve`: the operator armed this loop on this repo; parity with Cursor's `--trust`. It
    lets a repo-local `.pi/settings.json` (e.g. a project-scoped `pi-subagents` install) load.
  - `--skill`: additive delivery of the plugin's skills, no install step — the Cursor
    `--plugin-dir` analogue. Superpowers comes from the operator's global package install.
  - No `--tools` restriction: Pi's built-in set is already the tick's set and there are no
    interactive tools to exclude; extension tools (`subagent`) stay available to superrun's
    children. Sessions are kept (debuggable, like Codex rollouts).
- Env for children: export `SUPERAGENT_PI_SKILLS="$SKILLS_ROOT/skills"` so the bridge can hand the
  same skill root to every child `pi -p` it spawns (§ bridge). `SUPERAGENT_BRIDGE` is exported as
  today.
- Auth note: if `~/.pi/agent/auth.json` is absent, log "relying on env API keys" (warn only).
- The `gh` preflight is unchanged.

### `role-bridge.sh`

The `pi` branch grows to carry what the supervisor previously got from the harness's own subagent
tool:

- `--tools` gains a third named set and becomes meaningful on Pi:
  - `role` → `--tools read,edit,write,bash,grep,find,ls` (leaf: implementer, reviewer, panelist)
  - `planner` → same as `role` (superplan needs files + git; it invokes skills by `read`ing them)
  - `executor` → **no `--tools` flag** (built-ins + extension tools, so superrun's SDD may use
    `subagent` when `pi-subagents` is present)
  - `<list>` → passed verbatim.
  On the claude harness `planner` maps to the existing `role` set plus `Task,Skill` (a claude
  planner dispatched from a Pi supervisor needs the Skill tool); codex/cursor keep ignoring it.
- Always `--approve` and `--no-session` for the child (a bridged run is ephemeral; the log file is
  its record).
- When `SUPERAGENT_PI_SKILLS` is set, append `--skill "$SUPERAGENT_PI_SKILLS"` — a child spawned
  from a Pi supervisor sees the plugin's skills the same way the tick does. When unset (a `pi:`
  role bridged *from* another harness, the 0.5.x case), behaviour is unchanged.
- Effort: keep the `:<level>` model-suffix rule (already shipped, already warns on conflicts);
  additionally, when `--model inherit` and `--effort` non-`inherit`, pass `--thinking <e>` instead
  of dropping it with a warning (the CLI has the flag; the 0.5.0 warning path becomes dead).
- Exit-code mapping stays 0/2/3/4/64. Probe P1 decides whether a failed Pi turn surfaces as
  non-zero (→ exit 3) or as zero-with-empty-output (→ exit 4); both are already handled.

### New `scripts/bridge-fanout.sh`

The S4 primitive: run N bridge invocations concurrently and return all results in one blocking
call, so the L7 panel keeps "wait, never poll" on a harness with no blocking parallel subagent tool.

```
bridge-fanout.sh --harness <h> --model <m> --effort <e> --cwd <dir> --tools role \
                 --timeout <sec> --prompt-file <f1> --prompt-file <f2> --prompt-file <f3>
```

- One background `role-bridge.sh` per prompt file, `wait` on all, hard `--timeout` (default 1800 s)
  after which stragglers are killed and reported as failed.
- stdout: the results in order, each framed as `=== PANELIST <n> exit=<rc> ===` … `=== END <n> ===`
  so the supervisor can attribute them; failures carry the `BRIDGE-FAILED exit=… log=…` line the
  L7 clause already understands. Exit 0 if every run succeeded, 3 if any failed (the panel rung
  tolerates one failed panelist per its existing rule; two or more ⇒ Rung 2).
- Generic — it takes `--harness`, so a `codex:`-pinned panel from a Pi supervisor works unchanged,
  and the script is usable from the Claude/Codex builds later if wanted (not wired there now).

### `launch.sh` / `install-timer.sh`

No new flags. `ensure_cli_bin` covers the binary check. The per-goal env file gets the same
`BASH_MAX_TIMEOUT_MS`-style comment block the Claude build carries (issue #25 note) — Pi's `bash`
tool timeout is a per-call parameter, so the skill text carries the long-timeout instruction, as the
relay preamble already does.

## 3. Pi build (`scripts/build-pi-skills.sh` → `pi/`)

Generated from the canonical skills, committed, regenerated after any canonical edit (the
Codex/Cursor pattern). Laid out as a **Pi package** so it can be delivered either way:

```
pi/package.json                 { "name": "superagent-pi", "pi": { "skills": ["skills"] } }
pi/skills/<name>/SKILL.md       filtered + substituted skills
pi/templates/superenv.default   specialized: SUPER_HARNESS=pi, pi model strings
pi/README.md                    install notes, validated/known-gaps sections
```

Delivery: the tick passes `--skill pi/skills` (default, zero-install). Optionally
`pi install /path/to/superagent-plugin/pi` for interactive use; not required by the driver.

- Markers: new `pi-only:start` / `pi-only:end` activation markers (same inert-comment form as
  `codex-only`); this build drops `cc-only`, `codex-only`, `cursor-only`; the three existing build
  scripts learn to drop `pi-only`. The `<!-- cc-only -->` single-line marker is dropped as today.
- Substitutions: `claude -p` → `pi -p`, `ANTHROPIC_API_KEY` → "Pi provider credentials
  (`pi auth`)", `${CLAUDE_PLUGIN_ROOT}` → `${SUPER_PLUGIN_ROOT}`, `Claude CLI` → `Pi CLI`, driver
  line → external-only, cron_id → unused.
- Generated banner after each SKILL.md frontmatter with the tool mapping:
  - "Skill tool / invoke skill X" → `read` `${SUPER_PLUGIN_ROOT}/pi/skills/X/SKILL.md` and follow
    it (skills are files; `/skill:` commands are interactive-only). Superpowers skills are
    referenced by name — Pi lists them in the system prompt from the installed package.
  - "Agent tool / dispatch a subagent" **in the supervisor skill and superloop** → a blocking
    `bash` call to `role-bridge.sh` (S1/S2) or `bridge-fanout.sh` (S4), per § Dispatch below.
  - "Agent tool / dispatch a subagent" **inside superrun** → superpowers' Pi mapping
    (`subagent` tool from `pi-subagents` when present, `async: false`, one child per call;
    otherwise SDD's sequential fallback). Role pins ride the generated agent definitions (§4).
  - `CronCreate`/`Monitor`/`AskUserQuestion` → do not exist; never attempt.
- Model-name guard in the generated `init`: a resolved `SUPER_MODEL_*` value that is a Claude tier
  or `claude-*` ID, or a `gpt-*`/`codex*` name **without** a harness prefix, WARNs and is treated
  as bridged-to-its-inferred-harness only if that harness's CLI is present, else `inherit`. The
  Pi-native domain is exactly one `/`. Effort guard: `off|minimal|low|medium|high|xhigh|max`.
- `--check` mode, as the other build scripts.

### Dispatch rules (the `pi-only` blocks)

**superagent SKILL.md — Subagent dispatch (S1, S2).** Both heavy skills run as their own
`pi -p` (or foreign CLI) process via the bridge from a blocking `bash` call with the longest
timeout the tool accepts:

- superplan: write the dispatch prompt to a temp file; run
  `"$SUPERAGENT_BRIDGE" --harness <h> --model <m> --effort <e> --tools planner --cwd <primary root> --prompt-file "$f" --role planner`
  where `<h>/<m>/<e>` resolve from `SUPER_MODEL_PLANNER`/`SUPER_EFFORT_PLANNER` (the harness is
  `pi` when the value is native). The stdout is the Final Report.
- superrun: identical to the Claude 0.5.1 rule with `--tools executor`.
- A `BRIDGE-FAILED` / non-zero exit is the crashed-dispatch case (retry once, then the crash-recovery
  mapping: restore the ready status, release the lock, end the tick).

**superloop L7 Rung 1 (S4).** One `bash` call to `bridge-fanout.sh` with three prompt files; the
`SUPER_PANEL_AGENT_TYPE` key is ignored on Pi (no agent types; WARN in `init`). Two-or-more
failed panelists ⇒ Rung 2, as today.

**superrun Model policy (S3).** On Pi:
- If the `subagent` tool is available: dispatch each SDD role with `agent: super-<role>` (the
  definition `init` generated, §4), `async: false`, and no model override on the call — the pin
  rides the definition. `BRIDGE-FAILED` from a relay definition is the crashed-child case.
- If it is not available: follow SDD's sequential fallback; the role model/effort pins are
  **not applied** (the work runs on the executor's own model). Record this in the closeout
  report's findings so the operator can see the degraded mode.
- Never launch background/parallel `pi-subagents` runs from superrun.

## 4. Config, `init`, and agent definitions

### `templates/superenv.default` (canonical) and `pi/templates/superenv.default` (generated)

- `SUPER_HARNESS` comment: `claude | cursor | codex | pi`.
- Effort-domain comment for `pi:` roles: `off|minimal|low|medium|high|xhigh|max`.
- New key `SUPER_PI_SUBAGENTS=recommended` — `recommended | required | off`.
  `recommended` (default): `init` WARNs if `pi-subagents` is missing or `<0.58.0`; S3 degrades.
  `required`: `init` ABORTs instead (operators who never want silent sequential SDD).
  `off`: never generate agent definitions, never use the tool even if installed.
  Ignored on other harnesses.
- Generated Pi defaults: `SUPER_HARNESS=pi`; every `SUPER_MODEL_*` key `inherit` (Pi's
  settings default — the Cursor build's shape, since no Pi model string is a safe universal
  default); efforts keep the shipped medium/high/xhigh worker set and `inherit` for dispatch roles
  (all valid Pi levels). `SUPER_BRIDGE_RELAY_MODEL=inherit` (only S3 relays use it on Pi).

### `superagent:init` (canonical skill, `pi-only` blocks)

Prerequisites on the Pi build:
- `pi` binary — ABORT with install hint if missing.
- `pi list` includes superpowers — WARN with `pi install git:github.com/obra/superpowers` if not
  (a loop without superpowers cannot run superrun; the tick would fail loudly at S2).
- `pi-subagents` version (from `pi list` or the package's `package.json` under
  `~/.pi/agent/npm/` / `.pi/npm/`): per `SUPER_PI_SUBAGENTS` above.
- For every role bridged to another harness: that CLI on PATH (existing rule).
- Auth: `pi auth check --provider <p>` for each distinct provider named by a `pi:` role — WARN.

Validation: `pi:` model values must contain exactly one `/`; efforts in the widened domain;
`SUPER_PANEL_AGENT_TYPE` WARN "ignored on Pi"; `SUPER_PI_SUBAGENTS` enum.

### Role agent definitions (S3 only)

Generated only when `pi-subagents` is present and `SUPER_PI_SUBAGENTS != off`, into the agent
directory `pi-subagents` reads for the project (probe P3 fixes the path; the `docs/agents.md`
reference is the source of truth — the template records it as `<agents-dir>`):

- Native `pi:` role → `templates/super-role-agent.md` rendered with `model: <provider>/<id>`,
  optional `thinking: <e>`, `tools: read,edit,write,bash,grep,find,ls`, and `inheritGlobalContext`
  left at its ≥0.58 default (false). No model allow-list, so the definition's own model is always
  admissible.
- Foreign-harness role → `templates/super-role-bridge-agent.md` rendered as a `pi-subagents`
  agent: `tools: bash`, `model: SUPER_BRIDGE_RELAY_MODEL` (or omitted for `inherit`), body = the
  relay instructions (already harness-neutral: "Bash" → "the `bash` tool" substitution). The
  haiku short-circuit caveat carries over verbatim — a weak relay model answers instead of relaying.
- Stale-delete rule unchanged. On Pi with `pi-subagents` absent, `init` generates nothing for S3
  and says so.

### Docs

- `README.md`: Pi harness section (install, superpowers package, `pi-subagents` recommendation +
  version floor, `--approve` rationale, degraded-S3 note); role table gains the Pi row for `planner`
  tools; `bridge-fanout.sh` mention under L7.
- `scripts/README.md`: `bridge-fanout.sh`, `build-pi-skills.sh`, `pi-smoke.sh`.
- `CHANGELOG.md` 0.6.0; `.claude-plugin/plugin.json` version bump.

## 5. Verification

`scripts/pi-smoke.sh` (neutral workspace, numbered assertions). Probes first — each decides a
design detail and is recorded in `pi/README.md` with the CLI/package version it was run against:

- **P1** `pi -p` exit status on a failed turn (bad model id): non-zero ⇒ bridge exit 3; zero with
  empty output ⇒ exit 4. Sets the bridge's documented mapping.
- **P2** `pi -p --skill pi/skills` in a neutral cwd: the session can `read` and follow
  `superagent/SKILL.md`, and superpowers skills are listed (package installed).
- **P3** (`pi-subagents` present) `subagent` with `async:false`: (a) returns the child's final
  output as the tool result; (b) a definition's `model: provider/id:level` is honoured (assert via
  the child's self-reported model); (c) a child may itself run a blocking `subagent` and get the
  grandchild's result (nested foreground wait) — **this is the probe that could later promote
  `pi-subagents` to the S1/S4 path; a failure changes nothing in this design**; (d) the agents
  directory path. Skipped, not failed, when the package is absent.
- **P4** `--tools read,edit,write,bash,grep,find,ls` in `-p` mode excludes an extension tool
  (`subagent` absent from the child's toolset) and the executor set (no flag) includes it.

Then the tests:

- **T1** bridge echo → pi with `--tools role`, `--approve`, `--no-session`, `SUPERAGENT_PI_SKILLS`
  set (extends the 0.5.0 T4).
- **T2** `bridge-fanout.sh` with three echo prompts: ordered framed output, exit 0; one prompt that
  sleeps past `--timeout`: killed, framed as failed, exit 3.
- **T3** bridge → pi with `--model inherit --effort low` passes `--thinking low` (no warning).
- **T4** one real tick end-to-end on a throwaway loop file with `SUPER_HARNESS=pi`: status
  transitions, lock released, skills loaded via `--skill`.
- **T5** relay definition round trip under `pi-subagents` (pi→codex): the generated
  `super-implementer` relay returns `RELAY-OK` and leaves an `implementer-*.log` (the RELAY-PROVEN
  contract from bridge-smoke T6). Skipped when the package is absent.
- **T6** `build-pi-skills.sh --check` clean; the other three build scripts still `--check` clean
  after learning to drop `pi-only`.

Known gaps to carry in `pi/README.md` until exercised: no multi-tick loop driven to DONE on Pi;
S3 with `pi-subagents` not run end-to-end inside a real superrun; `pi-subagents` verified only at
the floor/tested versions named above.

## Error handling summary

- Unknown `SUPER_HARNESS`, malformed `pi:` supervisor model, bad `SUPER_PI_SUBAGENTS`: fail loud
  before invoking anything (exit 6 / 8 / 8).
- Missing `pi` binary: exit 5 via `ensure_cli_bin`. Missing Pi build: exit 7.
- Bridged supervisor: exit 11 (unchanged).
- `pi -p` failure in the tick: non-zero tick exit, standard log framing; P1 fixes the value.
- Bridge failures at S1/S2: crashed-dispatch path (retry once, then crash-recovery mapping).
- Fan-out: one failed panelist tolerated; two or more ⇒ Rung 2 (existing L7 rule); timeout ⇒
  failed panelist.
- S3 without `pi-subagents`: not an error — degraded mode, WARNed at `init`, noted in the closeout.
  With `SUPER_PI_SUBAGENTS=required`: `init` aborts.

## Decisions taken in this spec (for review)

1. Hybrid dispatch as described; `pi-subagents` recommended, floor `>=0.58.0`, not required.
2. Plugin skills delivered by `--skill`, not by package install; the `pi/` tree is still a valid
   package for interactive use.
3. The tick and every bridged Pi child pass `--approve` (unattended loop on an operator-chosen
   repo; Cursor `--trust` parity).
4. Pi effort domain widened to `off…max` on every harness's handling of `pi:` roles.
5. New `SUPER_PI_SUBAGENTS` key rather than overloading an existing one.
6. `bridge-fanout.sh` is a new generic script rather than three ad-hoc background calls in skill
   text, so the timeout/framing contract is testable.
7. No commit of this spec yet — review first.
