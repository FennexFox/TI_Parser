# Advise mission lifecycle projection

## Issue Target And Scope Summary

- Issue target: user request
- Scope: replace continuous Advisor bonuses with the audited recurring Advise lifecycle: saved mission cadence, expected resolution timing, automatic success, assignment movement, and renewal-cost reporting.

## Strategy

- Preserve saved Advisor effects until mission-phase bookkeeping clears them.
- Treat plan `advisors` as desired repeat orders, not immediate nation mutation.
- Reapply desired advisors at the audited mean resolution instant for order 0.
- Read mission timing from the save and package template facts used at runtime.
- Report future Influence requirements; whole-faction resource income stays outside nation projection.

## Phase Order

1. [Discovery and boundaries](01-discovery.md)
2. [Implement mission lifecycle modeling](02-implementation.md)
3. [Verification and cleanup](03-verification.md)

## Phase Dependencies

- Phase 1 establishes the mechanics contract.
- Phase 2 depends on phase 1 and leaves the parser usable.
- Phase 3 depends on phase 2 and completes regression and real-save validation.

## Source Of Truth Decisions

- This directory is the source of truth for the Advise lifecycle extension.
- `docs/plan/nation_projection/` remains authoritative for the existing engine and is amended where its continuous-renewal assumption is superseded.
- Installed DLL/templates are audit inputs; generated catalogs plus Python rules are runtime sources.

## Global Validation Expectations

- `py -3 -m unittest tests.test_nation_projection tests.test_nation_projection_cli tests.test_runtime_catalogs tests.test_catalog_generators tests.test_mechanics_registry tests.test_parser_income`
- `py -3 -m unittest discover -s tests -p 'test_*.py'`
- `py -3 tools/ti_save_parser.py catalog-verify --catalog nation-development`

## Known Risks And Assumptions

- Mission order within a resolution segment is randomized. Projection uses the exact mean stagger instant implied by `FinalizeCouncilorMissions.StaggerMissionResolutions` and marks it expected timing.
- Future Influence availability, target invalidation, detention, and competing councilor orders are not forecast. Required Influence is reported and the policy assumes renewals stay actionable and funded.
- Mission cadence changes with campaign age; repeat-change thresholds must not be frozen.
