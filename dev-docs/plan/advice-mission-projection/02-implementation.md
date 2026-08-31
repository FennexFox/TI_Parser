# Phase 02: Implement mission lifecycle modeling

## Goal

- Add package-only, event-timed recurring Advise behavior.

## Scope

- Catalog and registry facts, saved schedule extraction, mission-phase clear/resolution events, desired-policy state, transitions, provenance, and renewal cost.

## Non-goals

- No enemy interference, generic outcomes, faction-resource forecast, or competing-order optimizer.

## Affected files

- `tools/build_runtime_catalogs.py`
- `tools/ti_parser_mechanics.py`
- `tools/ti_parser_nation_projection.py`
- `tools/ti_save_parser.py`
- generated nation catalog/manifest
- focused tests and mechanics documentation

## Implementation steps

1. Generate Advise and mission-phase template facts with source hashes.
2. Add cadence helpers matching `TITimeEvent.GetNextEventTime` and repeat changes.
3. Preserve active advisors while segments update desired repeat orders.
4. Clear at phase start; activate the phase-start policy at expected order-0 resolution.
5. Emit transitions, renewal events, expected provenance, and Influence cost.

## Acceptance criteria

- New advisors have no effect before their resolution event.
- Existing advisors clear and renew through the same recurring schedule.
- Multiple cycles accumulate downtime and cost.
- Output states automatic success and immediate assignment movement.

## Validation commands

- Focused tests listed in the master plan.

## Manual smoke tests

- Run a real-save projection spanning at least two mission phases.

## Rollback risks

- Event ordering near the 10:30 investment tick can change daily allocation.
- Generated catalog and manifest must remain atomic.

## Progress

- Not started.

## Decision log

- Template facts are generated data; cadence and mean-stagger algorithms are Python mechanics.

## Outcomes / Retrospective

- Not completed yet.
