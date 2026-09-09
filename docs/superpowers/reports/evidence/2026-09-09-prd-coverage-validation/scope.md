# Bounded PRD coverage workflow validation — proposed v1

Status: DRAFT; awaiting real author approval. This is a new disposable spike, not a
reliability study. Historical staged cohort results and its budget remain closed.

## Scope and isolation

Run root: /private/tmp/prd-coverage-validation-20260909.
Drafts: scratch/prd.md, scratch/knowledge-base.md, scratch/evaluation.md.
Binding proposed sources: source/requirements.md and source/AGENTS.md.
After approval only: create code repo `repo/` and external vault `vault/` using the init
workflow with explicit local settings. No existing private vault or prior toy state.
Proposed project: vault/projects/2026-09-09-json-preservation/.
Use installed package 0.8.1+codex.20260909022917, record package hash inventory.

## Model routing and run limits

Pre-approval: one read-only PRD reviewer, gpt-5.6-sol/high, fresh context; at most two
review continuations if needed, as superprd permits. No downstream role until approval.
After approval: all child roles gpt-5.6-sol/high with isolated contexts. At most 12 role
dispatches including retries, 15 minutes per dispatch, 90 minutes elapsed for the whole
post-approval run. Stop on the first exhausted limit; record incomplete, never PASS.
At most one transport retry per phase, counted within the 12; no automatic repair sweep.
Record model/effort, dispatch receipts, per-role usage if exposed and elapsed duration.
These are dispatch/time ceilings, not a promised dollar or token cap. No paid cohort.
Use completion events, not status-polling loops. No scheduler is installed or started.

## Actual workflow to exercise

1. Finish superprd drafting/reviewer and obtain author approval of the concrete v1
   agreement and this scope. Retain author message and exact content hashes. Commit
   unchanged binding sources in the isolated code repo, then write READY project through
   superprd into the separately initialized vault; capture distinct source/vault SHAs.
2. Invoke installed supermeta and supergoal to create the actual root plan; superplan
   creates one actual implementation leaf owning AC1, AC2 and AC3. Each packet preserves
   full agreement, source revisions, approval record, C1/J1 ownership and evidence roots.
3. Execute that leaf through installed superrun with a real implementer and independent
   delivery review. Local feature-branch review/merge replaces GitHub PR transport under
   the proposed fixture policy. Save the reviewed positive code commit.
4. In isolated local snapshot repositories create the controlled negative variant by
   replacing only byte equality with a destination-existence assertion. Keep source,
   agreement and product behavior identical. Submit this candidate to an independent
   leaf review without repair or integration. It must be rejected for insufficient
   assertion evidence even though C1 is green. A protocol check that the one assertion
   is the only code difference precedes grading.
5. Invoke installed supereval on independent positive/negative code-and-vault snapshots,
   with actual runner execution and evaluator roles. Each has main pointing at its
   selected candidate and its own copied round-ledger state; neither report overwrites
   the other. Bind code SHA, original requirement SHA, copied agreement/vault SHA and
   absolute roots separately. Verify C1/C2 PASS in both; J1/AC1/AC2 PASS only in positive; AC3 PASS in both.
   Negative AC1 FAIL means missing required proof, not demonstrated product corruption.
6. Root inspect complete returned packets, command receipts, meaningful assertion lines,
   per-item verdicts and persisted eval/ledger records. Preserve actual failures and
   any transport deviation. Publish a bounded result, without operational-readiness or
   reliability claims. Missing binding context or J results must fail closed.

Expected controls are visible in the agreement: this is an open development validation,
not a blind accuracy measurement. Gzip advice remains explicitly unapproved.
GitHub PR transport, unattended scheduler behavior, multi-leaf ownership, cross-harness
routing and statistical reliability are outside this run. The old greeting harness is
not used as an approval authority: it synthesizes approval and supplies implementation
commits, so running it unchanged cannot satisfy this scope.

## Current preparation evidence and limitations

No code repository, vault, implementation, scheduler or downstream model role has been
created or launched. Only scratch documentation and offline maintenance checks exist.
The PRD reviewer was given the three exact file paths and instructed to read them, rather
than embedding their bytes verbatim as superprd prescribes. Record this preparation
transport deviation; it is not evidence of exact prompt serialization compliance.
Before any approval, root must show reviewer findings and lint warnings alongside the
complete acceptance agreement. A reviewer PASS cannot substitute for author approval.

Product draft clarified after review: callable API and environment constraints are explicit
AC1/AC3 obligations; code main HEAD selection is explicit; the negative control is owned
only by this external validation scope. It changes one preservation assertion, so its
J1/AC1/AC2 FAIL expectations coexist with AC3 PASS.
