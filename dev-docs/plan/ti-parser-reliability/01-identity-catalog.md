# Phase 01: Player identity and packaged module catalog

## Goal

- Make player identity and module data deterministic and fail closed.

## Scope

- Replace Resistance/first-faction fallbacks, preserve overrides, load packaged catalog by default,
  and expose catalog metadata.

## Non-goals

- Effect semantics and hab lifecycle refactoring.

## Affected files

- `tools/ti_parser_core.py`, `tools/ti_save_parser.py`, `tools/ti_parser_cli.py`, tests.

## Implementation steps

- Add strict player candidate reconciliation and ambiguous override handling.
- Add catalog rehydration, fingerprint diagnostics, and fatal missing-template handling.
- Route every runtime hab-module load through the packaged catalog.

## Acceptance criteria

- Academy is selected from `ExitSave(3).gz`; missing/ambiguous player and catalog data fail.

## Validation commands

- python -m unittest discover -s tests -v

## Manual smoke tests

- Run default and overridden topbar commands; remove access to raw module templates and confirm MC.

## Rollback risks

- Snapshot schema bump invalidates old compact caches.

## Progress

- Completed.

## Decision log

- Runtime module data has no implicit raw-template fallback; the generator remains raw-template based.

## Outcomes / Retrospective

- `CooperateCouncil` resolves as player and packaged Operations Center MC preserves 183 capacity.
