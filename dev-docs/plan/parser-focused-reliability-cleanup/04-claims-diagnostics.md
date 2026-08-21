# Phase 04: Claims diagnostics merge

## Goal

- Preserve claim-domain provenance when the CLI attaches runtime catalog diagnostics.

## Scope

- Diagnostic-mode wrapper output and its regression tests.

## Non-goals

- No claim rule changes or new reconstruction.

## Affected files

- `tools/ti_save_parser.py`, `tests/test_nation_claims.py`.

## Implementation steps

- Pop the calculator's domain diagnostics, then emit `calculationDiagnostics.runtime` and `.claims`.
- Exercise the real command wrapper rather than only the calculator.

## Acceptance criteria

- CLI JSON retains scenario, threshold, formula, rule source, assumptions, limitations, missing dependencies, and runtime fingerprints.

## Validation commands

- python -m unittest tests.test_nation_claims -v

## Manual smoke tests

- Run `nation-claims --diagnostics --compact` against the synthetic claims fixture and inspect both diagnostic branches.

## Rollback risks

- This intentionally changes only diagnostic-mode nesting; normal claim JSON must remain unchanged.

## Progress

- Not started.

## Decision log

- No decisions recorded yet.

## Outcomes / Retrospective

- Not completed yet.
