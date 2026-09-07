# Phase 20: BuildNavy completion simulation

## Goal

Implement the audited BuildNavy completion and merge PR #2 after validation.

## Scope

Human army selection by control-point priority and save order, conversion to Naval, live counts and maintenance, post-completion validity, and the existing army-priority market effect.

## Non-goals

Combat, movement, accessibility graph simulation, and game notifications remain outside projected output.

## Affected files

Projection engine, save extraction, mechanics registry, projection tests, audit document, and README.

## Implementation steps

1. Audit GetNextNavy, OnBuildSealiftPriorityComplete, and TIArmyState.AddNavy directly from the installed DLL.
2. Preserve required army type and ordering; fail closed on missing blocking inputs.
3. Implement conversion and downstream coverage with regression tests.
4. Run general and real-save suites, review changes, commit, push, and merge PR #2.

## Acceptance criteria

The highest eligible control point's first standard Human army gains Naval deployment without a new army identity; counts, maintenance, and validity follow that conversion. Market uncertainty retains separate coverage.

## Validation commands

- python -m pytest -q
- TI_PARSER_REAL_SAVE set to the user-specified OneDrive TerraInvicta ExitSave.gz, then python -m pytest -q tests/test_nation_projection_real_save.py
- strict phase-plan validation and git diff --check

## Manual smoke tests

Use the real save to exercise a qualifying nation's BuildNavy plan and inspect conversion events and coverage.

## Rollback risks

Conflating a naval army with a newly created army changes maintenance and future capacity. Preserve identity and verify the exact game selection order.

## Progress

DLL selection and mutation bodies verified; completion implemented and reviewed.
Catalog byte integrity repaired by regeneration in `b8d49d5`:
all seven manifest SHA-256 entries match canonical LF files, with no catalog
payload changes. Runtime catalog/package-only targeted suite: 25 passed.

## Decision log

GetNextNavy counts Human armies per CP, scans CPs descending for total above Naval count, then selects the first Standard army in save order for that CP. AddNavy changes deployment and dirty flags only. Completion also invokes ModifyMarketValuesForArmyPriority.

The DLL's `standardArmies` includes Naval deployment, unlike the existing public
non-naval count. Preserve the JSON count convention while retaining naval armies
in BuildArmy occupancy, home-region/CP selection, and unrest calculations.

Catalog integrity blocked real-save validation, so regenerate with the existing
LF-safe generator before completing this phase. Installed-source verification
passes generated runtime domains but reports pre-existing research DLC source
hash drift; research payload updates are outside this navy change.

## Outcomes / Retrospective

Implemented deterministic Human army conversion, identity-preserving live counts,
next-tick navy maintenance, post-completion revalidation, and separately covered
mean-input market mutation. Added fail-closed ArmyType/DeploymentType extraction
and regressions for saved order, descending CP selection, destroyed references,
last-convertible-army validity, and preserved BuildArmy/unrest behavior.

Final general suite: `python -m pytest -q` — 293 passed, 13 skipped,
25 subtests passed. Strict 20-phase plan validation and `git diff --check` passed.
The real-save navy smoke passed with the observed army target and explicitly
synthetic near-completion progress; source save bytes are not modified.
Independent review found no remaining material blocker after corrections.
Final committed-byte export verification and PR merge follow this phase commit.
