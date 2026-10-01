# Registry-derived MCP tools

## Goal

Generate typed bootstrap and primary tools plus capabilities using the optional SDK low-level server.

## Scope

Generate typed bootstrap and primary tools plus capabilities using the optional SDK low-level server.

## Non-goals

Remote transport, auth, plugins, new mechanics, raw game-data reads and source-save mutation.

## Affected files

tools/ti_parser_mcp.py; tests/test_mcp_adapter.py

## Implementation steps

Build schemas from registry argument contracts and handler annotations. Preserve required/default/union/list/enum behavior. Add explicit save_path and eligible per-call consent. Advertise no advanced or diagnostic routes.

## Acceptance criteria

In-process SDK client initializes, lists the exact registry-derived inventory, and validates representative schemas. Structured and text results preserve the application envelope.

## Validation commands

SDK environment: python -m pytest -q tests/test_mcp_adapter.py

## Manual smoke tests

Initialize and list tools using an in-process client. Start without SDK and check stderr-only installation guidance.

## Rollback risks

Reverting the optional adapter must also remove its packaging requirements and docs; preserve existing CLI/application contracts.

## Progress

In progress.

## Decision log

Use the accepted issue #6 plan. SDK imports stay outside normal CLI paths. Runtime catalog replacement requires restart.

## Outcomes / Retrospective

Pending verification.
