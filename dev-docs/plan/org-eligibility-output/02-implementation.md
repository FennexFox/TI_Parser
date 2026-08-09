# Phase 02: Expose candidate requirements and per-councilor eligibility

## Goal

- Correct nation-interest evaluation and expose all requested eligibility information on every market and owned-inventory candidate.

## Scope

- Resolve each org's home nation.
- Evaluate faction nation interest from controlled nations and councilor home nations.
- Evaluate required/prohibited owner traits for each councilor.
- Add requirement, faction eligibility, eligible-councilor, and ineligible-councilor summaries to candidate rows.
- Reuse the corrected eligibility check in individual and committee assignment planning.

## Non-goals

- Full reproduction of market technology, ideology, faction-specific, detention, location, or takeover rules.
- Any change to optimization objectives or resource affordability.

## Affected files

- `tools/ti_parser_org.py`
- `tests/test_org_plan.py`

## Implementation steps

- Add small helpers for nation summaries, faction nation-interest evidence, and requirement serialization.
- Pass faction context through assignment search so nationality-gated orgs use the same rule everywhere.
- Precompute enriched candidate rows for both candidate sources.
- Add focused unit tests for controlled-nation, councilor-home-nation, missing-interest, required-trait, and prohibited-trait cases.

## Acceptance criteria

- A faction control point in the org home nation makes the nationality requirement pass for all otherwise eligible councilors.
- A faction councilor homeland in the org home nation also satisfies the faction requirement.
- Missing faction interest is visible on the candidate and excludes every councilor.
- Owner-trait failures name the affected councilor and reason.
- Existing fields and planner behavior remain backward compatible.

## Validation commands

- python -m unittest discover -s tests -v

## Manual smoke tests

- python tools\ti_save_parser.py org-plan --compact

## Rollback risks

- Passing faction context through the planner touches multiple call sites; defaults must preserve direct helper callers and synthetic tests.

## Progress

- Complete.

## Decision log

- Candidate source rows preserve their existing fields and add `requirements`, `factionEligibility`, `eligibleCouncilors`, and `ineligibleReasons`.
- `factionEligibility.evaluatedRules` and `eligibilityScope` distinguish implemented nation/trait parity from detention, location, technology, and ideology checks that are not independently evaluated here.
- Assignment search receives the selected faction and uses the same faction-wide nation-interest rule as candidate diagnostics.
- Public assignment helpers recover omitted faction context from the councilor reference or faction roster.

## Outcomes / Retrospective

- Nation interest now accepts either a controlled control point in the org's current home nation or any faction councilor homeland in that nation.
- Required and prohibited owner traits are reported per councilor, and invalid candidates are no longer silently omitted from the audit surface.
- Owned inventory follows the same game UI nation-interest gate as market acquisition; source changes cost handling, not owner eligibility.
