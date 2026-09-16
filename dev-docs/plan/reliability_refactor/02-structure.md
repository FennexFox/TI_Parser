# Phase 02: Catalog and domain consistency

## Goal

- Reduce repeated work and consolidate domain boundaries without changing public results.

## Scope

- Packaged module/location integrity and duplicate rejection; command-local catalog reuse; cohesive implementation extraction; evidence-backed adviser selection.

## Non-goals

- Wholesale rewrite, guessed game mechanics, new CLI output shapes.

## Affected files

- Catalog loaders/generators, a new domain module, public facade wrappers, relevant tests and README.

## Implementation steps

- Inspect evidence and choose narrow boundaries; update generators and regenerate owned data; preserve wrappers; reuse validated catalog objects; verify parity and package-only behavior.

## Acceptance criteria

- All runtime catalog domains receive integrity protection; repeated loads are bounded per command; extracted domain preserves signatures/results; adviser policy follows authoritative evidence.

## Validation commands

- python -B -m pytest -q -p no:cacheprovider

## Manual smoke tests

- Compare public wrappers and extracted module results; verify altered catalog bytes are rejected.

## Rollback risks

- Public compatibility must remain; revert the phase commit rather than weakening checks.

## Progress

- Not started.

## Decision log

- No decisions recorded yet.

## Outcomes / Retrospective

- Not completed yet.
