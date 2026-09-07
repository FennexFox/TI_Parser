# Prevent lower-tier duplicate habitat recommendations

## Issue Target And Scope Summary

- Issue target: lower-tier-duplicate-recommendations
- Title: Prevent lower-tier duplicate habitat recommendations
- Source plan: None
- Scope: Fix habitat candidate filtering so an occupied one-per-hab upgrade family is not recommended again at a lower or higher tier, while preserving explicit in-place upgrades.

## Strategy

- Build one conflict set from the undirected `upgradesFromName` component for each one-per-hab candidate.
- Treat all templates with `mine=true` as an additional exclusive set so automated and conventional mining complexes cannot coexist in recommendations.
- Pass the full habitat module template map through every production caller of `module_unmet_requirements`.
- Cover both empty-slot candidates and valid in-place upgrades with focused regressions before checking the latest AutoSave output.

## Phase Order

1. [Implement one-per-hab conflict grouping and regressions](01-conflict-rule.md)
2. [Validate planner output against the latest AutoSave](02-autosave-validation.md)

## Phase Dependencies

- Phase 1 has no phase dependency beyond resolved issue context.
- Phase 2 depends on completion and validation of phase 1.

## Source Of Truth Decisions

- `00-master-plan.md` is the phased implementation plan source of truth.
- Phase files in this directory define phase-local scope and validation.
- Earlier monolithic plans are input material only unless explicitly retained.

## Global Validation Expectations

- python -B -m unittest tests.test_hab_plan -v
- python -B -m unittest discover -s tests -v

## Known Risks And Assumptions

- The exact-name check remains the fallback when callers do not have a module template map.
- Independent one-per-hab families must remain mutually compatible; only upgrade-connected templates share a generic conflict set.
- `Helium-3Mine` is not flagged as a mining complex and remains outside the mining exclusivity set.
- The upgrade path already subtracts the replaced module from `module_counts`; the new family test must use those adjusted counts.
- `candidateSummary.topPower` is a capability shortlist, not a request to add generation; actionable advice must first check the habitat-local projected power net and available slots.

## Implementation Status

- Phase 1 completed: upgrade-family and mining exclusivity checks are implemented with production-call-path regressions.
- Phase 2 completed: 72 tests passed and the latest Resistance AutoSave no longer shows the observed duplicate mining recommendations.
- AutoSave review correction: Yue Jin has +145 projected local power and no planned empty slot, so the earlier manual suggestion to add a power plant was withdrawn; planner logic stayed unchanged and the output notes now distinguish power shortlists from actual power-support recommendations.
