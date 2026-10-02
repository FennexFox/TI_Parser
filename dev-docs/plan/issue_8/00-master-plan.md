# Projection structural audit and pre-integration acceptance

## Issue Target And Scope Summary

Issue #8 continues from the existing fair-play enforcement and correlation contract. This plan is authoritative for structural read auditing, evidence gates, test-only orchestration, and real-client acceptance. Existing default runtime behavior and committed catalogs remain unchanged.

## Strategy

Trace a fully owned ModernScenario nation for 180 days with single-segment plans, empty advisors and no diagnostic output. Knowledge/Welfare 3:1 and 1:3 are acceptance fixtures, not a production permission rule. Dynamic tracing is paired with static closure review. No trace, build, or visibility uncertainty may be interpreted as approval.

## Phase Order

1. [Structural read audit](01-structural-audit.md)
2. [Authoritative build and visibility evidence](02-authority.md)
3. [Guarded projection policy](03-guard.md)
4. [Mock Companion and real TI Parser integration](04-mock-integration.md)
5. [Real Companion and Codex acceptance](05-real-acceptance.md)

## Phase Dependencies

Phase 2 complements phase 1; phase 3 requires both structural completeness and authoritative visibility/correctness acceptance. Phase 4 is independent of projection approval and must test the current blocked behavior when phase 3 cannot proceed. Phase 5 requires actual Companion and an approved projection path.

## Source Of Truth Decisions

The maintained [interoperability audit](../../fairplay_interoperability.md) owns evidence and limits. User-facing setup and correlation sequence live in [MCP setup](../../../docs/MCP_SETUP.md). Registry classification is separate from a future approved `fair-play-projection-v1` guard policy. The current route remains visibility-dependent and denied.

## Global Validation Expectations

Run relevant audit, correlation and MCP tests, then the full pytest suite. Verify committed distribution bytes, local documentation links and `git diff --check`. Keep automated MCP calls separate from actual Codex routing evidence.

## Known Risks And Assumptions

Installed DLL SHA-256 differs from the catalog evidence DLL. Catalog regeneration/build migration is out of scope. A/B synthetic fixtures do not prove visibility. Container copies, normalization and scalar materialization can lose read provenance; unresolved escapes or static/dynamic discrepancies force audit incomplete. Strong generation identity requires same-algorithm fingerprints; pinned weak identity remains provisional even after reobservation. Actual Companion substitution and successful fair-play prediction remain required for issue closure.

## Current State

Application generation checks, pending guard metadata and mock two-server
protocol/routing tooling are implemented. Structural instrumentation is a
development aid; unresolved read mappings keep completeness open. Authority
remains blocked by the build mismatch, so guarded prediction is disabled.
Actual Companion/TI/Codex prediction acceptance remains open. See phase files
for evidence and the [routing record](routing-evidence.json) for synthetic
client observations; this plan is retained while acceptance gates are unresolved.

## TI Parser Follow-up Order

1. Replace negative assembly checks with separate structural, source-authority,
   visibility and overall eligibility states. Structural completion never
   grants authority; missing evidence must reject overall approval.
2. Keep inspections save-only and bind a selected nation through a trusted
   application operation. Caller-supplied JSON IDs cannot attest a subject.
3. Close known source-to-derived mappings and explicitly reconcile static and
   dynamic dependencies. Classify visibility only from applicable authority
   evidence; new reads, unexplained escapes and discrepancies remain blocking.
4. Preserve current disabled policy, mock/routing evidence and actual Companion
   acceptance gate. This follow-up does not modify the Companion repository,
   regenerate catalogs or migrate mechanics.
