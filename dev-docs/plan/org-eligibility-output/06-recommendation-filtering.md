# Phase 06: Harden recommendation eligibility and end-to-end coverage

## Goal

- Make it difficult for consumers to mistake raw market rows for recommendations and protect the reported `RandomCriminal13` failure path end to end.

## Scope

- Add an explicit recommendation-readiness summary derived from `eligibleCouncilors`.
- Fail closed in `calculate_org_plan` when template data is unavailable and exclude unresolved-template candidates from recommendations with diagnostics.
- Normalize duplicate/overlapping market and owned-inventory references so output and search use the same source.
- Add a full-plan regression named for `RandomCriminal13`.

## Non-goals

- Removing ineligible orgs from raw candidate diagnostics.
- Expanding `eligibleCouncilors` to include Administration, org-count, detention, location, or affordability checks.

## Affected files

- `tools/ti_parser_org.py`
- `tests/test_org_plan.py`
- `tests/test_parser_org.py`
- `README.md`
- `dev-docs/plan/org-eligibility-output/*.md`

## Implementation steps

- Add `recommendationEligibility` to candidate rows with a boolean, eligible count, and eligible councilor IDs sourced directly from `eligibleCouncilors`.
- Add per-source recommendation-ready counts and IDs without duplicating candidate rows.
- Reject missing candidate templates when a template catalog was successfully loaded, and raise a clear full-plan error when no org template catalog exists.
- Deduplicate references with owned inventory taking precedence over market acquisition.
- Verify a high-stat `RandomCriminal13` candidate is diagnostic-only when no councilor has `Criminal`, then becomes recommendable only for a matching owner.

## Acceptance criteria

- No full-plan recommendation contains an org whose candidate row has no `eligibleCouncilors`.
- `RandomCriminal13` remains visible in `candidateSources` with its reasons but is absent from goal views and committee actions when no owner has `Criminal`.
- Missing templates cannot silently turn a restricted org into a recommendation.
- Candidate counts, source labels, and search pools agree when save references overlap.

## Validation commands

- `python -m unittest tests.test_org_plan tests.test_parser_org -v`
- `python -m unittest discover -s tests -v`

## Manual smoke tests

- Run the latest-save org plan and compare every candidate `recommendationEligibility.eligible` value with its `eligibleCouncilors` list and all emitted recommendations.

## Rollback risks

- Full-plan callers that intentionally ran without Terra Invicta template data will now receive an explicit error instead of an unsafe permissive result.

## Progress

- Pending.

## Decision log

- Raw candidate lists remain complete diagnostic inventories; recommendation readiness is a separate derived contract.
- Owned inventory takes precedence over market because assigning an already-owned org should not be modeled as a purchase.

## Outcomes / Retrospective

- Pending.
