# Phase 01: Cache, coverage and CLI correctness

## Goal

- Fix confirmed correctness and reliability defects.

## Scope

- Cache fingerprints/atomic recovery; advisor expected coverage; MC missing-position dependencies; CLI defaults, verification status, structured missing effects.

## Non-goals

- Domain extraction and new game mechanics.

## Affected files

- tools/ti_parser_core.py, ti_parser_snapshot.py, ti_parser_income.py, ti_parser_nation_projection.py, ti_parser_cli.py, ti_save_parser.py; focused tests; mechanics audit docs.

## Implementation steps

- Restore trait catalog committed bytes; implement independent fixes with regression tests; run targeted and full suites.

## Acceptance criteria

- Catalog updates invalidate snapshots, invalid runtime data cannot hide behind cache hits, corrupted caches rebuild; unknown CP positions fail closed; expected timing propagates; CLI outcomes are machine-readable.

## Validation commands

- python -B -m pytest -q -p no:cacheprovider

## Manual smoke tests

- Invoke default summary and failed verification with synthetic inputs; exercise corrupt snapshot and catalog refresh.

## Rollback risks

- Public compatibility must remain; revert the phase commit rather than weakening checks.

## Progress

- Implemented all seven confirmed defects. Full pytest passes (311 passed, 13 skipped, 36 subtests). Real temporary catalog tests prove changed traits refresh calculated attributes and corrupt catalog bytes fail closed.

## Decision log

- Preserve raw-byte SHA checks. Restored only CRLF-equivalent trait/org/ship checkout bytes from HEAD. Catalog verification uses code 2 for both failed and partial results. Missing MC positions block only remainder-sensitive allocations. Expected advisor coverage includes pending renewal; an unused schedule remains exact.

## Outcomes / Retrospective

- Phase complete. Targeted cache/runtime suite: 23 passed. Full suite and git diff --check pass.
- Regression tests cover default/explicit summary parity, verification exit statuses and no-save handling, structured missing effects, MC subset ownership, advisor clear/renew gaps, and cache corruption/atomic replacement. Existing successful outputs remain compatible.
