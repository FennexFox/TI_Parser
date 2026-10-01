# Phase 01: Prevent ambiguous selections and silent malformed input.

## Goal

- Prevent ambiguous selections and silent malformed input.

## Scope

- Core/errors, CLI, command/domain error boundaries, selector and input tests.

## Non-goals

- No game formula changes, catalog regeneration, projection restructuring or external publication.

## Affected files

- Core/errors, CLI, command/domain error boundaries, selector and input tests.

## Implementation steps

- Add typed expected errors; unique exact/partial resolution and integer ID selectors; validate save/index structure; JSON error boundary and exit codes.

## Acceptance criteria

- Ambiguous or corrupt input never silently produces a result; normal calculations stay unchanged.

## Validation commands

- python -m pytest tests/test_beta_input.py tests/test_beta_cli.py -q

## Manual smoke tests

- Help and missing-save error contracts.

## Rollback risks

- Lookup/exception contracts change intentionally; revert phase as one unit.

## Progress

- Implemented; targeted beta CLI 4 passed and runtime regression 349 passed, 13 skipped, 75 subtests passed.

## Decision log

- Use user-approved beta contract; root integrates independent worker changes.

## Outcomes / Retrospective

- Validated typed errors and selectors. Real local save inspection established empty {} collections are valid; nonempty non-list collections remain errors. No formulas changed.
- Integration review rejects unresolved/wrong-type human faction references and inconsistent metadata, and routes AI/claims selector failures through typed input errors. Final integrated suite: 392 passed, 13 skipped, 75 subtests passed on Windows Python 3.14.

