# Reusable machine-facing application API

## Issue Target And Scope Summary

- Issue target: #5
- Title: Reusable machine-facing application API
- Source plan: None
- Scope: Complete issue #5 on distribution; Python envelopes only, no MCP transport or new mechanics.

## Strategy

- Central registry owns capabilities, argument contracts and dispatch. Extract existing calculations without changing values; preserve CLI JSON and exit codes.

## Phase Order

1. [Registry and argument contracts](01-registry.md)
2. [Shared execution and session reuse](02-dispatch.md)
3. [Machine envelopes and regression verification](03-envelope.md)

## Phase Dependencies

- Phase 1 has no phase dependency beyond resolved issue context.
- Phase 2 depends on completion and validation of phase 1.
- Phase 3 depends on completion and validation of phase 2.

## Source Of Truth Decisions

- `00-master-plan.md` is the phased implementation plan source of truth.
- Phase files in this directory define phase-local scope and validation.
- Earlier monolithic plans are input material only unless explicitly retained.

## Global Validation Expectations

- python -m pytest -q

## Known Risks And Assumptions

- Sessions are single-threaded immutable save/runtime snapshots. Keep catalog integrity, fail-closed dependencies and projection authoritative prefixes. Existing CLI handlers and cache behavior must remain compatible.
