# Upfront plan-tree live acceptance

**Status:** PASS — PT-01 through PT-11 passed with no failed or incomplete requirements on 2026-09-17.

The run used three independent disposable code/vault fixtures and the copied Claude, Codex, Cursor,
and Pi plugin packages. Initial tree authorship and all five normal implementation stages ran through
real Codex CLI dispatches. Bounded stage preparation used `gpt-5.6-terra` at medium effort. The
contract-break batch used the distinct Claude `opus` replanner at high effort. Cursor and Pi package
copies were verified offline; no live claim is made for their model transports.

| Harness | Coverage in this acceptance | Model selection exercised | Scope of claim |
|---|---|---|---|
| Codex | Initial tree authorship, six normal stage refinements, five stage executions, and bounded-detail refinement | `PLAN_REFINER=codex:gpt-5.6-terra` / `medium` | Live CLI and lifecycle coverage |
| Claude | Contract-break detection and the successful affected-stage replanning batch | `REPLANNER=claude:opus` / `high` | Live bridged replanning coverage |
| Cursor | Generated package, configuration resolution, role routing, and bridge contract checks | Shipped `PLAN_REFINER` and `REPLANNER` selections are `inherit` / `inherit` | Offline compatibility coverage; live model transport not exercised |
| Pi | Generated package, configuration resolution, role routing, and bridge contract checks | Shipped `PLAN_REFINER=pi:openai-codex/gpt-5.6-terra` / `medium`; `REPLANNER=pi:openai-codex/gpt-5.6-sol` / `high` | Offline compatibility coverage; live model transport not exercised |

The acceptance snapshot used `claude:sonnet` / `medium` and
`claude:claude-opus-4-8` / `high` as the Claude defaults for those roles, while the Codex defaults
were `codex:gpt-5.6-terra` / `medium` and `codex:gpt-5.6-sol` / `high`. The live Claude replanner
used the accepted `opus` tier alias rather than the full default model ID. The current defaults have
since moved every Anthropic Opus role to `claude-opus-5`, the Claude planner to
`claude-fable-5-1`, and the Codex and Pi planners to `gpt-6-astra`; these newer selections were not
the models exercised by this retained run.

| Path | Result |
|---|---|
| Initial publication | Three complete generation-1 trees published atomically. |
| Normal lifecycle | Five of five stages refined, executed, integrated, and closed; 25 of 25 fixture tests passed. |
| Bounded detail | S01 preparation changed implementation detail only; zero replanner dispatches. |
| Contract break | S02 and S03 revised together in generation 2; S01, S04, and S05 retained. |
| Batch recovery | First replanner attempt interrupted without publication; retry resumed the same decision and published atomically. |
| Vault layouts | Internal and external vault publications both verified. |
| Legacy compatibility | Unmarked root retained incremental planning behavior. |

| Measured role work | Dispatches | Bridge time | Reported tokens |
|---|---:|---:|---:|
| Normal stage refinement | 6 | 2,044 seconds | 621,188 |
| Bounded-detail refinement | 1 | 415 seconds | 133,307 |
| Contract-break detection | 1 | 148 seconds | 64,130 |
| Successful replanning retry | 1 | 517 seconds | unavailable from Claude bridge output |

Normal preparation published six amendments because S05 needed one bounded correction from revision 2
to revision 3 after the live Python 3.9 check. The contract-break batch revised two stages and retained
three. The interrupted replanner log has no trailer, so its duration and token count remain unknown.

The machine-readable [manifest](evidence/2026-09-16-upfront-plan-tree/live-plan-tree-manifest.json),
[verdict](evidence/2026-09-16-upfront-plan-tree/live-plan-tree-result.json), operation traces, Git
bundles, role-log archive, and SHA-256 inventory are retained beside this report. The validator
reported `PASS: 11`, `FAIL: 0`, and `INCOMPLETE: 0`. Its 61-test self-test suite also passed.

The live artifacts exposed a schema gap in the evidence validator: shipped skills use goal-relative
extensionless links, uppercase bridge role names, list-item closeout metadata, and current receipt
labels. Regression coverage now exercises those forms while retaining strict checks for conflicting
identity metadata, exact historical plan digests, Git ancestry, model pins, ordering, interruption
recovery, and coherent replan dispositions.

With live acceptance green, the shipped `SUPER_PLANNING_MODE` default is now `upfront`. Existing
marked incremental roots and unmarked legacy roots remain incremental, and new goals can select that
lifecycle explicitly with `SUPER_PLANNING_MODE=incremental` or
`supergoal --planning-mode incremental`.
