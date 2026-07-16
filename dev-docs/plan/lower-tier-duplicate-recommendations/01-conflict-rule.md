# Phase 01: Implement one-per-hab conflict grouping and regressions

## Goal

- Prevent lower-tier, higher-tier, and alternate mining-complex recommendations when a mutually exclusive one-per-hab module is already present.

## Scope

- Add a helper that derives the occupied names relevant to a one-per-hab candidate from the module template catalog.
- Extend `module_unmet_requirements` with an optional habitat module template map and use the helper for its existing one-per-hab reason.
- Pass the map from candidate, upgrade, and project-unlock analysis callers.
- Add candidate-row and upgrade-row regression tests.

## Non-goals

- Do not change candidate scoring, affordability, slot planning, or resource economics.
- Do not collapse every one-per-hab template into one global exclusive group.
- Do not alter the generated module catalog.

## Affected files

- `tools/ti_save_parser.py`
- `tests/test_hab_plan.py`

## Implementation steps

- Compute the undirected upgrade-family component using template names and `upgradesFromName` links.
- Add every `mine=true` template to the conflict set when the candidate is a mining complex.
- Retain exact-name behavior when no template map is supplied.
- Exercise actual `hab_module_candidate_rows` and `hab_module_upgrade_rows` call paths with patched template data.

## Acceptance criteria

- A colony mining complex blocks outpost, settlement, and automated mining candidates for an empty slot.
- An unrelated one-per-hab family remains eligible.
- Replacing an outpost mining complex with its settlement upgrade remains eligible.
- Existing habitat-plan tests and the full test suite pass.

## Validation commands

- python -B -m unittest discover -s tests -p "test_hab_plan.py" -v
- python -B -m unittest discover -s tests -v

## Manual smoke tests

- Run hab-plan for the affected Resistance settlement and confirm lower-tier/alternate mining modules are absent

## Rollback risks

- Over-broad grouping could hide valid independent one-per-hab modules; regression coverage must retain an unrelated candidate.
- Failing to subtract the replaced template before family evaluation could suppress every legitimate upgrade row.

## Progress

- Completed.

## Decision log

- Use upgrade connectivity plus the existing `mine` flag instead of display-name or tier heuristics.
- Preserve the existing `one per hab already present` reason so downstream summaries remain stable.

## Outcomes / Retrospective

- Added `module_one_per_hab_conflict_names`, which traverses upgrade links in both directions and adds the mining exclusivity set only for mining candidates.
- Passed the habitat module template map through empty-slot candidate, explicit upgrade, and project-unlock analysis paths.
- Added regressions proving that generic non-mining upgrade families and colony/lower-tier/automated mining duplicates are excluded while an unrelated one-per-hab family and a legal in-place mining upgrade remain available.
- Validation: 17 focused habitat-plan tests and 72 repository tests passed.
