---
name: supercoverage
description: Use when drafting or revising a PRD and its acceptance criteria, to advise on test coverage, distinguish requirements from examples, and resolve verification ambiguities before implementation.
license: MIT
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

# Supercoverage

Advise the PRD author on what should be verified. The author approves the acceptance
checklist; implementation review verifies delivery against that approved checklist.
This skill produces advice and draft text, not product code or an implementation gate.

## Draft the coverage agreement

Read the proposed requirements and the author's decisions. Produce:

1. A draft acceptance checklist with stable IDs, source clauses, required cases or general
   behavior, observable expected results, verification method, and owning C/J check IDs.
2. A separate list of optional test suggestions and unresolved questions. Mark suggestions
   as unapproved. Resolve ambiguous outcomes with the author before declaring readiness.

Use this table under `## Acceptance checklist` in `evaluation.md` when called by
`superagent:superprd`. A standalone invocation returns the draft to the author; it does
not write or approve a project folder.

| Id | Source | Required case or rule | Expected result | Verification and check ids |
|---|---|---|---|---|
| AC1 | prd.md SC1 | Invalid input | Destination bytes remain unchanged | Assert byte equality before/after rejected operation; J1 inspects assertion, C1 executes suite |

The row is an example of form, not a requirement for every project. Use existing check
IDs where available; label proposed new checks as drafts until their commands/criteria
are resolved. Never claim a command was run or a test exists from this planning artifact.

## Coverage decisions

- Expand combinations explicitly required by the source. “Both formats, each with empty,
  single-record and malformed input” requires six cases, which may share a parameterized test.
- Preserve broad rules separately from example fixtures. “Unicode names, e.g. accented Latin”
  retains general Unicode behavior; it does not require every script or only Latin.
- Specify what an assertion must distinguish, not just a test name or input. For preserving
  a destination, checking existence alone does not establish unchanged contents.
- Suggest boundaries and failure cases with their rationale. Extra partitions, new supported
  formats, and exhaustive combinations become mandatory only through author approval.
- Choose a suitable verification method: executable assertion, command result, or concrete
  evidence inspection. Documentation obligations need not become artificial product tests.

## Approval and later changes

In superprd, present the checklist and separate suggestions at its existing confirmation
step. Record the user's approval of that concrete revision; unresolved required outcomes
prevent READY. A general instruction to automate implementation does not settle an
unspecified product behavior. Explicit prior approval of the same revision remains valid.

The approved checklist is a verification agreement, not proof of exhaustive coverage or
permission to weaken the PRD. If it conflicts with a source requirement, resolve the conflict
with the author. Later scope changes return to PRD revision, preserve prior versions, and
receive approval before becoming acceptance conditions. Reviewers may report newly found
risks, but do not silently turn suggestions into release requirements.
