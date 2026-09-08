# Blocked repair and verified completion

The mdtoc RCA is confirmed against canonical skills and the retained decision log, finding,
and evaluation: closeout removes a blocked leaf from both queues; re-plan only changes loop
status; empty queues then produce DONE. A fresh read-only agent reproduced this on 2026-09-07.

## Design

Create a successor implementation plan for an explicitly adopted repair. Preserve the original
plan, closeout, finding and PR evidence. The current step gets `repair requested` plus a durable
`Repair: [[findings/...]]` record. This record identifies the decision, step, prior active plan,
reason, PR/worktree, and successor (once written). Planning selects that row before closeout
filtering; execution skips it until a successor is published. Ancestors are reopened only along
this authorized repair path. Ordinary closed rows retain their existing descent behavior.

The successor replaces the active Plan link on the same step. Historical links move to the
repair record, outside navigation. It carries explicit corrected scope and integration disposition
for the existing PR. A late closeout from the predecessor cannot overwrite the successor.
Durable records plus idempotent publication support crashes between tree and loop writes.

DONE requires empty queues AND a fresh, recursive completion audit, which traverses internal
nodes even with stale closed status. Active leaves require verified integration on main, or a
recorded intentional disposition. Open PRs, pending repair, missing evidence, and inconsistent
reports block completion. BLOCKED takes precedence over none. Unknown state fails closed into
the existing decision ladder, not successful disarm. No new scheduler status or parser is needed.

## Alternatives

Revising the old leaf mixes failed and corrected execution evidence and fights closeout
idempotency. Adding a sibling repair leaves the original open leaf blocking forever unless a
second resolution model is added. A successor replacing the current step's link preserves one
active obligation and a complete history.

## Scope and constraints

- Canonical skill contracts are production logic; rebuild Codex, Pi and Cursor outputs.
- Python 3.9 standard library / unittest; macOS bash 3.2 compatible verification.
- Preserve the failed mdtoc run, frozen evaluation, blocked PR and scheduler state.
- No claim of real transport acceptance from static or agent scenario tests.
- Corrected mdtoc parsing/write behavior and hardened C4/C7 checks belong to a new operator round.

## Verification

Run a fresh-agent baseline before edits; persist reusable scenario prompts and an automated
answer validator; run fresh-agent scenarios after edits and against generated skills. Check
repair selection, mixed none/BLOCKED, historical closeout, fresh-tick replay, successor execution,
stale ancestor completion, integration evidence, merged/declined completion, predecessor closeout
and duplicate repair decisions. Run builders with --check and existing package/runner suites.
