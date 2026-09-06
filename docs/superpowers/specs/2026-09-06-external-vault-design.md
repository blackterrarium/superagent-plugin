# External vault — `SUPER_GOAL_ROOT` outside the repository

**Date:** 2026-09-06 · **Status:** approved design · **Ships as:** 0.7.1 · **Prerequisite for:**
coding-loop Stage 2 (dogfooding superagent on its own checkout without contaminating it).

## Scope

Today the goal vault (`SUPER_GOAL_ROOT`, shipped default `vault`) is a repo-relative directory
inside the git checkout. Four skills commit into it via pull request (superauthor A7), the loop's
sync gate refreshes it with `git pull`, and init writes its loop-status ignore pattern into the
repo's `.gitignore`. That makes it impossible to run supergoal / superagent on a repository whose
history must not carry the plan tree — the superagent-plugin checkout itself being the motivating
case.

This change lets `SUPER_GOAL_ROOT` be an **absolute or `~`-prefixed path**. That value selects
**external mode**: the vault lives outside the checkout as **its own git repository**, and every
vault artifact is committed there instead of into the code repo. A relative value keeps today's
behaviour byte-for-byte. Alongside it, `superagent:init` gains a `--local-only` flag so that a
dogfooded checkout has nothing at all to commit.

Out of scope: multi-machine vault sharing beyond "pull when a remote exists"; moving `.superenv`
or the generated `.claude/agents/super-*.md` out of the checkout; changing how `launch.sh`
derives the repo root.

## Configuration and resolution

No new key. In `templates/superenv.default` the `SUPER_GOAL_ROOT` comment documents both forms:

```
SUPER_GOAL_ROOT=vault   # goal folders land at <SUPER_GOAL_ROOT>/<STAMP>-<slug>/. Relative: inside
                        # the checkout (default). Absolute or ~/…: EXTERNAL vault — its own git
                        # repo outside the checkout; vault artifacts are committed there, never here.
```

`SUPER_PROJECT_DIRNAME` and `SUPER_LOOP_STATUS_DIRNAME` are unchanged; they nest under the
resolved root in both modes.

**Resolver.** `scripts/_common.sh` gains two functions:

```bash
# vault_is_external — true when SUPER_GOAL_ROOT is absolute or ~-prefixed
vault_is_external() { case "${SUPER_GOAL_ROOT:-vault}" in /*|"~"|"~/"*) return 0 ;; *) return 1 ;; esac; }
# vault_root <primary-root> — absolute goal root in either mode (no trailing slash)
vault_root() {
  local primary="${1:?vault_root needs the primary checkout root}" v="${SUPER_GOAL_ROOT:-vault}"
  case "$v" in
    "~")   printf '%s\n' "$HOME" ;;
    "~/"*) printf '%s/%s\n' "$HOME" "${v#"~/"}" ;;
    /*)    printf '%s\n' "${v%/}" ;;
    *)     printf '%s/%s\n' "$primary" "${v%/}" ;;
  esac
}
```

Skills get the same logic as a canonical **Vault root** block placed directly under the existing
`.superenv` resolver block, in every skill that composes a vault path (init, superloop, superagent,
superagent-external, supergoal, superplan, superfinish, superprd). Its wording:

> Resolve `SUPER_GOAL_ROOT`. If it starts with `/` or `~`, the vault is **external**:
> `<vault_root>` is that path (with `~` expanded) and the vault is its own git repository.
> Otherwise `<vault_root>` is `<primary_root>/<SUPER_GOAL_ROOT>`. Every goal folder, project
> folder, loop-status file and lock derives from `<vault_root>`; never join `SUPER_GOAL_ROOT`
> onto the checkout root by hand.

`superagent-stop`, `superagent-force-stop` and `superagent-monitor` take an absolute `<PLAN.md>`
or a slug and never compose vault paths; they change only in their prose ("the plan may live in an
external vault").

**Validation.** init's `.superenv` lint gains one shape check: `SUPER_GOAL_ROOT` must be a
non-empty path without a trailing `/`, and when absolute or `~`-prefixed it must not resolve to
inside the checkout (that is just internal mode spelled confusingly — report as a finding, do not
abort). Relative values containing `..` are a finding too.

## Commit discipline (superauthor A7)

A7 gains a **target repo**, resolved once at the top of the clause:

- **internal mode** — the code repo; the skeleton is unchanged (feature branch + PR when
  `SUPER_PROTECTED_MAIN=true`, direct commit when `false`).
- **external mode** — the vault repo at `<vault_root>`. The **direct-commit variant always
  applies**, regardless of `SUPER_PROTECTED_MAIN` (that key describes the code repo, not the
  vault). All git commands run as `git -C "<vault_root>" …`; the `git add` paths are the
  caller's files made **relative to `<vault_root>`**; the commit subject keeps the caller's text
  (the `[skip ci]` tag is harmless and stays for uniformity); `git -C "<vault_root>" push` runs
  **only if** `git -C "<vault_root>" remote get-url origin` succeeds, otherwise the commit stays
  local and that is not an error. No branch, no `gh`, no PR.

A8's Final Report line `**PR:** <url> (merged)` becomes `**Commit:** <short-sha> in <vault_root>`
in external mode. Every caller that prints A8 (supergoal, superplan, superfinish, superprd) uses
the same substitution; nothing else in their reports changes.

Callers change only in that their `git add` lists are expressed as vault-relative paths resolved
through `<vault_root>` — the file lists themselves are unchanged. `superrun` is unaffected: its
code PR never contained vault files, and its closeout is superfinish's commit.

Progress-table `PR` cells written by supertraverse / superfinish keep recording the **code** PR
number for executed plans; in external mode a planning row's PR cell is left blank (there is no
PR for a vault-only commit).

## Loop chassis (superloop)

**L1 — loop-status file.** The path is `<vault_root>/<goal>/<SUPER_LOOP_STATUS_DIRNAME>/<date>-<slug>.md`.
The "always in the primary checkout, never in a worktree" paragraph is rewritten: in internal
mode the reasoning stands (root at `primary_root`); in external mode the vault is the same
directory from every worktree, so no rooting step is needed. The `master_plan:` frontmatter
field is **repo-relative in internal mode (unchanged) and absolute in external mode**; its
comment says so. The lock directory is derived from the loop file's own directory and needs no
change. The gitignore sentence moves: in internal mode the pattern lives in the code repo's
`.gitignore` (as today); in external mode it lives in `<vault_root>/.gitignore` as
`**/<SUPER_LOOP_STATUS_DIRNAME>/`, which also covers the `.<loop>.lockd` and `.ci-stale` markers
that sit beside the loop file.

**L2 — bootstrap/resume.** The loop-file lookup and lazy first-write are rooted at
`<vault_root>/<goal>/<SUPER_LOOP_STATUS_DIRNAME>/` (internal: under `primary_root`, as today;
external: the vault), and the input `<PLAN.md>` is repo-relative (internal) or absolute
(external), the form `launch.sh` stores in `master_plan:`.

**L5 — sync gate.** `sync_main()` on the code repo is unchanged; code PRs still need it. A second
mechanical step, `sync_vault()`, runs immediately after it in external mode — in the driver's
pre-dispatch gates (step 1 of both states) as well as the post-dispatch ones:

1. `git -C "<vault_root>" remote get-url origin` fails → **no remote → no-op**, synced.
2. `origin` exists but the branch has no upstream → `git -C "<vault_root>" push -u origin HEAD`;
   failure → STOP and escalate.
3. Otherwise `git -C "<vault_root>" fetch origin`, then the same left-right count comparison
   against the vault's current branch: equal → synced; behind only → `merge --ff-only`; ahead or
   diverged → in external mode **ahead is normal** (local commits not yet pushed because a push
   failed) — attempt `git -C "<vault_root>" push`; if that fails or the branches diverged →
   STOP and escalate exactly as `sync_main()` does.
4. No uncommitted **tracked** changes in the vault repo (`git -C "<vault_root>" status
   --porcelain --untracked-files=no` empty) → else STOP and escalate.

**Be-sure verification** distinguishes the two kinds of reported artifact. Internal vault: both
kinds are checked with today's form, `git -C "$primary_root" ls-files --error-unmatch
<repo-relative path>`. External vault: code paths as before; a vault artifact is reported as an
absolute path plus `**Commit:** <short-sha> in <vault_root>` — strip the `<vault_root>/` prefix and
check `git -C "<vault_root>" ls-files --error-unmatch <vault-relative path>`, confirming the commit
with `git -C "<vault_root>" cat-file -e <short-sha>`.

**L6** is unchanged. The `superagent` driver skill's per-branch "present and tracked on local
`main`" checks after superplan / superrun use the same two-kind rule.

## Scripts

- **`scripts/_common.sh`** — `vault_is_external`, `vault_root` (above).
- **`scripts/launch.sh`** — replaces the hard rejection of a plan outside the checkout: a plan is
  accepted if it lies under `$REPO` (repo-relative `master_plan:`, as today) **or** under
  `$(vault_root "$REPO")` (absolute `master_plan:`); anything else is still rejected with the
  existing message extended to name both accepted roots. The existing-loop scan compares
  `master_plan:` to whichever form was stored.
- **`scripts/stop.sh` / `scripts/force-stop.sh`** — already fall back to the absolute path when
  the plan is outside the repo; they need tests, not changes.
- **`scripts/superagent-tick.sh`**, `install-timer.sh`, `answer.sh`, `status.sh`,
  `console-watch.sh`, `uninstall-timer.sh`, `bootstrap.sh` — the loop file is an absolute path in
  the per-goal env file; no change.
- **`scripts/prd-lint.sh`** — unchanged. `superprd` step 4 and step 6 always invoke it with
  `PRD_LINT_REPO_ROOT="<primary_root>"`, so an external project folder resolves `repo-file` /
  `entry-point` locators against the code repo.

## `superagent:init`

**Step 4 — Vault.** Resolve `<vault_root>`. The three existing cases (create + seed; seed
`root.md` into existing; already present) apply at that path. In external mode, additionally:
unless `<vault_root>` is already its own repository — `git -C "<vault_root>" rev-parse
--show-toplevel` succeeds and, resolved physically, equals `<vault_root>` — run
`git -C "<vault_root>" init -q` (a vault sitting inside some other repo's tree gets its own
nested repo rather than committing into the enclosing one); ensure
`<vault_root>/.gitignore` contains the line `**/<SUPER_LOOP_STATUS_DIRNAME>/` (same newline
guard and idempotent check as Step 5); then, if the vault repo has no commits yet
(`git -C "<vault_root>" rev-parse --verify HEAD` fails), commit `root.md` and `.gitignore` with
subject `chore(vault): seed goal root`. This is a **deliberate, narrow exception** to "init never
commits": it is the plugin-owned vault repo, never the user's code repo, and only its very first
commit. The summary table gains a row `Vault repo` — `initialised` / `already a git repo`.

**Step 5 — Gitignore.** In external mode the loop-status pattern is **not** written to the code
repo (it lives in the vault). The `.env` line is still written. With `--local-only` (below) the
destination changes; the entries do not.

**`--local-only` flag.** Every line Step 5 would append to `<repo-root>/.gitignore` is appended
to `<repo-root>/.git/info/exclude` instead (`.git` resolved via `git rev-parse --git-common-dir`
so worktrees share it; same newline guard; same idempotent check), and two more lines are added
there: `.superenv` and `.claude/agents/super-*.md`. `.gitignore` is not touched. The flag is
recorded in the summary table (`Ignore target: .git/info/exclude`). Re-running without the flag
later does not remove the exclude lines (init never deletes).

**Step 6 — Landing.** Internal mode without the flag: unchanged. External mode: the vault seed is
no longer in the list to commit. With `--local-only`: the report states that nothing needs
committing, listing the excluded paths, and that the vault (external) or `.gitignore` (internal)
carries the loop-status pattern.

**Cursor / Codex / Pi builds** carry the same flag; the exclude path is harness-independent.

## Docs, builds, tests, version

- `README.md` (vault section, external-loop launch example), `scripts/README.md` (launch
  arguments, "plan may be an absolute path under the external vault"), and
  `docs/superagent-structure.html` (the vault box) describe both modes.
- `CHANGELOG.md` gains `## 0.7.1`; `.claude-plugin/plugin.json` and `marketplace.json` bump.
- `scripts/build-codex-skills.sh`, `build-cursor-skills.sh`, `build-pi-skills.sh` are re-run; the
  template change flows through the Paths block untouched.
- **New offline test `scripts/vault-external-test.sh`** (bash 3.2, no network, no `claude`):
  1. `vault_root` / `vault_is_external` on `vault`, `vault/sub`, `/abs/path`, `~/x`, `~`, and a
     trailing-slash value;
  2. `launch.sh --dry-run` accepts a plan under an external vault and prints an absolute plan
     path, still rejects a plan under neither root, and still accepts a repo-relative plan;
  3. `stop.sh` / `force-stop.sh` slug matching with an absolute `master_plan:` (registry env
     file pointed at a temp loop file);
  4. init's exclude routing is exercised by a shell-level fixture: given a temp repo, the
     documented append rules (newline guard, idempotency, exclude vs gitignore) are run as the
     skill text prescribes and the resulting files compared to expected.
  Existing testbenches that assert `<clone>/vault` (`bridge-test.sh`, `mix-e2e.sh`, `pi-e2e.sh`)
  are unchanged — they exercise internal mode.
- **Live acceptance (operator checklist, recorded in `vault-external-report.md`, gitignored):**
  in a throwaway clone with `SUPER_GOAL_ROOT=$TMPDIR/ext-vault`, run `superagent:init
  --local-only`, then `superagent:supergoal` with a one-line goal; assert `git status --porcelain`
  in the clone is empty and `git log` unchanged, `.git/info/exclude` holds the four entries, and
  the external vault repo has the seed commit plus the supergoal commit with exactly the goal
  folder's files.

## Compatibility

Every existing repo has a relative `SUPER_GOAL_ROOT`; for them nothing changes: same paths, same
PR flow, same gitignore line. External mode is opt-in per repo. A loop file written by 0.7.0 is
read unchanged. The only behavioural difference an internal-mode user can notice is the new init
summary rows and the `--local-only` flag.
