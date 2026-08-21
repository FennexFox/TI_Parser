# Phase 02: Strict dependency and catalog foundation

## Goal

- Establish strict dependency, scenario selection, catalog validation, and provenance contracts.

## Scope

- Add `RuntimeCatalogs`, manifest/envelope validation, `CalculationDependencyError`, strict effect resolution,
  and structured incomplete CLI failures.

## Non-goals

- Do not migrate research or ship calculations beyond the adapters required to keep tests green.

## Affected files

- `tools/ti_parser_catalogs.py`, `tools/ti_parser_core.py`, `tools/ti_parser_cli.py`, focused tests and manifest.

## Implementation steps

- Validate file SHA, payload fingerprint, schema, duplicate rows, and exact supported scenario.
- Make requested effect contexts resolve every named active effect and reject invalid operation/value data.
- Stop resolving installed templates during normal CLI startup; reserve `--templates-dir` for verification.

## Acceptance criteria

- Corrupt/missing/unsupported catalogs and relevant missing effects fail with structured dependencies.
- An effect in a context not evaluated by a calculator does not cause a false failure.

## Validation commands

- python -m unittest discover -s tests -v

## Manual smoke tests

- Exercise a normal command with all raw loaders replaced by exceptions.

## Rollback risks

- CLI compatibility risk is limited by retaining successful result fields and exit code 2 for dependency failures.

## Progress

- Not started.

## Decision log

- No decisions recorded yet.

## Outcomes / Retrospective

- Not completed yet.
