# WAITING FOR CI gate + 0.4.8 follow-up hardening — design

**Date:** 2026-08-28  **Status:** accepted  **Ships as:** 0.4.9

## Problem

0.4.8 made a `WAITING FOR INPUT` park free. The other parked state, `WAITING FOR CI`, still launches
a full CLI session every interval whose only job is one batched status query over `ci_wait.runs`
(superagent SKILL.md, "WAITING FOR CI (parked — the cheap branch)"): a paid session per interval for
the whole 60–120 min lane. The #22 review also parked four small correctness items.

## Decisions

1. **CI gate in bash (`SUPER_CI_GATE=true`).** In `superagent-tick.sh`, AFTER `ensure_gh_auth`
   (it needs `GH_TOKEN`/`gh`) and before the prompt is built: if `status == WAITING FOR CI`, parse the
   run ids from the frontmatter `ci_wait:` block (`superagent_ci_runs`, accepts `runs: [1, 2]` and a
   `- id` list) and query `gh run view <id> --json status --jq .status` for each, from `$REPO`.
   Any run not `completed` → one log line, exit 0, no session. All `completed` → fall through; the
   skill's branch runs the Resuming flow as today. **Fail-open:** no parseable ids, or any `gh`
   failure → log and fall through to the session (today's behaviour), never a silent stall.
   One API call per run per interval replaces one CLI session per interval.
2. **`answer.sh` lock hardening.** Release the lock before the kick on the under-lock skip path
   (a kicked tick otherwise sees a held lock and exits; resume waits an interval). Steal a lock whose
   `owner` PID is dead (superloop L3 semantics) instead of refusing forever with exit 4.
3. **`status.sh` INPUT column tells the truth post-gate:** `YES` = parked and unanswered (needs
   you), `ans` = answer recorded, next fire resumes, `-` otherwise; JSON gains `answer_recorded`.
4. **`scripts/README.md` `.superenv` facts:** cite `templates/superenv.default` instead of the stale
   "28 keys / 30m / inherit" numbers.

## Out of scope
Event-driven wake; `answer.sh --loop-file` / a shared slug→loop-file helper; the `--` terminator.

## Compatibility
No loop-file format change (the skill already prescribes `ci_wait.runs`; this adds "write `runs:` as
an inline list of GitHub Actions run ids" as the canonical form — the parser accepts both). New key
`SUPER_CI_GATE=true`. No new exit codes. Armed loops pick it up on their next fire.
