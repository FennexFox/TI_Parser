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

- Completed.
- The command wrapper now preserves the calculator's claim-domain diagnostics under `calculationDiagnostics.claims` and attaches catalog provenance under `.runtime`.
- A command-level JSON regression exercises the actual wrapper and verifies both branches.

## Decision log

- Diagnostic output intentionally gains one nesting level; non-diagnostic claim JSON is unchanged.
- Claim reasoning remains calculator-owned, while payload fingerprints and scenario overlay selection remain runtime-catalog-owned.

## Outcomes / Retrospective

- All 8 focused nation-claim tests pass.
- Full validation passes 199 tests with one expected local-fixture skip.
- The wrapper regression preserves selected scenario, threshold, formula, decompiled-rule source, assumptions, limitations, missing dependencies, runtime fingerprint, and override metadata without one diagnostic source overwriting the other.
