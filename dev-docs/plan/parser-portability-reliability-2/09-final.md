# Phase 09: Final regression documentation and audit

## Goal

- Finish regression, documentation, residual dependency audit, and evidence-based handoff.

## Scope

- Full suite, raw-loader rescan, phase outcomes, README, catalog docs, final comparison report.

## Non-goals

- No unrelated refactor or save mutation.

## Affected files

- All touched runtime, test, data, README, docs, and plan files.

## Implementation steps

- Run all tests and verification commands; fix failures rather than documenting them away.
- Search runtime modules for prohibited loaders/paths and document justified exceptions.
- Record silent failures removed, catalogs, scenarios, API/CLI changes, tests, comparison results, and unknown mechanics.

## Acceptance criteria

- Every requested completion criterion is satisfied or an evidenced blocker is recorded; repository is clean and reviewable.

## Validation commands

- python -m unittest discover -s tests -v

## Manual smoke tests

- Run representative package-only commands from the CLI and inspect diagnostic JSON.

## Rollback risks

- Generated catalogs are large; stage only intentional outputs and verify hashes before commit.

## Progress

- Complete: residual loader audit, README, phase records, full regression, real-save smoke tests, and raw/package verification are complete.

## Decision log

- Two raw helper-to-helper edges remain allowlisted in `ti_parser_core`; no normal command or calculator reaches them.

## Outcomes / Retrospective

- Full suite passes with one expected local-fixture skip; Broken Earth catalog verification passes 12/12.
