# Structural read audit

## Goal

Trace source reads across preparation, calculation, branches and output without changing mechanics.

## Scope

Developer-only audit tool and fixtures; source-path reads, catalog inputs, alias/copy escape tests and original/traced parity.

## Non-goals

Visibility approval, catalog regeneration, broad mechanics refactors.

## Affected files

tools/audit_projection_reads.py; tools/projection_audit_dependencies.py; tests/test_projection_read_audit.py; the maintained interoperability audit.

## Implementation steps

Run bounded A/B fixtures with separate read records, including target preflight.
Collect executed rules and transitive dependencies from existing ruleExecutions,
metric ruleIds and static preparation paths. Explain unexecuted branch candidates
and scalar/container lineage; missing explanations remain incomplete.

## Acceptance criteria

Plain-container or normalization escapes must be accounted for. Unexplained escapes, missing execution stages or unmatched static paths are incomplete, never safe.

## Validation commands

- `python -m pytest tests/test_projection_read_audit.py -q`
- `git diff --check`

## Manual smoke tests

Run the audit with explicit output path and explicit assembly input when available; record reached execution prefix.

## Rollback risks

Audit instrumentation is developer-only; ordinary runtime behavior must be unchanged.

## Progress

Implemented developer-only save/catalog payload tracing and copy/normalization
tests. The controlled ModernScenario A/B fixture completes with baseline/traced
result, status and coverage parity. Input/catalog hashes stay unchanged, index
aliases remain intact and no raw-container mutations are recorded. This bounded
The observed fixture execution edges are closed by source-bound helper returns
and execution records. This does not establish complete source-read coverage
or production-domain closure: unobserved static candidates remain blockers.

The explicit DLL audit returns exit 2: structural completeness is incomplete
while the refreshed build comparison is match. Catalog decode/manifest validation,
plain index-container accesses and unexplained normalization paths remain
unresolved. A bounded set of source-to-derived chains has static mappings;
these establish structural roles only. Each candidate records source location
and fingerprint, consumer, destination, evidence layer, visibility, build
applicability and blocking status. Dynamic/static discrepancies, unobserved
static candidates and unclassified visibility remain explicit blockers.

## Decision log

The canonical endpoint comparison follows the original initial/terminal
checkpoint design; the proposed intermediate-checkpoint variant is not the
approved audit shape. A/B pips are audit fixtures only; no advisors does not
imply no councilor reads.

Observed preparation includes councilor_summary_maps, projection_advisor_profiles
and calculate_topbar despite advisors being empty. No preparation optimization
was applied because complete dependency closure has not been established.

## Outcomes / Retrospective

Instrumentation and parity checks pass; structural acceptance remains open.
Do not infer visibility from parity, absent hidden-read events or DLL identity.
The exact xenoforming value remains a mandatory blocker: the inspected current
DLL UI exposes gated color/severity information, not the exact numeric operand
used by annual population growth. No raw-save projection is authorized by this
structural audit.
