# Phase 03: Machine envelopes and regression verification

## Goal

- Versioned results and completed integration

## Scope

- Issue #5 application boundary, existing CLI compatibility.

## Non-goals

- MCP, UI, history, new formulas and generated catalog values.

## Affected files

- tools/ti_parser_session.py; tools/ti_parser_analysis.py; tests/test_application_api.py; README.md

## Implementation steps

- Add run envelopes; retain context on expected errors; bootstrap consumes common outcomes; document API and verify packaged runtime.

## Acceptance criteria

- Success/deferred/incomplete/error retain identity; programming exceptions propagate; projection payload remains intact.

## Validation commands

- python -m pytest -q

## Manual smoke tests

- Build committed beta ZIP and run tools/verify_beta_distribution.py outside checkout.

## Rollback risks

- Envelope is Python-only. Save load failures before session construction continue to raise. No generator/catalog changes.

## Progress

- Not started.

## Decision log

- Python API only for envelope; raw/types remain inspection routes outside primary recommendations.

## Outcomes / Retrospective

- Not completed yet.
