# Git-free operating mode

Status: implementation design for the requested planning work; no implementation performed.

## Goal and configuration

Make GitHub a recommended integration workflow, not a prerequisite for Superagent. Preserve
planning, execution, review, evaluation, repair, scheduling, and closeout in ordinary directories.

```bash
SUPER_GIT_MODE=github  # github | none; default github
```

The key follows existing precedence: process environment > project `.superenv` > packaged default.
Missing means `github`; empty or unknown values are configuration errors. `none` disables all
Superagent-managed git commands, GitHub CLI/API operations, credential discovery, worktrees,
commits, pushes, PRs, merge/sync gates, and GitHub CI polling, for both code and vault artifacts.
An existing `.git` directory is left untouched. No implicit fallback on authentication failure.

This is a workflow setting, not a network sandbox. Model authentication, dependencies, user
application networking, and unrelated research are unaffected. An acceptance check that itself
requires git/GitHub cannot be silently skipped or rewritten: report the incompatibility for an
explicit acceptance change. Do not evade the mode using absolute git paths, libraries, or curl.

`SUPER_TEST_EVIDENCE=ci` with `none` is an error before execution. GitHub-only settings such as
`SUPER_CI_GATE`, protected-main, branch style, merge method, and finishing handoff are inapplicable
in `none`; their shipped defaults must not require additional user configuration. Local tests and
reviews remain mandatory. Keep all harness/model settings and current default sandbox policy.

## Project discovery and initialization

Introduce shared context resolution used by scripts and prescribed by every skill:

1. An explicit `REPO` identifies the project. Canonicalize it physically and load its configuration.
2. Otherwise find the nearest ancestor `.superenv`. Resolve the mode with environment precedence.
   In `none`, that directory is the project root, even if it contains git metadata.
3. With environment `SUPER_GIT_MODE=none` and no ancestor config, use the current directory only
   for initialization; other commands require explicit `REPO` or an ancestor `.superenv`.
4. Only when no local-mode selection has been found may the GitHub path use git discovery.
   Preserve primary-checkout configuration for linked worktrees, including reloading that config
   after discovering the primary root. Explicit local-mode invocation from a linked worktree uses
   that directory as its independent project unless `REPO` explicitly identifies the primary root.

`init` in an unconfigured non-repository directory offers GitHub (recommended) or local operation
before requiring git. The equivalent unattended entry is `SUPER_GIT_MODE=none` at init. Write the
chosen mode to `.superenv`. GitHub mode retains existing prerequisites and worktree behavior.

Local init creates a normal internal/external vault, role assets, and configuration. It does not
create git metadata, `.gitignore`, or `.git/info/exclude`; `--local-only` is redundant and reported
as such. Keep existing vault containment checks and refusal of home/filesystem-root vault targets.
Persist the physical project root in scheduler registration, because an external vault cannot
identify its code directory by walking ancestors. Lifecycle tools consume that registration.

## Persistence and completion

All authoring and closeout skills have an explicit local path. Artifacts are saved at their normal
paths, reopened and verified, then parent progress advances. Retain confirmation gates, acceptance
agreements, repair history, predecessor/successor identity, review gates, and model-role dispatch.
Interpret persistence as durable files, not as git tracking. L5 verifies files and receipts in
local mode; L6 does not integrate a PR. Guard duplicated commit recipes, not just shared A7.

Local leaves finish with `completed-local`. A closeout receipt identifies the root/leaf, mode,
changed files (including deletions), local command results and evidence paths, review outcomes,
acceptance coverage, outstanding obligations, and timestamp. PR/commit fields say
`N/A (SUPER_GIT_MODE=none)`. A status label or an existing report alone never proves completion.
Ancestors roll up only after every active descendant has valid local completion evidence or an
authorized disposition. C9 audits actual descendants and unresolved repair obligations. Delayed
predecessor closeouts cannot complete successors. `completed-local` is not merge evidence in
GitHub mode. Preserve existing `completed-and-merged` semantics there.

For review without git diff, capture the task's before-state and compare file contents, additions,
deletions, and executable bits against the after-state. Reuse the snapshot helper. Reports name
the reviewed baseline and resulting snapshot; do not require old file hashes to remain identical
after an authorized later task changes them. Final acceptance checks apply to the final workspace.
Snapshots support inspection and evidence, not automatic rollback or automatic overwriting.

## Shared workspace ownership

Without worktrees, local execution edits the project directly. Serialize Superagent writers with
an atomic directory lock at `<project>/.superagent-runtime/workspace.lockd`. Keep existing per-goal
L3 locks; project lock first, then goal lock. Hold the project lock for a mutating tick/standalone
operation, including its review and closeout. Idle polling, status, and stop remain available.
Acquire an external vault lock at `<vault>/.superagent-runtime/workspace.lockd` as well when writing
it. Acquire multiple physical-root locks in lexical order to avoid deadlocks across shared vaults.

Record a unique token, live owning process, acquisition time, and operation/loop path. Nested
executor and planner processes inherit ownership and validate token and owner; they do not create
a second writer. Release only owned locks. A live owner is never stolen solely because it is old.
A busy workspace yields without incrementing work or declaring failure. Recover a dead owner only
after its supervised process group is gone; an ambiguous/orphaned child keeps the lock blocked.
Force-stop may reap only the stopped operation's verified locks. Initialization of the lock itself
uses atomic mkdir and must not create an unlocked check-then-write race.

This serializes Superagent processes, not arbitrary editors. Detect source changes during snapshot
capture and refuse a completion claim on inconsistent evidence. Do not promise isolation from
uncooperative external writers or automatic recovery of lost uncommitted work.

## Evaluation without commits

Retain current git worktree evaluation in `github`. Add local snapshot evaluation in `none`:

```text
supereval.sh PROJECT --repo ROOT --out RESULTS --keep-workspace
```

`--commit`, `--worktree`, and `--keep-worktree` retain their GitHub meanings; reject them in local
mode with the local command shown above. Capture a temporary snapshot outside source/vault roots,
run setup and command checks there, and keep that same workspace for judged evaluation. Freeze
the evaluation specification and required acceptance inputs for the run as well. Preserve
command verdicts, timeouts, acceptance-source validation, and judged-objective semantics.

Use Python 3.9 standard library for copying and manifests. Copy regular files and executable bits,
including untracked source files and installed dependencies. Exclude `.git` entries, `.env` and
`.env.*`, `.superagent-runtime`, internal vault contents, and the output/snapshot destination.
Do not invent a gitignore parser. Relative symlinks that stay within the captured tree can be
preserved; reject external, absolute, dangling, or excluded-target links and special files with
their exact paths. Required excluded inputs must be supplied through setup/environment or the
run fails explicitly. No silent incomplete snapshot. Read model credentials from the original
project through the existing launch path; never include their values in manifests/reports.

Store a sorted manifest of relative paths, kind, mode, content SHA-256 or symlink target. Verify
source membership and contents before/after capture; fail if they changed. The pre-setup manifest
digest is `snapshot:<sha256>`; capture post-setup/test state separately because tests may write.
Record manifest path, workspace path, and setup result. The report and iteration ledger use a
mode-neutral source identity (`commit:<sha>` or `snapshot:<sha256>`), preserving old ledger reads.
Cleanup may remove only a helper-owned temporary workspace with a matching marker/token.

## Existing goals and mode changes

Persist `git_mode` and `project_root` in new root plans and loop metadata. Legacy unmarked goals
mean `github`. Mode is an execution contract, not a mutable per-tick preference: compare effective
configuration to recorded mode before any git/auth action or implementation dispatch.

A mismatch parks on `WAITING FOR INPUT` (or reports the same actionable error for standalone
commands) without contacting GitHub. Version one provides no automatic in-flight migration.
The operator can restore the original setting to finish/resolve the old goal, or start a new
local goal carrying the remaining scope and explicit predecessor disposition. Completed history
is preserved. Local goals cannot be silently promoted to merged goals by changing `.superenv`.

## Acceptance requirements

| ID | Requirement |
|---|---|
| GF-01 | One key enables git-free operation; absent key preserves GitHub behavior and precedence. |
| GF-02 | Init and nested-directory commands work without a repo/git/gh, for internal and external vaults. |
| GF-03 | Start/tick/status/answer/stop/force-stop use no git, gh, token discovery, or GitHub API in local mode. |
| GF-04 | Planning, implementation, reviews, repairs, and closeout work with durable local evidence. |
| GF-05 | Local completion reaches DONE only after acceptance and descendant/repair verification. |
| GF-06 | Concurrent goals/shared vaults cannot create multiple Superagent writers; crash recovery preserves ownership. |
| GF-07 | Evaluation uses a stable snapshot and honest identity, preserving command and judged checks. |
| GF-08 | CI-only evidence conflicts and existing-goal mode mismatches stop before prohibited operations. |
| GF-09 | Canonical, Codex, Cursor, and Pi distributions carry the setting, helpers, and local instructions. |
| GF-10 | GitHub default, direct-merge configuration, and external-vault behavior retain existing coverage. |

No local-git-only third mode, provider abstraction, automatic rollback, or existing-goal conversion
command is included. Git operations used to develop/release this plugin are outside the runtime
setting; this planning request itself authorizes no implementation, commit, push, or PR.
