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

- Completed.
- Added a temporary Git-archive verifier for the full suite, package-only/static guard suite, and every supported catalog scenario.
- Updated README contracts for package-only runtime, required versus optional dependencies, ship deltas, nested claim diagnostics, and the fresh-export release gate.
- Replaced stale research/ship planner claims that local template files were required with packaged-catalog provenance while retaining the legacy nullable `templatesDir` field for result-shape compatibility.

## Decision log

- The verifier uses the current Python interpreter by default and fails explicitly when Git, archive creation, tests, or scenario loading fails.
- The archive is extracted only to an isolated temporary directory and is removed after the result is reported.
- Both dynamic package-only traps and the static raw-loader guard run inside the archive; the full suite remains an independent first check.
- Final AST/loader audit found no forbidden normal calculation/CLI edge. The only runtime-module helper edges are the documented legacy `load_trait_templates -> load_named_templates` and `scenario_template_sources -> load_named_templates` paths; neither is reached by normal commands and both remain covered by the static allowlist.

## Outcomes / Retrospective

- Working-tree full validation passed 200 tests with one expected local-fixture skip; the focused package-only/static guard suite passed 5 tests.
- The committed fresh export independently passed the same 200-test full suite and 5-test package-only/static guard suite.
- All six supported scenarios (`2003Scenario`, `2026Scenario`, `2030Scenario`, `2070Scenario`, `BrokenEarthScenario`, and `ModernScenario`) loaded from the archive with bundle fingerprint `43239f441b8969a1088f261f84b34aa770056b444f4e12f63b7ac4437b258c9d`.
- The verifier removed its temporary export and left the source worktree unchanged.
