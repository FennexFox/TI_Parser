# Phase 03: Effects traits and org catalogs

## Goal

- Package effect, trait, and org calculation data and migrate shared runtime consumers.

## Scope

- Deterministic builders, base/scenario overrides, snapshot/councilor/income/org/topbar/hab/nation/world/advise migration.

## Non-goals

- Do not reconstruct unverified trait conditions or market-generation rules.

## Affected files

- Runtime catalog builder/data, snapshot/income/org/save parser modules, generator and domain tests.

## Implementation steps

- Normalize only fields read by current calculators; preserve source hashes and override provenance.
- Require definitions only when a save/reference makes them calculation-relevant.
- Replace raw loader arguments with injected packaged mappings.

## Acceptance criteria

- Package-only org, snapshot, topbar, and hab calculations match their raw-reference equivalents.

## Validation commands

- python -m unittest discover -s tests -v

## Manual smoke tests

- Run a Broken Earth save through topbar and org-plan with the install path hidden.

## Rollback risks

- Tightening low-level helpers may expose old synthetic fixtures; update fixtures rather than restore silent defaults.

## Progress

- Not started.

## Decision log

- No decisions recorded yet.

## Outcomes / Retrospective

- Not completed yet.
