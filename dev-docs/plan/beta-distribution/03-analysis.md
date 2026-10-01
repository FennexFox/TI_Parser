# Phase 03: Create bounded LLM bootstrap context and reusable machine-facing session.

## Goal

- Create bounded LLM bootstrap context and reusable machine-facing session.

## Scope

- Analysis orchestration, CLI, new analysis tests, skill and user guides.

## Non-goals

- No formula or projection structure changes; no comprehensive nation/hab/fleet/org/history report, persistent history, previous-save diff, alerts, UI, browser/Pyodide, companion integration, FastAPI or MCP server.

## Affected files

- Analysis orchestration, CLI, new analysis tests, skill and user guides.

## Implementation steps

- Introduce a thin AnalysisSession with one save/index and scoped catalog reuse. inspect-save/analyze share stable saveIdentity. analyze contains campaign/player, compatibility, core resource/research/CP-capacity context, section evidence/failures and availableAnalyses. capabilities returns a versioned inventory of specialized commands, purpose, observed-state/planning-evidence/simulation kind and compatibility requirements without requiring a save. CLI uses the session for new entrypoints; legacy calculate_* functions remain source of truth. Add safe report output and skill routing.

## Acceptance criteria

- No repeated save/index load or invented formulas; partial results explicit; no absolute path/cache leakage; identical save bytes yield identical identity across paths; capabilities inventory matches implemented command policy.

## Validation commands

- python -m pytest tests/test_beta_analysis.py -q

## Manual smoke tests

- Analyze synthetic save before/after opt-in; inspect JSON output.

## Rollback risks

- Keep existing export intact; new report schema versioned.

## Progress

- Planning complete; implementation in progress.

## Decision log

- User refinement: analyze is LLM bootstrap context and machine boundaries are reusable. Preserve original five-phase plan.

## Outcomes / Retrospective

- Pending implementation and verification; no completion claimed.

