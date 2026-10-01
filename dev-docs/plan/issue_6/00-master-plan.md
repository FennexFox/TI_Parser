# Optional local stdio MCP adapter

## Issue Target And Scope Summary

- Issue target: #6
- Title: Optional local stdio MCP adapter
- Source plan: None
- Scope: Optional local stdio MCP tools over the existing machine application API; no remote transport, game mechanics changes, or catalog regeneration.

## Strategy

- Generate typed tools from the canonical registry input schema; preserve application envelopes and declare application-owned output schemas.
- Reuse at most two sessions, checking compressed-save SHA-256 on every call and serializing session use.
- Package the optional entrypoint, dependency metadata and setup documentation while keeping SDK-free CLI validation separate.

## Phase Order

1. [Registry-derived MCP tools](01-adapter.md)
2. [Session lifecycle and evidence preservation](02-sessions.md)
3. [Optional distribution and verification](03-distribution.md)
4. [Canonical input contract](04-input-contract.md)
5. [Machine output contract](05-output-contract.md)
6. [Schema regression and distribution verification](06-schema-verification.md)

## Phase Dependencies

- Phase 1 has no phase dependency beyond resolved issue context.
- Phase 2 depends on completion and validation of phase 1.
- Phase 3 depends on completion and validation of phase 2.
- Phases 4 and 5 extend the delivered adapter following the 2026-10-01 issue scope update; phase 6 verifies both.

## Source Of Truth Decisions

- `00-master-plan.md` is the phased implementation plan source of truth.
- Phase files in this directory define phase-local scope and validation.
- Earlier monolithic plans are input material only unless explicitly retained.

## Global Validation Expectations

- SDK-free: `python -m pytest -q`, `python tools/verify_fresh_export.py`, beta ZIP build and verification.
- SDK-enabled: adapter and extracted-ZIP stdio tests with `mcp==2.2.0` in a separate environment.

## Known Risks And Assumptions

- SDK 2.2.0 is optional and pinned; parser runtime remains stdlib-only.
- Save identity in application results remains authoritative; cache hashes are compressed-byte invalidation keys only.
- Runtime-data replacement requires restarting the server.
- Plans are implemented as reviewable commits; no push, publication, or installed host configuration is requested.

## Final Verification

The following records describe the original delivery. Issue #6 now additionally requires phases 4–6: canonical registry/application input-schema ownership (including choices) and declared MCP output schemas. See [scope update](https://github.com/FennexFox/TI_Parser/issues/6#issuecomment-5942071813).

- Adapter and session phases completed in commit `373e414`; optional packaging and CI in `f2e38bf`.
- SDK-free checkout and fresh-export suites: 433 passed, 16 skipped, 75 subtests passed.
- SDK-enabled protocol, subprocess boundary and extracted ZIP tests: 15 passed.
- Beta archive verification passed using `-I -S`, outside the checkout, with game-input/network guards.
- Unrelated external AGENTS.md changes were preserved and not staged.
- No push, host configuration change, or external publication was performed.
