# Phase 04: Enforce the per-councilor 15-org assignment limit

## Goal

- Prevent individual and committee org recommendations from producing a roster with more than 15 assigned orgs and make the count constraint visible in output.

## Scope

- Add a canonical maximum-org constant.
- Report org count, remaining org slots, and independent Administration/count validity in roster summaries.
- Require removal of enough existing orgs before adding a candidate to a full roster.
- Add capacity details to recommended actions and candidate diagnostics where they clarify whether direct assignment or replacement is required.

## Non-goals

- Changing nation-interest, owner-trait, cost, or scoring rules.
- Reconstructing detention, Earth-system location, or market technology/ideology checks.

## Affected files

- `tools/ti_parser_org.py`
- `tools/ti_save_parser.py`
- `tests/test_org_plan.py`
- `tests/test_parser_org.py`
- `dev-docs/plan/org-eligibility-output/*.md`

## Implementation steps

- Verify the exact game limit and whether it applies after removals for both market and owned-inventory assignment.
- Extend `org_plan_roster_summary` with count-capacity fields while preserving existing keys.
- Include count overflow in `validCapacity` and enumerate the minimum removal count required by both tier and count constraints.
- Expose before/after org counts and remaining slots on actions and roster output.
- Add focused boundary tests for 14→15, 15→replacement, and attempts to retain 16 orgs.

## Acceptance criteria

- A 14-org roster may receive a fifteenth org when Administration capacity permits.
- A 15-org roster may receive a new org only through a recommendation that removes at least one existing org.
- No returned action or committee final roster contains more than 15 orgs.
- Output distinguishes Administration capacity from org-count capacity.
- Existing eligibility and planning tests remain green.

## Validation commands

- `python -m unittest tests.test_org_plan tests.test_parser_org -v`
- `python -m unittest discover -s tests -v`

## Manual smoke tests

- `python tools\ti_save_parser.py org-plan --compact`

## Rollback risks

- Removal enumeration is bounded for performance; the bound must account for both incoming tier and org-count overflow or valid replacements could be missed.

## Progress

- In progress.

## Decision log

- Count capacity is represented separately from Administration tier capacity, while the backward-compatible `validCapacity` field requires both.

## Outcomes / Retrospective

- Not completed yet.
