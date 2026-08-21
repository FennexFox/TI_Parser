# Phase 08: AI and fleet diagnostics

## Goal

- Diagnose saved AI/fleet production and assignment state without inventing AI intent.

## Scope

- Add `ai-fleet-diagnostics`, fact/derivation/suspicion layers, optional user stale threshold.

## Non-goals

- Do not reproduce the whole AI planner or infer resource blocking from an empty queue alone.

## Affected files

- New AI diagnostics module, CLI wiring, synthetic tests, README.

## Implementation steps

- Link AI factions, fleet goals, assigned/pending fleets, ships, habs, shipyards, queues, resources, and MC.
- Report broken references and evidenced blockers as derived facts.
- Emit suspected staleness only when `--stale-days` is supplied.

## Acceptance criteria

- Valid/broken assignment, queue uncertainty, blocker, and stale-threshold tests pass.

## Validation commands

- python -m unittest discover -s tests -v

## Manual smoke tests

- Inspect installed `AttackWithFleet` and `TransportCouncilorsWithFleet` goal states without modifying the save.

## Rollback risks

- Save schemas vary by game version; unknown fields must remain observable without unsupported conclusions.

## Progress

- Complete: `ai-fleet-diagnostics` connects supported goals, assigned/pending fleets, ships, habs, shipyards, queues, resources, and MC evidence.

## Decision log

- Age is always derived; stale suspicion is emitted only when the caller supplies `--stale-days`.

## Outcomes / Retrospective

- Empty queues retain an unknown cause and do not imply resource shortage.
