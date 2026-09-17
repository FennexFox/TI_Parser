# Phase 03: Verify final compatibility from checkout and committed export

## Goal

- Verify final compatibility from checkout and committed export

## Scope

- Architecture/import regression tests and plan records

## Non-goals

- Mechanics changes, output redesign, generator changes, performance claims.

## Affected files

- Architecture/import regression tests and plan records

## Implementation steps

- Run full tests, fresh export and real-save CLI parity against baseline; record exact results.

## Acceptance criteria

- Tests and parity pass; reviewed commits and clean worktree.

## Validation commands

- python -B -m pytest -q -p no:cacheprovider

## Manual smoke tests

- Compare baseline public signatures and real-save command output; verify independent module imports.

## Rollback risks

- Cross-module references and test patch targets must follow ownership; revert the phase as a unit.

## Progress

- Complete. Accepted implementation commit bda1c67.

## Decision log

- Acceptance includes exact output comparison against commit 36539ae, not only passing refactored tests.
- Actual-save incomplete results for WaterHeatSink and SunMarsL1 remain unchanged; this extraction does not alter mechanics or catalog coverage.
- Export verification runs committed LF-preserving bytes on Windows; no claim of native execution on another OS.

## Outcomes / Retrospective

- Full pytest: 327 passed, 13 skipped, 59 subtests passed.
- `python -B tools/verify_fresh_export.py`: complete; 340 unittest cases (14 skipped), package-only suite 6 passed, all 6 supported scenarios loaded.
- All 14 modules import independently without loading the facade, and the domain import graph is acyclic.
- 457 original function/class/assignment AST nodes match exactly; no unresolved moved globals.
- Actual-save CLI parity: 11/11 raw stdout, parsed JSON and exit codes match baseline. Commands: research, research-ui, research-plan --top 2, hab-slots, hab-plan --top 2, ship-plan --top 2, project-analysis --top 2, topbar, world-ui, nation-ui KOR, nation-projection KOR --days 2. Seven exit 0; four retain the exact pre-existing incomplete output and exit 2.
- CLI help, plan helper validation, and git diff --check passed.
- Tests that replace implementation dependencies now patch the owning modules; public callable exports and signatures remain available.
