# Phase 02: Shared execution and session reuse

## Goal

- Pure calculation paths and session-owned reuse

## Scope

- Issue #5 application boundary, existing CLI compatibility.

## Non-goals

- MCP, UI, history, new formulas and generated catalog values.

## Affected files

- tools/ti_parser_application.py; tools/ti_parser_commands.py; tools/ti_parser_session.py; tools/ti_parser_catalogs.py; tools/ti_parser_snapshot.py

## Implementation steps

- Extract return-value handlers and retain CLI wrappers; share catalog cache per session; lazily build snapshot with existing index.

## Acceptance criteria

- Sequential calls reuse one load/index and matching catalog bundles; CLI results retain field selection and rounding.

## Validation commands

- python -m pytest tests/test_parser_cli.py tests/test_runtime_catalogs.py tests/test_package_only_runtime.py -q

## Manual smoke tests

- Run multiple direct calculations against one synthetic save.

## Rollback risks

- Mock patch targets move to the owning application module; default catalog scopes still discard caches.

## Progress

- Not started.

## Decision log

- Python API only for envelope; raw/types remain inspection routes outside primary recommendations.

## Outcomes / Retrospective

- Not completed yet.
