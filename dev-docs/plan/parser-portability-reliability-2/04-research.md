# Phase 04: Research runtime migration

## Goal

- Make all research calculations use packaged runtime data and fail closed on referenced missing rows.

## Scope

- Extend research catalog v2 with runtime tech/project fields and migrate research, research-ui, research-plan,
  and project-analysis to the runtime bundle.

## Non-goals

- Do not alter prerequisite semantics or strategic scoring beyond data-source and correctness changes.

## Affected files

- Research builder/catalog, save parser research functions, research and package-only tests.

## Implementation steps

- Preserve graph indexes while adding normalized runtime rows and catalog provenance.
- Resolve active tech/project rows strictly; reject missing org/trait/effect dependencies used in bonuses.
- Keep unavailable optional projects distinct from referenced missing definitions.

## Acceptance criteria

- Active missing rows cannot become cost 0 or disappear from candidate lists; package-only research commands pass.

## Validation commands

- python -m unittest discover -s tests -v

## Manual smoke tests

- Compare installed raw and packaged research breakdown/plan on representative saves.

## Rollback risks

- Research catalog size is acceptable; normalization must avoid copying unrelated template fields.

## Progress

- Complete: research catalog v2 packages strict tech/project runtime rows while retaining the prerequisite graph.

## Decision log

- Disabled project rows remain in the runtime index so a save reference is distinguishable from a missing dependency.

## Outcomes / Retrospective

- Research UI, breakdown, plan, and project analysis load research/effect/trait/org/module/ship data from packaged catalogs.
