# Phase 05: Package-only command matrix

## Goal

- Protect every major normal-runtime command from raw game-template access.

## Scope

- Bounded synthetic CLI matrix plus loader/install discovery traps and the existing static guard.

## Non-goals

- No performance benchmark or late-game exhaustive planner search.

## Affected files

- `tests/test_package_only_runtime.py` and reusable synthetic fixture helpers if needed.

## Implementation steps

- Trap candidate/install directory discovery, scenario resolution, and raw named/trait loaders at defining modules and imported aliases.
- Run summary, topbar/forecast, research/UI/plan, bounded org-plan, hab UI/plan, saved-design ship-plan, claims, and AI diagnostics.
- Require exit 0 and non-incomplete results for valid fixtures; test unsupported scenario separately.

## Acceptance criteria

- Every listed command reaches its intended calculation path without a raw-loader call; org and ship tests remain bounded.

## Validation commands

- python -m unittest tests.test_package_only_runtime tests.test_runtime_raw_loader_guard -v

## Manual smoke tests

- Inspect command JSON to confirm research modifiers, org candidates, hab rows, forecast, and ship simulation are actually populated.

## Rollback risks

- A single empty mega-fixture could produce false confidence; use command-specific minimal state with at least one relevant reference.

## Progress

- Complete. The normal-runtime CLI matrix runs through command-specific bounded synthetic saves with raw loader and install discovery traps active.

## Decision log

- Split fixtures by calculation domain (base/research, org, hab/forecast, ship, claims, AI) instead of using one permissive mega-fixture.
- Trap all five raw/install entry points both in `ti_parser_core` and in the aliases imported by `ti_save_parser`.
- Keep planner paths bounded with `org-plan --top 1 --max-actions 1 --beam-width 1`, `hab-plan --top 1`, and `ship-plan --top 1 --design`.
- Require a command-specific populated result in addition to exit code 0 and absence of `status: incomplete`.

## Outcomes / Retrospective

- Protected summary, topbar, research, research UI/plan, org plan, hab UI/plan, resource forecast, saved-design ship simulation, nation claims diagnostics, and AI fleet diagnostics from raw runtime access.
- The static raw-loader guard remains part of the focused acceptance command, complementing the dynamic alias/defining-module traps.
- Focused validation passes all 5 package-only/static-guard tests; full validation passes 200 tests with one expected local-fixture skip.
