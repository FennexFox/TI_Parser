# Phase 03: CLI faction contribution and diagnostics integration

## Goal

- Expose nation projection through the existing JSON-first CLI and separate nation state from target-nation faction contribution.

## Scope

- Add `nation-projection` arguments and raw command dispatch.
- Reuse income helpers for observed/projection contribution views.
- Emit requested output hierarchy, diagnostics, comparison, and advisor provenance.

## Non-goals

- No changes to `nation-ui` semantics and no future whole-faction totals.

## Affected files

- `tools/ti_parser_cli.py`
- `tools/ti_save_parser.py`
- `tools/ti_parser_income.py` where pure value helpers are required
- CLI/integration tests

## Implementation steps

1. Add CLI flags for days, plan file, checkpoints, faction, details, and diagnostics.
2. Resolve save/nation/faction/catalog inputs and call the projection core.
3. Emit `initialState`, per-plan projections/contributions/transitions/events/goals, comparison, coverage, rules, limitations, and source notes.
4. Keep incomplete plans out of authoritative ranking.

## Acceptance criteria

- Example commands parse and produce JSON.
- `factionContribution.*` always means only the target nation's contribution.
- `factionContext.observedTotalAtStart` is context-only and never a projected metric.
- Advisor-derived output is marked `hypotheticalPolicy`.

## Validation commands

- py -3 -m unittest discover -s tests -p 'test_*.py'

## Manual smoke tests

- Run current-pips projection and a two-segment plan against an available local save.

## Rollback risks

- Additive command; rollback does not alter existing CLI output.

## Progress

- Completed: save extraction, strict Advisor resolution, owner priority bonuses, faction contribution context, command dispatch and CLI flags are implemented.

## Decision log

- Whole-faction values are calculated once through the existing topbar path and emitted only under `factionContext.observedTotalAtStart`.
- Current advisors from any faction affect the cloned initial nation state, while plan-selected saved advisors must be active members of the selected faction.
- Federation Funding/Boost outside the target nation is frozen at the starting snapshot; target-nation changes are added to that pool for contribution conversion.

## Outcomes / Retrospective

- `nation-projection` accepts the requested days, plan file, checkpoints, faction, details and diagnostics options. Existing `nation-ui` output remains unchanged.
