# Phase 02: Inspect saved facts without calculations and gate unverified calculations.

## Goal

- Inspect saved facts without calculations and gate unverified calculations.

## Scope

- Compatibility module/registry, CLI integration and compatibility tests.

## Non-goals

- No game formula changes, catalog regeneration, projection restructuring or external publication.

## Affected files

- Compatibility module/registry, CLI integration and compatibility tests.

## Implementation steps

- Extract raw metadata; match exact evidence-backed compatibility records; classify commands; add per-invocation allow option and result metadata.

## Acceptance criteria

- Unknown version/mod state gates every calculation; raw inspect works without catalog calculation; strict dependencies survive opt-in.

## Validation commands

- python -m pytest tests/test_beta_compatibility.py tests/test_beta_cli.py -q

## Manual smoke tests

- Inspect synthetic save; blocked calculation then explicit allow.

## Rollback risks

- Registry must never imply verification from version names alone.

## Progress

- Planning complete; implementation in progress.

## Decision log

- Use user-approved beta contract; root integrates independent worker changes.

## Outcomes / Retrospective

- Pending implementation and verification; no completion claimed.

