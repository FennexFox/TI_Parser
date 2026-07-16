# Phase 02: Validate planner output against the latest AutoSave

## Goal

- Confirm the corrected filters remove the observed duplicate recommendations from the newest Resistance AutoSave without hiding legitimate module or upgrade rows.

## Scope

- Run the focused and full automated suites.
- Run `hab-plan` against the newest local save for the affected settlement and inspect candidate and upgrade templates.
- Record the exact validation result and any remaining limitations.

## Non-goals

- Do not rebalance module scores or make new economic recommendations.
- Do not modify the save, game templates, or generated catalogs.

## Affected files

- `dev-docs/plan/lower-tier-duplicate-recommendations/00-master-plan.md`
- `dev-docs/plan/lower-tier-duplicate-recommendations/02-autosave-validation.md`

## Implementation steps

- Identify the affected Resistance habitat from the previously observed mining duplicates.
- Re-run the planner with enough output rows to detect the former candidates.
- Confirm conventional lower tiers and the automated mining complex are absent while an explicit legal upgrade, if present, remains available.
- Capture test counts and the AutoSave result in the phase outcome.

## Acceptance criteria

- Focused and full test suites exit successfully.
- The affected settlement no longer recommends an additional mining complex in an empty slot.
- Phase and master plan documents contain no unresolved implementation placeholders.

## Validation commands

- python -B -m unittest discover -s tests -p "test_hab_plan.py" -v
- python -B -m unittest discover -s tests -v

## Manual smoke tests

- Run hab-plan for the affected Resistance settlement and confirm lower-tier/alternate mining modules are absent

## Rollback risks

- A newer save may no longer contain the exact affected habitat state; if so, use the latest reproducible save and record that limitation.
- Cache reuse can mask parser changes, so the smoke command must use `--refresh-cache`.

## Progress

- Completed.

## Decision log

- Used `Chevalier Paul 기지` to reproduce the occupied colony-mine case and `제502자원개발단 Black Hawk` to verify an actual settlement-to-colony mining upgrade remains available.
- Rebuilt the parser cache before the first smoke run so the result necessarily used the corrected filter.
- Classified `candidateSummary.topPower` as reference data rather than an actionable recommendation after checking Yue Jin's habitat-local power balance.

## Outcomes / Retrospective

- Latest local `Autosave.gz`: `Chevalier Paul 기지` has one `ColonyMiningComplex` and eight empty slots; none of `OutpostMiningComplex`, `SettlementMiningComplex`, `ColonyMiningComplex`, or `AutomatedMiningComplex` appeared among 69 candidates.
- `제502자원개발단 Black Hawk` has one `SettlementMiningComplex`; lower-tier and automated mining candidates were absent, while `ColonyMiningComplex` remained present in the upgrade summary.
- Yue Jin projects 2,925 generation against 2,780 consumption (net +145), has no planned empty slots, and has an empty `suggestedFill`; adding a power plant was therefore removed from the manual recommendation list, and `sourceNotes` now state that `topPower` is not an actionable recommendation.
- Focused habitat-plan suite: 17 tests passed. Full repository suite: 72 tests passed.
