# Canonical input contract

## Goal
Make the registry the sole caller-visible analysis input-schema owner.
## Scope
Fresh get_input_schema() results for all callable analyses; handler-derived shapes, existing choices, special projection inputs; MCP adds only transport fields.
## Non-goals
New domain rules, blanket runtime JSON Schema validation, CLI argument changes.
## Affected files
Registry, shared config/CLI exports, MCP adapter and input-schema tests.
## Implementation steps
Reuse public parameter discovery; centralize choices and research mode constants; preserve unions/defaults and exclude private overrides; replace MCP introspection with canonical schemas.
## Acceptance criteria
All callable schemas describe the public contract; choices and schema changes propagate to MCP; fresh return values cannot mutate later results.
## Validation commands
python -m pytest -q tests/test_input_schema.py tests/test_application_api.py
SDK environment: python -m pytest -q tests/test_mcp_adapter.py
## Manual smoke tests
List tools through the SDK client and inspect projection, planning and forecast schemas.
## Rollback risks
Revert registry and adapter changes together; retain original runtime semantics and bootstrap routes.
## Progress
Implementation started.
## Decision log
Use existing choice constants; JSON Schema describes canonical public inputs without replacing domain validation/normalization.
## Outcomes / Retrospective
Pending validation.
