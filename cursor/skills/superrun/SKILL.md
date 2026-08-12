---
name: superrun
description: Use when asked to execute the next ready implementation plan in a goal's plan tree from its root seed/master plan — finds the highest-priority written-but-unexecuted leaf plan, executes it, and closes it out.
license: all rights reserved
related skills: supertraverse, superfinish, superplan
---

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
> - Skill names are **unprefixed** on Cursor: `superagent:superplan` means the `superplan` skill
>   from this plugin, `superpowers:subagent-driven-development` means `subagent-driven-development`,
>   and so on — strip the `<plugin>:` prefix when looking a skill up. The `superagent` supervisor
>   skill itself carries `disable-model-invocation` and is invisible to model-driven skill lookup —
>   it is driven by reading its SKILL.md directly (the external tick's file-read prompt), never
>   invoked by name.

# Superrun

The **execution** leg of the plan-tree lifecycle. The `super*` family covers the rest of the
arc — `supergoal` seeds the tree, `superplan` writes a step's implementation (leaf) plan and marks
its row `PLAN WRITTEN — ready to execute`, `superfinish` closes out an *already-executed* leaf.
superrun is the verb between "plan written" and "closed out": given a goal's **root** seed/master
plan, it finds the highest-priority written-but-unexecuted leaf plan, **executes it**, and hands it
to `superfinish`.

## Repo configuration (.superenv)

Repo-specific values in this skill are named `SUPER_*` keys. Resolve each at point of
use, highest wins: (1) a process environment variable of the same name, (2) the
repo-root `.superenv` file, (3) the plugin default
`${SUPER_PLUGIN_ROOT}/templates/superenv.default`. Read a key with:
`grep -hs '^KEY=' "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")/.superenv" "${SUPER_PLUGIN_ROOT}/templates/superenv.default" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*//;s/[[:space:]]*$//'`
(checking the env var first, and anchoring at the primary checkout so worktrees resolve the same config). A repo with no `.superenv` runs on the shipped defaults.

## Prerequisite — superpowers

This skill executes plans via `superpowers:subagent-driven-development`. If that skill is
not resolvable in this session, ABORT with: "superrun requires the superpowers plugin —
install it (e.g. `/plugin marketplace add obra/superpowers-marketplace`, then
`/plugin install superpowers`) and retry." Never degrade to inline execution.

**One leaf plan per invocation.** superrun finds the single highest-priority incomplete leaf,
executes it, closes it out, reports, and exits. To run the next plan, invoke superrun again on the
same root.

Unlike superplan/superfinish (which are docs-only), superrun **does** change source code — but
**only via the delegated skills**. It never finds the target, executes the work, or writes the
closeout by hand: each phase is owned by an existing skill, and superrun must invoke it.

| Thought | Reality |
|---------|---------|
| "I'll just detect the target plan myself by reading the tree" | NO. Invoke `superagent:supertraverse` DESCENT in **execution mode** — it is the only place tree navigation is defined. |
| "I'll implement the plan's tasks directly / dispatch my own subagents" | NO. You **MUST** use `superpowers:subagent-driven-development` to execute the plan. |
| "I'll write the findings/closeout report and update the tree myself" | NO. You **MUST** use `superagent:superfinish` for closeout. |
| "No worktree needed — I'll edit in the primary checkout" | NO. Enter a git worktree first — required by `superpowers:subagent-driven-development`'s own precondition. |
| "I'll pause before each CI push to confirm" | NO. Run fully autonomously — let subagent-driven-development run end-to-end per its no-check-in-between-tasks rule. |
| "I found the target, I'll execute the next one too while I'm here" | NO. One leaf per invocation. After closeout, report and exit. |
| "A long CI push is queued — I'll wait for it to finish before pushing the next one" | NO. If `SUPER_CI_RUNNERS > 1`, queue every independent long push back-to-back (**CI scheduling**, Step 3) — the next free runner picks up the next job; serialize only across a named procedural gate. If `SUPER_CI_RUNNERS=1`, there is no runner contention to exploit, but a shardable batch's pushes still queue together and wait together. |
| "I'll wait for CI with `gh run watch` / a backgrounded sleep-poll loop" | NO. The wait is **parked** (Step 3a): standalone → report the queued run ids and end the turn (resume later via **Resume entry — post-CI**); under superagent → return a CI-PENDING report and stop. Poll loops burn context for nothing. |

## Input — `<PLAN.md>` (Gate 1)

superrun requires `<PLAN.md>` — the **root** seed/master plan of the goal whose tree it traverses.
If it was not provided, exit with:

    superrun needs the root plan file (<PLAN.md>) to traverse. Nothing was run. Exiting.

Do not guess a root from the working directory.

## Step 1 — Find the target (invoke `superagent:supertraverse`, execution mode)

Invoke the `superagent:supertraverse` skill (Skill tool) and run its **DESCENT in execution mode** on
`<PLAN.md>`. It returns one of:

- **`not-traversable`** — the root is not maintained as a progress-report tree (only orchestration
  tables / no step-tracking list). Report this and exit; there is nothing to execute.
- **`none`** — no incomplete implementation plan exists under this root. Everything is either still
  **unplanned** (a blank-`Plan` row — use `superagent:superplan` to plan it) or **already complete**.
  Report which case applies and exit.
- **a target leaf plan file path** — the highest-priority written-but-unexecuted leaf. Proceed.

## Step 2 — Isolate the workspace (enter a worktree)

Before any code work, enter a git worktree via the native `EnterWorktree` tool. This is a
precondition of `subagent-driven-development`, required regardless of any host-repo policy on the
question. Keep multi-batch execution isolated from the primary checkout. The native tool can be
unavailable in subagent/headless contexts (a pinned cwd it cannot change) — when it is, fall back to
plain `git worktree add <path> <branch>` with absolute-path operations from there on, which
preserves the same isolation in substance.

## Step 3 — Execute the plan (invoke `superpowers:subagent-driven-development`)

**You MUST use `superpowers:subagent-driven-development` to execute the target leaf plan. Do not
execute it any other way.** Invoke it via the Skill tool and follow it exactly, **subject to the
repo profile below**:

- **Read the target leaf plan yourself** and extract its **full task list** plus scene-setting
  context. subagent-driven-development expects you to hand each implementer the **full task text**
  (it does not make the subagent read the plan file). Provide the context about where each task fits.
- Run the plan **end-to-end, fully autonomously** — do **not** pause for confirmation between tasks
  or before CI pushes.
- Honor the skill's two-stage review (spec compliance, then code quality) per task; never skip a
  review or proceed with unfixed issues.
- When the tasks are done, superrun integrates the code PR **itself**, autonomously, per **Step 3a**
  below. Capture the resulting **code PR** URL for the Final Report.

### Repo profile — apply these overrides to subagent-driven-development

This block is the single, consolidated statement of where this repo's `.superenv` deviates from the
skill's defaults. Carry it into every dispatch the skill's task loop makes:

1. **Test evidence is keyed by `SUPER_TEST_EVIDENCE`.** If `SUPER_TEST_EVIDENCE=ci`: implementers
   never run tests or builds locally — no test runners, no build scripts. A task's test
   evidence is the CI push its plan step specifies: the run id and conclusion. The skill's TDD
   RED/GREEN local-output contract does not apply; reviewers judge the code plus the reported CI
   results and never execute anything themselves. If `SUPER_TEST_EVIDENCE=local` (the shipped
   default): the SDD skill's native RED/GREEN contract applies unchanged.
2. **Unattended conflict routing.** Every "ask your human partner" branch in the skill — the
   pre-flight plan-conflict scan, plan-mandated findings, the fix-loop breaker's load-bearing
   escalation — becomes: **report BLOCKED** with the finding and the plan text it collides with,
   then stop. The caller (a `superagent` loop's escalation ladder, or a human running superrun
   directly) decides. Never call `AskUserQuestion` from the SDD controller.
3. **Model policy** (supersedes the skill's Model Selection section): dispatch each SDD role on its
   `.superenv` model key — implementer: `SUPER_MODEL_IMPLEMENTER`, fix-applier:
   `SUPER_MODEL_FIX_APPLIER`, task reviewer: `SUPER_MODEL_TASK_REVIEWER`, re-reviewer:
   `SUPER_MODEL_RE_REVIEWER`, final whole-branch reviewer: `SUPER_MODEL_BRANCH_REVIEWER`, fix rounds
   4–5 fix-planner: `SUPER_MODEL_FIX_PLANNER` (then hand the mechanical edit to a
   `SUPER_MODEL_FIX_APPLIER` fix-applier). A value of `inherit` means omit the model override. A tier
   name (`sonnet` | `opus` | `haiku` | `fable`) is passed as the Task call's `model:` parameter. A
   **full model ID** (matches `^claude-`, e.g. `claude-fable-5`) cannot go through `model:` — the
   parameter is tier-enum-only — so dispatch that role with `subagent_type: super-<role>` (e.g.
   `super-implementer`, `super-task-reviewer`), the per-role agent definition `superagent:init`
   generates in `.cursor/agents/`, and omit `model:`. A missing definition for a full-ID key, or any
   other unrecognized value, is a hard error — fail the dispatch loudly (for the missing-definition
   case, instruct a `superagent:init` re-run); never silently substitute a cheaper tier.
   **Effort policy:** each role also has a `SUPER_EFFORT_<ROLE>` key (same names as the
   model keys). `inherit` = no override. A non-`inherit` effort can only ride the
   generated per-role agent definition (the Task tool has no effort parameter) — dispatch
   that role with `subagent_type: super-<role>` and omit `model:` (the definition carries
   both pins). A missing definition for a non-`inherit` effort key is the same hard error
   as the full-ID case: fail loudly and instruct a `superagent:init` re-run.
4. **Reviewer labels — keyed by `SUPER_REVIEW_CONFIDENCE_FILTER` (shipped default `controller`,
   the only supported value).** Reviewers report **every** finding with a severity **and a
   confidence label**; the controller filters to high-confidence findings before acting on or
   surfacing them. Never instruct a reviewer to report only high-confidence issues — Claude
   5-family reviewers apply that filter silently and drop real findings.
5. **Finishing handoff is keyed by `SUPER_SKIP_FINISHING_HANDOFF`.** If `true`: skip
   `superpowers:finishing-a-development-branch` entirely — its interactive completion menu cannot be
   answered by an unattended caller, it leaves the code PR open for a manual merge, and it runs tests
   on the host. Integration is owned by **Step 3a**. If `false` (the shipped default) and a human is
   driving, the finishing skill's menu is available; unattended callers always use Step 3a regardless
   of this key.
6. **Repo notes.** If `SUPER_REPO_NOTES` is set, read that file before starting the task loop and
   treat it as standing repo policy.

### CI scheduling — queue all shards (keyed by `SUPER_CI_RUNNERS`)

If `SUPER_CI_RUNNERS > 1`, this repo's CI shares one job queue across that many identical runners —
the next free runner picks up the next queued run. When the leaf plan's tasks trigger **more than
one independent long CI push** (>10 min each — e.g. a shardable stress lane split into per-shard
pushes, or two unrelated long lanes), **queue them all back-to-back, then wait on all of them
together**:

1. Push every shard/lane now — each as its own commit + push. If `SUPER_CI_FLAG_TEMPLATE` is set
   (e.g. `[test:%s]`), stamp each push with it — when `SUPER_CI_ONE_FLAG_PER_PUSH=true` (the shipped
   default), **exactly one** flag per push; sharding is *more pushes queued at once*, never more
   flags per push. If `SUPER_CI_FLAG_TEMPLATE` is empty, the repo has no commit-flag system — push
   normally.
2. Record **every** resulting run id; the CI-green gate (Step 3a) waits on **all** of them in a
   single monitor-parked wait.
3. Serialize two pushes **only** across a genuine procedural gate the plan names — worked example
   from the originating repo: a smoke lane that must be green before its expensive baseline, like
   `multi_motif_smoke` → `multi_motif`. Runner contention is never a reason to serialize — the queue
   handles it.

If `SUPER_CI_RUNNERS=1` (the shipped default), there is no runner contention to exploit: push and
wait for CI runs in the order the leaf plan specifies. A plan that names a shardable batch still
queues every shard's push together and waits on all run ids in one monitor-parked wait (Step 3a) —
it just gets no benefit from parallel pickup. If the plan text stages pushes serially with no named
procedural gate under `SUPER_CI_RUNNERS > 1` (a leftover of single-runner-era authoring), queue them
concurrently anyway and note the deviation in the Final Report.

## Step 3a — Autonomous code-PR integration (keyed by `SUPER_SKIP_FINISHING_HANDOFF`)

If `SUPER_SKIP_FINISHING_HANDOFF=true`, or the caller is unattended (a `superagent` loop), Step 3a
owns integration end-to-end with no interactive prompt. If `false` and a human is driving,
`superpowers:finishing-a-development-branch`'s menu may take over integration; Step 3a governs only
when it does not.

When Step 3a governs (per the keying above), integrate the code PR with **no interactive prompt**,
merging only when the CI-green gate below — or its review-green fallback — is satisfied. This
integration step is itself keyed by `SUPER_PROTECTED_MAIN` — the CI-gate keying in item 2 below still
governs whether to wait for CI **first**, in both branches; only the merge mechanism at the end (item
3) differs. Both key states need the primary checkout's absolute path below — derive it once, before
item 1, so it is defined for every use in either branch:

```bash
primary_root="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
```

1. The leaf plan's own task steps already pushed to CI with the flag `SUPER_CI_FLAG_TEMPLATE`
   specifies, if any (see Step 3). Ensure the feature branch is pushed — if `SUPER_BRANCH_STYLE=flat`
   (the shipped default), use a flat branch name with no slashes (a slashed name can miss CI's branch
   glob); if `SUPER_BRANCH_STYLE` is anything else, follow that style instead. If
   `SUPER_PROTECTED_MAIN=true` (the shipped default), also open the code PR with `gh pr create`. If
   `SUPER_PROTECTED_MAIN=false`, skip `gh pr create` — there is no PR in this branch, only the pushed
   feature branch (still pushed so CI, if any, has something to run against).
2. **CI-green gate — monitor-parked, never polled — keyed by `SUPER_TEST_EVIDENCE` three ways:**
   - **`SUPER_TEST_EVIDENCE=ci`:** collect the run id of **every** CI run this leaf queued (`gh run
     list --branch <branch>` — one run per push; a sharded batch has several, see **CI scheduling**
     in Step 3), then wait for all of them (wait mechanics below). If the plan expected a run and
     `gh run list` finds none, that is **BLOCKED** — do not merge.
   - **`SUPER_TEST_EVIDENCE=local`** (the shipped default) **and `gh run list --branch <branch>`
     returns runs** — the repo has CI wired even though evidence is local: wait for those runs to be
     green before merging (same wait mechanics as the `ci` branch).
   - **`SUPER_TEST_EVIDENCE=local` and no runs exist:** CI evidence is not expected for this repo.
     Skip the wait entirely and merge on review-green alone — the task reviews and final
     whole-branch review already completed in Step 3 are the evidence. State this explicitly in the
     Final Report (e.g. "no CI configured for this repo; merged on review-green").

   When a wait is needed (either of the first two branches above), never wait with `gh run watch`,
   foreground sleeps, or backgrounded re-poll loops — every poll iteration re-enters your context and
   a long lane (60–120 min) burns it for nothing. Instead:
   - **Standalone (superrun is the top-level session's task):** there is no Monitor tool in this
     build, so do not wait in-session at all. Report the queued run ids, the worktree/branch/PR
     packet, and how to check the runs (`gh run list --branch <branch>`), then **end the turn**.
     Once every run is terminal, re-invoke superrun via its **Resume entry — post-CI** with that
     packet and the conclusions to finish the leaf.
   - **Dispatched as a subagent (e.g. by a `superagent` loop):** do NOT arm the wait yourself
     (a Monitor cannot resume a subagent whose turn has ended) and do NOT emit interim
     "still waiting" notifications. Return a **CI-PENDING report** (format below) as your final
     message and stop. The supervisor owns the wait and resumes you — `SendMessage` in-session, or a
     fresh resume dispatch (see **Resume entry — post-CI**) when the session was recycled — with the
     terminal conclusions. A CI-PENDING report is a valid yield, not a failure and not your Final
     Report.

         ## Superrun CI-PENDING
         **Leaf plan:** <full path to the target leaf plan>
         **Root:** <full path to <PLAN.md>>
         **Worktree:** <absolute path — left in place>
         **Branch:** <branch name>
         **Code PR:** <url> (open — awaiting CI) — or `N/A (SUPER_PROTECTED_MAIN=false)` if there is no PR
         **CI runs:** <every queued run id, comma-separated>
         **Remaining:** CI-green gate verdict (Step 3a) → superfinish closeout (Step 4) → worktree exit (Step 5)

   On the terminal state (Monitor fired, or the supervisor resumed you) — or immediately, when no
   wait was needed (`SUPER_TEST_EVIDENCE=local` with no runs found):
   - **ALL runs GREEN, or no CI wait was needed** → (`SUPER_PROTECTED_MAIN=true`, the shipped
     default) merge per `SUPER_MERGE_METHOD` (default `squash`) — e.g.
     `gh pr merge --squash --delete-branch` (plain merge — **not** `--admin` unless
     `SUPER_ADMIN_MERGE=true` permits it; see item 3) — then
     `git -C "$primary_root" pull --ff-only`. When `SUPER_PROTECTED_MAIN=false`,
     integrate via item 3's direct-merge recipe instead — no PR, no `gh`.
   - **ANY run RED / cancelled / timed_out, or `SUPER_TEST_EVIDENCE=ci` expected a run and found
     none** → **do NOT merge.** Leave the PR open, capture the failing run URL(s), and declare the
     step **BLOCKED** in the Final Report. (When a `superagent` loop drives superrun, its escalation
     ladder decides what happens next; a human caller sees the blocker plainly.)
3. **If `SUPER_PROTECTED_MAIN=true` (the shipped default): merge per `SUPER_MERGE_METHOD` (default
   `squash`). Pass `gh pr merge --admin` only if `SUPER_ADMIN_MERGE=true` — otherwise never.**
   Reaching for `--admin` when the key is unset or `false` buys nothing on a repo whose branch
   protection doesn't require it, and reliably **trips the harness security classifier**, which reads
   merge-over-red as a privileged override and denies it. If the plain merge is actually refused,
   escalate to `--admin` only when `SUPER_ADMIN_MERGE=true` permits it, and report why. Full rationale
   in `superauthor` clause **A7**. Note that `--delete-branch` can exit 1 with `fatal: '<branch>' is
   already used by worktree` **after a successful merge** — that is the local delete step, not a
   rejection; confirm with `gh pr view <n> --json state,mergedAt` and drop the remote ref via
   `gh api -X DELETE repos/<owner>/<repo>/git/refs/heads/<branch>` rather than re-running the merge.

   **If `SUPER_PROTECTED_MAIN=false`: no PR, no `gh` — merge the worktree branch into the default
   branch directly and locally, from the primary checkout** (the worktree stays on its feature
   branch throughout — `git checkout <default-branch>` is invalid there, since Step 2's linked
   worktree already has the default branch checked out at the primary), once the CI-gate above
   (item 2) is satisfied:

   ```bash
   git -C "$primary_root" merge --no-ff <branch>   # or per SUPER_MERGE_METHOD, e.g. --squash — but
                                                    # --squash stages without committing, so follow it with:
                                                    # git -C "$primary_root" commit -m "<leaf-plan title>"
   git -C "$primary_root" push   # only if a remote exists — a repo with no remote simply keeps the merge local
   ```
4. If `SUPER_GH_DISABLE_SANDBOX=true` (macOS hosts where `gh` needs keychain access to verify the
   TLS cert), all `gh` commands need `dangerouslyDisableSandbox: true`. If `false` (the shipped
   default), run `gh` normally. Do **not** add Anthropic/Claude attribution or `Co-Authored-By`
   trailers (repo policy).

### Resume entry — post-CI (superagent-driven)

When superrun is invoked (or a prior superrun subagent is `SendMessage`-resumed) with a **CI-terminal
resume packet** — the CI-PENDING fields (leaf plan, root, worktree, branch, PR url, run ids) plus each
run's terminal conclusion — do **not** re-run Steps 1–3: the leaf is already implemented and its runs
are already terminal. Enter the recorded worktree (it was left in place), verify the packet's
conclusions with one `gh run view <id>` per run (trust but verify — the packet may be stale), and take
Step 3a's terminal-state branch directly: merge on all-green, BLOCKED on any-red. Then continue with
Steps 4–5 and return the real **Final Report**.

## Step 4 — Close out the plan (invoke `superagent:superfinish`)

Once execution is complete, invoke the `superagent:superfinish` skill (Skill tool), **passing the
target leaf `<PLAN.md>`** (superfinish's Gate-1 resolution precedence #2 — "passed by a calling
skill"). It captures findings, writes the closeout report, annotates the leaf plan, runs
`supertraverse` **completion-mode ascent** (C7) to advance the parent seed's progress-report table,
and merges its docs-only **closeout PR**. Capture that PR URL too.

## Step 5 — Worktree lifecycle

After `superfinish` reports the work merged, exit the worktree via `ExitWorktree`
(worktree is kept only while a PR stays open). If the **code PR** was left open in Step 3a (CI red /
BLOCKED, not merged), leave the worktree in place and note that in the Final Report.

## Final Report — then exit

Give the user a single report and exit. **Ground every line in evidence from this session** — a tool
result, PR URL, or CI conclusion you actually observed. If something is not yet verified (e.g. a merge
you did not confirm landed), say so explicitly rather than reporting it done:

    ## Superrun complete

    **Executed plan:** <full path to the target leaf plan>
    **Root:** <full path to <PLAN.md>>
    **Worktree:** <path> (exited / left in place — code PR open)

    **Code PR:** <url> (merged)               ← or (open — BLOCKED: <reason>, CI run <url>)
    **Closeout PR:** <url> (merged)            ← from superfinish

    **Findings:** <summary>                    (or: none — superfinish recorded none)

    ⚠️ **Critical:** <only when a finding or blocked task needs attention>

If execution was **blocked** (subagent-driven-development could not complete a task — plan wrong,
task too large, missing context — or the Step 3a CI-green gate was red), do **not** fabricate
completion and **do not merge** the code PR: report the blocker plainly, note what was and wasn't done,
and still run `superagent:superfinish` so the partial outcome is recorded honestly.

After printing the report, the skill is done: take no further action and ask no follow-up question.
