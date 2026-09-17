# Phase 03: Cross-platform acceptance

## Goal

- Complete reviewable acceptance and documentation.

## Scope

- Full tests, fresh-export gate, phase documentation and final diff review.

## Non-goals

- New features and unrelated formatting.

## Affected files

- Phase documentation and validation follow-ups only.

## Implementation steps

- Run full pytest; inspect diff; commit implementation; run fresh-export gate against commits; record exact outcomes.

## Acceptance criteria

- Full and package-only tests pass; supported scenarios load from committed bytes; worktree is clean.

## Validation commands

- python -B -m pytest -q -p no:cacheprovider

## Manual smoke tests

- Run CLI help and archive acceptance; inspect git status.

## Rollback risks

- Public compatibility must remain; revert the phase commit rather than weakening checks.

## Progress

- Complete. Full checkout, committed-export and real-save integration verification passed.

## Decision log

- Acceptance targets implementation commit b3691f7. Documentation-only completion follows the gate.
- AST comparison verified all 23 extracted ship function bodies match the previous facade after the constant-reference substitution.

## Outcomes / Retrospective

- `python -B -m pytest -q -p no:cacheprovider`: 325 passed, 13 skipped, 45 subtests passed.
- `python -B tools/verify_fresh_export.py`: complete; 338 unittest cases with 14 skipped, package-only suite 6 passed, all 6 supported scenarios loaded.
- `phase_plan_helper.py validate --plan-dir dev-docs/plan/reliability_refactor`: OK (3 phases).
- `git diff --check`: passed.
- Cross-platform scope: validated LF-preserving export on Windows, not native execution on another operating system.

- Real-save integration: set `TI_PARSER_REAL_SAVE` to `find_latest_save()` and ran `pytest -q -p no:cacheprovider tests/test_nation_projection_real_save.py`: 12 passed, 16 subtests passed in 133.50 seconds.
