# Phase 02: Move remaining implementation to domain modules

## Goal

- Move remaining implementation to domain modules

## Scope

- tools/ti_save_parser.py, new domain modules, tests and README

## Non-goals

- Mechanics changes, output redesign, generator changes, performance claims.

## Affected files

- tools/ti_save_parser.py, new domain modules, tests and README

## Implementation steps

- Move exact bodies; add explicit imports and compatibility exports; retarget mock ownership; verify AST/signature parity and full tests.

## Acceptance criteria

- Facade owns only entry functions, domain modules do not import facade, behavior tests pass.

## Validation commands

- python -B -m pytest -q -p no:cacheprovider

## Manual smoke tests

- Compare baseline public signatures and real-save command output; verify independent module imports.

## Rollback risks

- Cross-module references and test patch targets must follow ownership; revert the phase as a unit.

## Progress

- Complete. Implemented 14 modules and an explicit public facade (9,727 to 629 lines including compatibility imports).

## Decision log

- Preserve function, class and assignment bodies exactly. 457 top-level AST nodes match the baseline.
- Separate research planning from base research, and keep shared solar/body primitives in hab_ui. This removes dependency cycles without function-local imports, injected facade contexts, or global rebinding.
- Shared settings live in config; existing configured calculation wrappers and save-state helpers live in runtime. The facade contains only imports, build_parser and main.
- Mock patches target the implementation lookup module; direct public calls remain facade-compatible.

## Outcomes / Retrospective

- All moved global references resolve. Independent module imports and acyclic dependency tests pass (3 tests including raw-loader guard, 14 subtests).
- Existing mock assertions and fixtures preserved; focused suite: 78 passed, 5 subtests passed.
- Full suite: 327 passed, 13 skipped, 59 subtests passed.
- Actual-save baseline comparison against 36539ae: 11/11 raw stdout, parsed JSON and exit codes identical. Seven successful commands and four pre-existing incomplete results are preserved.
- Independent review found no missing public exports or signature/default mismatches.
