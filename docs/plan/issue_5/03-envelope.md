# Phase 03: Machine envelopes and regression verification

## Goal

- Versioned results and completed integration

## Scope

- Issue #5 application boundary, existing CLI compatibility.

## Non-goals

- MCP, UI, history, new formulas and generated catalog values.

## Affected files

- tools/ti_parser_session.py; tools/ti_parser_analysis.py; tests/test_application_api.py; tools/verify_beta_distribution.py; README.md

## Implementation steps

- Add run envelopes; retain context on expected errors; bootstrap consumes common outcomes; document API and verify packaged runtime.

## Acceptance criteria

- Success/deferred/incomplete/error retain identity; programming exceptions propagate; projection payload remains intact.

## Validation commands

- python -m pytest -q
- python tools/verify_fresh_export.py
- python tools/build_beta_distribution.py --output dist/TI_Parser-issue-5.zip
- python tools/verify_beta_distribution.py dist/TI_Parser-issue-5.zip

## Manual smoke tests

- Build committed beta ZIP and run tools/verify_beta_distribution.py outside checkout.

## Rollback risks

- Envelope is Python-only. Save load failures before session construction continue to raise. No generator/catalog changes.

## Progress

- Implemented run(), bootstrap routing, 37 dedicated application contract tests, API documentation and isolated ZIP application smoke checks.

## Decision log

- Python API only for envelope; raw/types remain inspection routes outside primary recommendations.
- Projection results use per-plan statuses and scopes inside plans/comparison; the envelope must inspect these without rewriting the authoritative payload.
- Public run rejects truthy non-boolean compatibility consent and calculator input overrides; legacy calculate retains its runtime override options.

## Outcomes / Retrospective

- Dedicated application tests: 37 passed. Clean committed export: 432 passed, 13 skipped, 75 subtests; package-only unittest gate: 6 passed; all six catalog scenarios loaded. ZIP stdlib isolation/application smoke gate passed and is repeated for the final documented commit.

- Final contract correction: faction_name accepts integer IDs across all primary handlers; real topbar/research-ui API and CLI entity-ID parity is protected by regression tests.
