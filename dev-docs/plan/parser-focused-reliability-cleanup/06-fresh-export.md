# Phase 06: Fresh-export gate and documentation

## Goal

- Make committed LF artifacts—not the current checkout—the final acceptance source.

## Scope

- Cross-platform fresh-export verifier, README architecture contract, final audit and reports.

## Non-goals

- No CI provider configuration or catalog schema migration.

## Affected files

- `tools/verify_fresh_export.py`, `README.md`, phase documents.

## Implementation steps

- Build a temporary `git -c core.autocrlf=false archive HEAD`, run the full suite and package-only suite inside it, and validate all supported catalog scenarios.
- Document normal package-only runtime, generation-only raw inputs, integrity/fail-closed semantics, command coverage, ship overlays, and nested claims diagnostics.
- Re-run raw-loader search and record any allowlisted legacy helper edges.

## Acceptance criteria

- Working-tree, package-only, and fresh-export suites pass independently; README matches implementation.

## Validation commands

- python -m unittest discover -s tests -v
- python -m unittest tests.test_package_only_runtime -v
- python tools/verify_fresh_export.py

## Manual smoke tests

- Compare result counts and supported-scenario catalog loads between working tree and archive.

## Rollback risks

- The verifier must not mutate the source tree and must surface missing Git explicitly; run it after the final code commit.

## Progress

- Not started.

## Decision log

- No decisions recorded yet.

## Outcomes / Retrospective

- Not completed yet.
