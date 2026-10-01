# Machine output contract

## Goal
Declare SDK-independent schemas for existing machine results.
## Scope
Analysis envelopes, identity, compatibility, pre-session errors and capabilities output; MCP outputSchema registration.
## Non-goals
Reshaping results, typing each domain result, new runtime dependencies.
## Affected files
Application-owned schema helper, MCP adapter and output/protocol tests.
## Implementation steps
Provide fresh schemas; distinguish full envelopes from small errors; preserve fallback compatibility fields; register common analysis and separate capabilities schemas.
## Acceptance criteria
Real complete/deferred/incomplete/error outcomes validate; error results are checked explicitly; text and structured payloads stay equal.
## Validation commands
python -m pytest -q tests/test_output_schema.py
SDK environment: python -m pytest -q tests/test_mcp_adapter.py tests/test_mcp_distribution.py
## Manual smoke tests
Initialize/list/call with an SDK client, including a missing save and save-free capabilities.
## Rollback risks
Remove schema declarations with their helper; do not alter application envelope bytes or status policy.
## Progress
Implementation started.
## Decision log
Output schemas permit arbitrary domain JSON and existing evidence extensions; no fabricated saveIdentity on pre-session errors.
## Outcomes / Retrospective
Pending validation.
