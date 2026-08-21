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

- Not started.

## Decision log

- No decisions recorded yet.

## Outcomes / Retrospective

- Not completed yet.
