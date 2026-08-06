---
name: superauthor
description: Shared plan-authoring core — the no-execution rule, the plan-authoring standard, no-placeholders, generic self-review, standing authorization, findings capture, commit-and-merge-via-PR, and Final Report format. Invoked by plan-producing skills (supergoal, superplan) to avoid duplicate planning logic.
license: all rights reserved
---

# Superauthor

The single source of truth for the mechanics shared by plan-producing skills: how to **author a
planning artifact to the shared standard, self-review it, capture findings, commit and merge it via
a PR, and report** — without ever executing the planned work.

This is the authoring analogue of `supertraverse` (which owns plan-*tree navigation*). Like
`supertraverse`, superauthor is a **clause library**: the calling skill (e.g. `supergoal`) invokes it
via the Skill tool and carries out the clauses A1–A8 inline with its own file / Bash / Skill tools.
**Superauthor itself reads nothing, writes nothing, runs nothing, and commits nothing** — the **caller**
owns every read, write, and commit. The clauses define *how* the shared steps are performed; the caller
supplies the artifact-specific specifics:

- **(a)** the **goal folder** all output is written under;
- **(b)** the **artifact(s)** to author and where they route (which subfolder);
- **(c)** for A7 — the **branch prefix**, the **commit subject**, and the explicit **`git add` file list**;
- **(d)** for A8 — the **report lines** specific to what the caller produced.

Anything tree-specific (descent, a parent-seed reference, updating a parent's progress-report row,
ascending the tree) is **not** part of superauthor — a calling skill that participates in a plan tree
layers those on top of A1–A8 itself.

---

## A1 — The deliverable is the plan, and ONLY the plan

**The calling skill produces a planning artifact and a report, then stops. DO NOT execute, implement, or
begin any of the planned work.** Not one "trivial" step. Not "just scaffolding it." Not even in
auto-accept / `bypassPermissions` mode. Not even if the user seems eager or the work looks small.

A superauthor-driven skill **never** writes or edits source code, **never** runs tests or builds,
**never** creates worktrees, and **never** begins the planned work. Executing the plan is a separate,
later action the user invokes explicitly (e.g. `superrun`) —
it is **not** part of the authoring skill.

The one thing the skill *does* commit is **the planning artifacts themselves** (the plan documents and
any structural/`findings/` docs it wrote). Once written to the vault, the skill commits **only those
artifacts** and merges them to `main` via a pull request as its final action — **automatically, under
the user's standing authorization, without pausing to ask** (see A7). That is the sole commit — never
source code, never execution output.

| Thought | Reality |
|---------|---------|
| "Auto mode is on, so I'm cleared to start coding" | NO. Auto mode governs tool permissions, not scope. The deliverable is the plan. |
| "The first task is trivial, I'll just knock it out" | NO. Zero implementation steps. Ship the artifact and stop. |
| "I'll set up the worktree / branch for the planned work" | NO worktree and no branch for the *planned work*, and no source-code commits. (The artifacts are committed and merged via PR as the final step — that is the only commit.) |
| "The user will obviously want this run, I'll get a head start" | NO. Produce and commit the artifact, report, exit. Wait to be asked before executing. |

## Repo configuration (.superenv)

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${CLAUDE_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.superenv" "${CLAUDE_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
(checking the env var first, and anchoring at the primary checkout so worktrees resolve the same config). A repo with no `.superenv` runs on the shipped defaults.

## A2 — Authoring standard (REQUIRED)

**Author the plan yourself, directly, to the standard below.** This standard is the distilled
replacement for delegating *authorship* to `superpowers:writing-plans` — that skill is **no longer
invoked to produce the plan document itself** by any superauthor-driven caller; its
`docs/superpowers/plans/` save location and its "Execution Handoff" section do not apply here. Whether
the produced plan's own verification steps follow that skill's local-test TDD cycle or specify CI
pushes instead is governed by `SUPER_TEST_EVIDENCE` (see the **Verification-steps mode** bullet below).

Write for a skilled engineer with **zero context for this codebase**: name the exact files each task
touches, show the actual code, and state how the work is verified. DRY. YAGNI.

- **File structure first.** Before defining tasks, map which files will be created or modified and
  what each is responsible for — this locks in the decomposition. Prefer small, focused files with
  one clear responsibility and a well-defined interface; in existing code, follow the established
  patterns rather than restructuring beyond the task's scope.
- **Task right-sizing.** A task is the smallest unit that carries its own verification and is worth
  a fresh reviewer's gate. Fold setup, configuration, scaffolding, and documentation steps into the
  task whose deliverable needs them; split only where a reviewer could meaningfully reject one task
  while approving its neighbor. Each task ends with an independently verifiable deliverable.
- **Plan header.** Every implementation plan starts with:

  ```markdown
  # [Feature Name] Implementation Plan

  > **For agentic workers:** REQUIRED SUB-SKILL: use superpowers:subagent-driven-development
  > (normally reached via `superagent:superrun`) to implement this plan task-by-task. Steps use
  > checkbox (`- [ ]`) syntax for tracking.

  **Goal:** [one sentence describing what this builds]
  **Architecture:** [2–3 sentences about approach]
  **Tech Stack:** [key technologies/libraries]

  ## Global Constraints

  [The source material's project-wide requirements — version floors, naming rules, exact values
  copied verbatim, one line each. Every task's requirements implicitly include this section.]
  ```

- **Task structure.** Each task carries: a **Files** block with exact paths
  (`Create:` / `Modify: path:lines` / `Test:`); an **Interfaces** block — *Consumes:* what this
  task uses from earlier tasks (exact signatures), *Produces:* the names, parameter and return
  types later tasks rely on (a task's implementer sees only their own task; this block is how
  neighboring tasks stay consistent); and checkbox (`- [ ]`) steps whose code steps contain real
  code blocks.
- **Verification-steps mode is keyed by `SUPER_TEST_EVIDENCE`.** If `SUPER_TEST_EVIDENCE=ci`: authored
  plan steps specify CI pushes as the test evidence — the commit flag (if any), the lane it routes to,
  and the run id + conclusion as the pass criterion — following the CI-scheduling rules the caller
  supplies (queue-all batches, monitor-parked waits); never write `pytest` / `./run.sh` / build
  commands to execute on the host, and never instruct poll-loop CI waits in plan text. If
  `SUPER_TEST_EVIDENCE=local` (the shipped default): plan steps use the normal local test cycle per
  `superpowers:writing-plans`.
- **A mechanical gate belongs in a committed test, never in an unrun shell block.** If a plan step
  says "verify X before proceeding" and X is checkable by code, the plan's deliverable is **the test
  that checks X**, cited by name — not a snippet the executor is told to run and trust. A committed
  test is executed, reviewed, and maintained; a code block in plan prose is **none of those and is
  trusted anyway**, because plan text reads as authoritative. This applies with most force to a
  **STOP gate**: a wrong gate does not merely fail to catch a defect, it **halts a correct run**.
  Worked example — a T2.2.4 Task-0 STOP gate asserted `src.count('pool="train"') == 41` against a
  file where the string also appears in a docstring and a comment, so the true count is **43**. An
  executor obeying the plan literally would have halted a run that was entirely correct. If a gate
  genuinely cannot be a test (it inspects CI output, a PR state, or the host), write the exact
  command **and** the failure mode that makes it wrong, so the executor can tell a real trip from a
  broken probe.
- **Never size a test fixture as a multiple of the parameter under test.** A fixture whose dimensions
  are commensurate with the parameter lets a wholly wrong implementation satisfy every assertion.
  Worked example — a plan-mandated stratification test used two synthetic strata of **6** against
  `stride=3`; because 6 is a multiple of 3, an implementation that ignored stratification entirely
  passed all seven assertions. Unequal, non-commensurate sizes (4 and 6) fail it immediately. State
  the fixture's dimensions in the plan **with the reason they were chosen**, so an implementer does
  not "tidy" them back into round numbers. The general form: **a fixture must be able to distinguish
  the property under test from its most plausible wrong implementation** — write down what that wrong
  implementation is, and check the fixture separates them.

  > Both rules above exist because this class of defect is **self-concealing**: it produces green,
  > confident output. In one authoring-plus-review session it recurred **four times** — twice in the
  > plan text and twice in the reviewer's own throwaway verification regexes (one required a unit
  > word, one rejected sentence-final periods; each published a wrong count that had to be retracted).
  > Treat any ad-hoc regex or one-off count written to *check* a claim as unreviewed code on the
  > critical path: cross-check it against a second, differently-shaped extraction before quoting the
  > result.

**Author the draft to a scratch path OUTSIDE the goal folder** (e.g. `$TMPDIR/` or `.claude/scratch/`),
not into the goal folder. **Nothing is written under the goal folder (no plan file, no structural doc,
no `findings/` doc) until self-review (A4) passes** — at which point the scratch draft is written into
the vault automatically.

> The A2 standard applies to authoring a **plan**. Purely *structural* documents a caller may also
> write (e.g. a `goal-directives.md` layout guide) are not plans and are exempt from the plan-shaped
> parts of the standard. The caller states which of its outputs are plans.

## A3 — No placeholders

Every step must contain the actual content an engineer needs. These are **plan failures** — never write
them:

- "TBD", "TODO", "implement later", "fill in details"
- "Add appropriate error handling" / "add validation" / "handle edge cases"
- "Write tests for the above" (without actual test code)
- "Similar to Task N" (repeat the code — the engineer may read tasks out of order)
- Steps that describe what to do without showing how (code steps require code blocks)
- References to types, functions, or methods not defined in any task

## A4 — Generic self-review

**Review the written plan yourself, inline — not via a subagent dispatch.** The caller authored the
plan directly (A2), so nothing has pre-checked it — run the full checklist with fresh eyes:

1. **Spec coverage against the caller's source material** — skim each section/requirement of the topic.
   Point to a task that implements it; add a task for any gap.
2. **Placeholder scan** — search the plan for the A3 patterns. Fix every hit.
3. **Type/term consistency** — do the types, signatures, and names used in later tasks match what
   earlier tasks defined? A function called `clearLayers()` in Task 3 but `clearFullLayers()` in
   Task 7 is a bug.

If you find issues, fix them inline — no need to re-review the whole plan.

**Tree-specific self-review items are NOT part of A4.** Confirming a parent-seed reference, an updated
immediate-parent progress-report row, or an ancestor ascent applies only to a skill that inserts the new
plan into an existing plan tree — that skill adds those checks itself, after A4. A root-creating caller
(no parent, no tree above it) has none of them and runs A4 alone.

## A5 — Standing authorization: proceed without pausing

The user has granted **standing authorization** for a superauthor-driven skill to write its docs to the
vault and merge the artifact PR. **Do NOT pause to ask for approval, and do NOT present the draft and
wait for a "go" before writing.** After self-review, proceed directly — capture findings (A6), write the
docs into the goal folder, commit, and merge the PR (A7) — then report (A8). This is not waived or
re-enabled by auto-accept / `bypassPermissions` mode; it is the default behavior.

Do not print the full draft to chat up front. The user's single checkpoint is the **Final Report** (A8),
which clearly enumerates every file written this run.

## A6 — Capture findings

After self-review, identify any **findings** or new insights uncovered during the authoring phase —
e.g. a constraint discovered, a contradiction in the source material, a mechanism that does not work as
assumed, or a non-obvious fact a future planner would need.

Review the existing docs in the goal folder's **`findings/`** subfolder to decide whether each finding is:

- an **addition** — write it to a new doc in `findings/`, named `YYYY-MM-DD-hh_mm-<topic>.md` (today's date and the current UTC hour and minute), or
- a **revision** — update the relevant existing doc in `findings/`.

(These writes happen as part of the automatic write-out — after self-review, alongside the plan file. No
user confirmation is awaited.)

**Be extra certain of each finding.** If you are unsure whether a finding is correct, **do not include
it** — false findings are harmful to the goal. Only record what you have verified. If there are no
findings, record none.

## A7 — Commit and merge via PR (caller-parameterized)

After the artifact(s) and any `findings/` docs are written into the goal folder, commit those planning
artifacts and merge them to `main` via a pull request. **Merge the PR without asking the user for
confirmation** — the user has granted standing authorization (A5), so never pause before writing or
merging.

If `SUPER_PROTECTED_MAIN=true` (the shipped default), the default branch is a **protected branch**
(direct pushes are rejected), so this MUST go through a feature branch and a PR — merged per
`SUPER_MERGE_METHOD` (default `squash`) — even though it is docs-only. If `SUPER_PROTECTED_MAIN=false`,
a direct commit to the default branch is permitted instead.

**Scope of the commit: only the planning artifacts this run produced.** Add each with an explicit
`git add <path>`; **never `git add -A`** (the working tree may hold unrelated changes that are not yours
to commit). These are docs-only changes, so tag the commit subject `[skip ci]` to avoid firing CI on the
merge.

**The caller supplies three parameters:** the branch prefix, the commit subject, and the explicit
`git add` file list. Substitute them into this skeleton:

```bash
# from the repo root, with the artifact/findings files already written
BRANCH="<caller-branch-prefix>-$(date +%Y-%m-%d)"
git checkout -b "$BRANCH"
git add <file> [<file> ...]                       # caller-supplied explicit paths only — never git add -A
git commit -m "<caller-commit-subject> [skip ci]"
git push -u origin "$BRANCH"
gh pr create --title "<caller-pr-title>" \
  --body "<caller-pr-body>"
gh pr merge --squash --delete-branch          # plain --squash is the DEFAULT — do NOT reach for --admin
git checkout main && git pull --ff-only
```

Notes:
- `--squash --delete-branch` keeps history clean and removes the feature branch after merge.
- **Merge per `SUPER_MERGE_METHOD` (default `squash`). Pass `gh pr merge --admin` only if
  `SUPER_ADMIN_MERGE=true` — otherwise never.** Reaching for `--admin` when the key is unset or `false`
  buys nothing on a repo whose branch protection doesn't require it, and reliably **trips the harness
  security classifier**, which reads merge-over-red as a privileged override and denies it. If the plain
  merge is actually refused, escalate to `--admin` only when `SUPER_ADMIN_MERGE=true` permits it, and
  say in your report **why** it was refused.
- **`--delete-branch` can exit 1 with `fatal: '<branch>' is already used by worktree` — the PR still
  merged.** That failure is the *local* branch-delete step, not a permission rejection. Confirm with
  `gh pr view <n> --json state,mergedAt`; if it merged, delete the remote ref directly with
  `gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/<branch>` rather than re-running the merge.
- Capture the resulting **PR URL** (from `gh pr create` / `gh pr view --json url`) — report it in A8.
- Do **not** commit Anthropic/Claude attribution or `Co-Authored-By` trailers (repo policy).
- If `SUPER_GH_DISABLE_SANDBOX=true` (macOS hosts where `gh` needs keychain access to verify the
  TLS cert), all `gh` commands need `dangerouslyDisableSandbox: true`. If `false` (the shipped
  default), run `gh` normally.

**`SUPER_PROTECTED_MAIN=false` — direct-commit variant.** The skeleton above is the
`SUPER_PROTECTED_MAIN=true` (shipped-default) path. When `SUPER_PROTECTED_MAIN=false`, skip the
branch/PR machinery entirely and commit straight to the default branch — no `gh` calls at all:

```bash
# from the repo root, with the artifact/findings files already written
git add <file> [<file> ...]                       # caller-supplied explicit paths only — never git add -A
git commit -m "<caller-commit-subject> [skip ci]"
git push                                           # only if a remote exists
```

A repo with no remote simply keeps the commit local — `git push` has nothing to push to and that is
not an error; skip it rather than forcing a remote into existence.

## A8 — Final Report, then exit (caller-parameterized)

After the artifact is written, self-review is done, findings are captured, and the PR is merged (A7),
give the user a **single report** and then **exit the skill**. **Do not ask whether to execute the plan
and do not offer execution options** — a superauthor-driven skill never offers execution.

**This report is the user's single window into what the skill wrote — every file path created or
modified this run MUST appear here.** Include the merged **PR URL**, and call out any **CRITICAL finding**
(a contradiction in the source, a mechanism that does not work as assumed, a blocking constraint) under
its own bold ⚠️ line so it cannot be missed.

Generic shape — the caller fills in its artifact-specific lines (and may rename the heading to its own
skill):

```
## <skill> complete

**<primary artifact>:** <full path>      ← the most important line; always include it
**PR:** <url> (merged)

**Other files created/modified:**
- <path> — <what changed>     (or: none)

**Findings:**
- <finding summary>           (or: none)

⚠️ **Critical:** <only present when a finding needs attention>
```

After printing the report, the skill is done: take no further action and ask no follow-up question.
