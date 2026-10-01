# Phase 03: Create basic shareable report and question-driven assistant workflow.

## Goal

- Create basic shareable report and question-driven assistant workflow.

## Scope

- Analysis orchestration, CLI, new analysis tests, skill and user guides.

## Non-goals

- No game formula changes, catalog regeneration, projection restructuring or external publication.

## Affected files

- Analysis orchestration, CLI, new analysis tests, skill and user guides.

## Implementation steps

- Reuse one loaded index; facts plus independent topbar/research sections; section evidence/failures; safe output; skill routing and consent.

## Acceptance criteria

- No repeat load or invented formulas; partial results explicit; no absolute path/cache leakage.

## Validation commands

- python -m pytest tests/test_beta_analysis.py -q

## Manual smoke tests

- Analyze synthetic save before/after opt-in; inspect JSON output.

## Rollback risks

- Keep existing export intact; new report schema versioned.

## Progress

- Planning complete; implementation in progress.

## Decision log

- Use user-approved beta contract; root integrates independent worker changes.

## Outcomes / Retrospective

- Pending implementation and verification; no completion claimed.

