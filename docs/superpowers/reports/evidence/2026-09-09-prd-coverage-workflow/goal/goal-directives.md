# Goal Directives — 2026-09-09-15_18-json-preservation-r1
**Source:** [[projects/2026-09-09-json-preservation/meta-plans/2026-09-09-15_16-r1]]
**Confirmation:** auto-confirmed (SUPER_GOAL_AUTOCONFIRM=true, --autoconfirm) on 2026-09-09

## Goal / Objectives

Create one planning tree for a disposable Python 3.9+ standard-library function that rejects every string rejected by `json.loads` with `ValueError` or a subclass before changing an existing destination file, plus one executable unittest that proves the required malformed case leaves the destination bytes exactly unchanged. The single implementation leaf must own AC1, AC2, AC3 and all C1/C2/J1 evidence under the approved v1 agreement and bounded scope.

## What `goal-directives.md` is

This authoritative structural map lives once at the goal-folder root. It defines where goal artifacts belong and must be kept current as the planning tree and its outcomes evolve.

## Folder map

| Folder | One-line purpose | Lifecycle stage | Dated? |
|---|---|---|---|
| `master-plans/` | Strategic anchors: master/sub-master plans, design seeds, planning handoffs, reviews | Before & across sub-PRs | Yes |
| `plans/` | Self-contained, execution-ready implementation plans for **one** sub-PR | Just before execution | Yes |
| `findings/` | Pre-/mid-implementation investigation: spikes, categorizations, input ledgers | Feeds a plan | Yes |
| `reports/` | Post-implementation outcomes: closeouts, engagement/A-B results, "wiring complete" | After code runs/ships | Yes |
| `handoff/` | Session-to-session continuity: state-of-the-world, what the next agent picks up | At a session boundary | Yes |
| `todo/` | Open work-item backlog: deferred items, follow-ups, open-question trackers | Running, all stages | Yes |

## Per-folder directives

### `master-plans/`

**Put here:** strategic anchors, root and sub-master plans, design seeds, cross-sub-PR planning handoffs, and reviews that coordinate more than one execution unit.

**Does NOT belong:** a turn-key implementation plan for one sub-PR; put that in `plans/`.

### `plans/`

**Put here:** one self-contained, execution-ready implementation plan for one sub-PR, including exact files, interfaces, implementation steps, and verification.

**Does NOT belong:** cross-sub-PR strategy, seeds, or planning-tree coordination; put those in `master-plans/`.

### `findings/`

**Put here:** verified investigation, spikes, categorizations, and input ledgers that inform a future or active plan.

**Does NOT belong:** results or closeouts produced after implementation runs or ships; put those in `reports/`.

### `reports/`

**Put here:** post-implementation closeouts, measured outcomes, integration evidence, and reports that grade work after code runs or ships.

**Does NOT belong:** analysis whose purpose is to shape a plan before implementation; put that in `findings/`.

### `handoff/`

**Put here:** dated session-boundary state that tells a future agent what is true now and what to resume.

**Does NOT belong:** durable strategy, an execution-ready sub-PR plan, or a deferred backlog item.

### `todo/`

**Put here:** dated deferred work items, follow-ups, and open-question trackers that remain outside the active plan.

**Does NOT belong:** work already committed to a current implementation plan or evidence from completed implementation.

## Naming conventions

Dated plans, findings, post-mortems, baselines, handoff documents, and other lifecycle artifacts use `YYYY-MM-DD-hh_mm-<topic>.md`, where `hh` and `mm` are the UTC hour and minute at which the file is written. This keeps `ls` chronological and distinguishes files written on the same day. Undated structural documents, including this file and any future `README.md` or `architecture.md`, remain undated at the folder root.

## Cross-link conventions

Use full-path vault wikilinks in the form `[[2026-09-09-15_18-json-preservation-r1/<subfolder>/<basename-without-.md>]]`. Every document opens with a `# Title` followed by a `**Date:**` / `**Status:**` / `**Related:**` header block. Close the loop in both directions: a plan or seed links forward to its `reports/` outcome, and the report links back to the plan or seed.

## Which folder?

1. If the file grades shipped or executed code, route it to `reports/`.
2. If it records investigation that informs code or planning before implementation, route it to `findings/`.
3. If it is one turn-key sub-PR implementation plan, route it to `plans/`.
4. If it coordinates cross-sub-PR architecture, a seed, a planning handoff, or a review, route it to `master-plans/`.
5. If it records live state for a later session to resume, route it to `handoff/`.
6. If it tracks a deferred backlog item, route it to `todo/`.
