# Phase 01: Runtime dependency and silent-fallback audit

## Goal

- Record every raw loader and silent fallback before changing runtime behavior.

## Scope

- Classify loader usage as generator, explicit verification, or normal runtime; add a normal-runtime guard test.

## Non-goals

- Do not migrate calculations or change output contracts in this phase.

## Affected files

- `dev-docs/plan/parser-portability-reliability-2/`, runtime-loader guard tests.

## Implementation steps

- Capture `load_named_templates`, `load_trait_templates`, game/DLC path, and localization call sites.
- Record missing effect/trait/org/research/ship rows and numeric fallbacks that currently produce plausible output.
- Define the generator/verification allowlist checked by the guard.

## Acceptance criteria

- Audit covers every Python runtime module and the guard fails on a newly introduced prohibited call.

## Validation commands

- python -m unittest discover -s tests -v

## Manual smoke tests

- Run the guard against the current tree and review its allowlist.

## Rollback risks

- An overly broad text guard can reject docs/tests; restrict it to runtime modules and parsed call sites.

## Progress

- Complete: loader/silent-fallback inventory documented and AST regression guard added.

## Decision log

- Normal CLI dispatch is classified as runtime even when an installed game is auto-discovered.

## Outcomes / Retrospective

- The guard intentionally snapshots the current debt so each migration can remove entries while any new edge fails.
