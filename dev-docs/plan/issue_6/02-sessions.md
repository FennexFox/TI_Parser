# Session lifecycle and evidence preservation

## Goal

Preserve application semantics while safely reusing immutable sessions.

## Scope

Preserve application semantics while safely reusing immutable sessions.

## Non-goals

Remote transport, auth, plugins, new mechanics, raw game-data reads and source-save mutation.

## Affected files

tools/ti_parser_mcp.py; tests/test_mcp_adapter.py

## Implementation steps

Implement two-entry LRU keyed by normalized absolute path and compressed-byte SHA-256. Compare hashes before and after construction; never cache failed or changing inputs. Serialize cache access and analysis. Keep expected input failures structured and unexpected exceptions visible.

## Acceptance criteria

Reuse, eviction, same-metadata changes, construction races and concurrency tests pass. Deferred, incomplete, error and partial projection evidence survive unchanged.

## Validation commands

SDK environment: python -m pytest -q tests/test_mcp_adapter.py tests/test_application_api.py

## Manual smoke tests

Inspect and calculate for the same save; verify equal saveIdentity and explicit consent behavior.

## Rollback risks

Reverting the optional adapter must also remove its packaging requirements and docs; preserve existing CLI/application contracts.

## Progress

In progress.

## Decision log

Use the accepted issue #6 plan. SDK imports stay outside normal CLI paths. Runtime catalog replacement requires restart.

## Outcomes / Retrospective

Pending verification.
