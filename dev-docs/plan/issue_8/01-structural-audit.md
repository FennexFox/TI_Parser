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

Run bounded A/B fixture; record preparation and simulation separately; reconcile observed reads with static call closure and preserve unresolved paths.

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
tests. The controlled ModernScenario fixture has six player-owned CPs; both
180-day A/B paths complete with exact baseline/traced result, status and
coverage parity. Input/catalog hashes stay unchanged, index aliases remain
intact and no raw-container mutations are recorded.

The explicit DLL audit returns exit 2: structural completeness is incomplete
and the build comparison is mismatch. Catalog decode/manifest validation,
plain index-container accesses and unexplained normalization paths remain
unresolved. Five bounded source-to-derived chains now have static mappings;
these establish structural roles only. Each candidate records source location
and fingerprint, consumer, destination, evidence layer, visibility, build
applicability and blocking status. Dynamic/static discrepancies, unobserved
static candidates and unclassified visibility remain explicit blockers.

## Decision log

Canonical audit checkpoints are `[0, 180]`, matching the original initial/180-day
comparison. `[30, 90, 180]` is not the approved canonical audit shape.
A/B pips are audit fixtures only; no advisors does not imply no councilor reads.

Observed preparation includes councilor_summary_maps, projection_advisor_profiles
and calculate_topbar despite advisors being empty. No preparation optimization
was applied because complete dependency closure has not been established.

## Outcomes / Retrospective

Instrumentation and parity checks pass; structural acceptance remains open.
Do not infer visibility from parity, absent hidden-read events or DLL identity.
