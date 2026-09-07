# Phase 03: Add regression coverage and validate the latest Broken Earth save

## Goal

- Demonstrate the corrected output with focused tests, the complete test suite, and the latest Broken Earth save.

## Scope

- Run focused org-plan tests.
- Run all repository tests.
- Inspect current-save candidate diagnostics and verify previously rejected nationality orgs now have eligible councilors where appropriate.

## Non-goals

- Committing user save data or adding a machine-specific save fixture.

## Affected files

- `tests/test_org_plan.py`
- `dev-docs/plan/org-eligibility-output/*.md`

## Implementation steps

- Run the focused unittest module.
- Run full unittest discovery.
- Run `org-plan` against the parser's latest-save default and inspect representative nationality and owner-trait candidates.
- Record exact outcomes and remaining limitations.

## Acceptance criteria

- All focused and full tests pass.
- Latest-save output includes requirements and both eligible and ineligible councilor diagnostics.
- At least one nationality-gated market org is no longer falsely rejected solely because a prospective owner has a different homeland.

## Validation commands

- python -m unittest discover -s tests -v

## Manual smoke tests

- python tools\ti_save_parser.py org-plan --compact

## Rollback risks

- The smoke test depends on a local save and templates; automated correctness remains covered by synthetic tests.

## Progress

- Complete.

## Decision log

- Synthetic tests cover both nation-interest satisfaction paths, missing nation interest, required/prohibited traits, and planner consistency.
- The latest-save smoke test is read-only and does not add user save data to the repository.

## Outcomes / Retrospective

- `python -m unittest discover -s tests -v`: 90 tests passed.
- Latest Broken Earth save (`CooperateCouncil`) produced 14 market candidates at the final smoke-test save state: 6 with nation-interest requirements, 6 with owner-trait requirements, 8 with at least one eligible councilor, and 7 with explicit ineligible reasons.
- `RandomNGO12` and `RandomResearch21` were accepted through `councilorHomeNation`, demonstrating the faction-wide homeland path on the live save.
- Multiple nationality-gated candidates without faction interest were retained in candidate output with `faction lacks interest in required nation` reasons and excluded from recommendations.
- Focused tests also cover direct `TIControlPointState.nation`, the nation-state fallback, unresolved home nations, public helper faction recovery, and full `calculate_org_plan` propagation.
