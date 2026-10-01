# Phase 01: Registry and argument contracts

## Goal

- Central immutable descriptors and argument contracts

## Scope

- Issue #5 application boundary, existing CLI compatibility.

## Non-goals

- MCP, UI, history, new formulas and generated catalog values.

## Affected files

- tools/ti_parser_registry.py; tools/ti_parser_capabilities.py; tools/ti_parser_application.py; tools/ti_parser_commands.py; owning-module mocks in CLI/claims tests

## Implementation steps

- Register all commands and classify routing; derive capabilities and compatibility policy from registry; bind arguments against pure handler signatures.

## Acceptance criteria

- Primary routes have callable handlers; inventory equals CLI commands and routing excludes diagnostics.

## Validation commands

- python -m pytest tests/test_parser_cli.py tests/test_nation_claims.py tests/test_beta_analysis.py tests/test_beta_cli.py -q

## Manual smoke tests

- Run capabilities without resolving a save.

## Rollback risks

- Registry handler introspection needs pure application functions from phase 2; extracted functions ship with phase 1 to keep the commit usable.

## Progress

- Completed registry, argument contracts and pure handlers. CLI wrappers now dispatch through the registry.

## Decision log

- Python API only for envelope; raw/types remain inspection routes outside primary recommendations.

## Outcomes / Retrospective

- Targeted CLI/beta/claims checks: 31 passed, 7 subtests passed. Capabilities remain schema 1 with additive routing/argument metadata.

- Execution note: Pure application handlers and CLI wiring moved into phase 1 because executable signature-derived metadata depends on them; no session/envelope implementation is required by this commit.
