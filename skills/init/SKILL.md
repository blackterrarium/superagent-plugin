---
name: init
description: Bootstrap a repository for the superagent plugin — verify prerequisites, create the .superenv config, create and seed the goal vault if absent, and add the loop-status gitignore entry. Idempotent; safe to re-run. Run this once per repo before supergoal/superagent.
---

# superagent:init — repo bootstrap

Prepare the current repository to run the superagent skill family. Every step is
idempotent: report what was **done** vs **already present**; never overwrite existing
files. Finish with a summary table of step → done/skipped.

Invoke this skill explicitly as `superagent:init` — a built-in `init` skill (CLAUDE.md
authoring) ships unscoped in most sessions, so the bare name `init` is ambiguous the
moment both are available.

## Repo configuration (.superenv)

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${CLAUDE_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' .superenv "${CLAUDE_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
(checking the env var first). A repo with no `.superenv` runs on the shipped defaults —
which is exactly the case Step 2 below fixes by creating one.

## Step 1 — Prerequisite checks

1. `git rev-parse --show-toplevel` succeeds — else ABORT: "init must run inside a git
   repository."
2. The `superpowers` plugin is resolvable (its skills, e.g. `superpowers:writing-plans`,
   appear in the available-skills list). If not: WARN with install instructions
   (`/plugin marketplace add obra/superpowers-marketplace`, `/plugin install superpowers`)
   — planning skills (`supergoal`, `superplan`) work without it, but `superrun` requires
   `superpowers:subagent-driven-development` to execute a plan and will refuse.
3. `gh auth status` succeeds — else WARN (PR-based flows need it; planning artifacts are
   drafted either way, but `superauthor`'s A7 commit-and-merge step and every CI/PR
   operation in `superplan`/`superrun` need it). On a macOS host, a sandboxed `gh auth
   status` can fail even when `gh` is actually authenticated, because `gh` needs keychain
   access the tool sandbox blocks — see `SUPER_GH_DISABLE_SANDBOX` in
   `${CLAUDE_PLUGIN_ROOT}/templates/superenv.default`. If the check fails on macOS, note
   that possibility rather than reporting a bare WARN.
4. Informational: external (unattended) mode needs a Linux host with systemd user timers
   (crontab fallback documented in
   [scripts/README.md](../../scripts/README.md#cron-fallback-instead-of-systemd)). Run
   `uname -s` and say which this host is — planning-only usage (`supergoal`/`superplan`)
   is host-independent; only `superagent-external`'s systemd path is Linux-specific.

## Step 2 — Config

If `<repo-root>/.superenv` does not exist, copy
`${CLAUDE_PLUGIN_ROOT}/templates/superenv.default` to `<repo-root>/.superenv` (keep the
comments — the repo edits knobs in place). If it exists, leave it untouched and report
any `SUPER_*` keys the shipped default defines that the existing file lacks — diff the
key names (`grep -oE '^SUPER_[A-Z_]+='` on each file) rather than the full lines, since
an intentionally edited value is not a gap. This is informational only: a missing key
falls through to the plugin default per the resolution order above.

## Step 3 — Vault

Resolve `SUPER_GOAL_ROOT` per the resolution order above (shipped default `vault`; a
worked example from the originating repo sets it to `vault/network-compose`). If
`<repo-root>/<SUPER_GOAL_ROOT>` does not exist: create it and copy
`${CLAUDE_PLUGIN_ROOT}/templates/vault-root.md` to `<SUPER_GOAL_ROOT>/root.md`. If the
directory exists (with or without a `root.md`), touch nothing — `supergoal` creates goal
folders under it and expects the root to already be in place, which is exactly what this
step guarantees once.

## Step 4 — Gitignore

Resolve `SUPER_LOOP_STATUS_DIRNAME` per the resolution order above (shipped default
`loop-status`). Append the line `<SUPER_GOAL_ROOT>/**/<SUPER_LOOP_STATUS_DIRNAME>/` to
`<repo-root>/.gitignore` unless an identical line is already present (create
`.gitignore` if absent). This is the exact pattern `superloop`'s L1 clause documents as
gitignored local-only state (worked example: `vault/**/loop-status/`) — every loop-status
file `superagent`/`superagent-external` write must never be tracked or swept into a
docs-only PR commit.

## Step 5 — Landing

init only prepares files — it never commits. Tell the user what to commit
(`.superenv`, the vault seed, `.gitignore`) and remind them to follow the repo's own
change discipline: if `SUPER_PROTECTED_MAIN=true` (the shipped default), that means a
feature branch + PR, same as every `superauthor`-driven skill's own A7 commit step.
