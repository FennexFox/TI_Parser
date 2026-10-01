# Optional distribution and verification

## Goal

Ship optional MCP support without adding dependencies to the base parser.

## Scope

Ship optional MCP support without adding dependencies to the base parser.

## Non-goals

Remote transport, auth, plugins, new mechanics, raw game-data reads and source-save mutation.

## Affected files

README.md; docs/MCP_SETUP.md; requirements-mcp.txt; beta builder/tests; beta-validation workflow

## Implementation steps

Extend distribution allowlist and required paths. Document installation and absolute-path host configuration. Add separate SDK-enabled Windows/Linux Python 3.11-3.14 CI, in-process and extracted-ZIP stdio coverage; preserve isolated SDK-free verification.

## Acceptance criteria

SDK-free full suite, clean-export checks and ZIP verification pass. SDK-enabled protocol and extracted ZIP tests pass. CLI never imports optional dependencies.

## Validation commands

python -m pytest -q; python tools/verify_fresh_export.py; python tools/build_beta_distribution.py --ref HEAD --output dist/beta.zip; python tools/verify_beta_distribution.py dist/beta.zip; SDK environment: python -m pytest -q tests/test_mcp_adapter.py tests/test_mcp_distribution.py

## Manual smoke tests

Launch extracted ZIP from another working directory using a save path containing spaces and Korean characters. Verify protocol-only stdout.

## Rollback risks

Reverting the optional adapter must also remove its packaging requirements and docs; preserve existing CLI/application contracts.

## Progress

Complete.

## Decision log

Use the accepted issue #6 plan. SDK imports stay outside normal CLI paths. Runtime catalog replacement requires restart.

## Outcomes / Retrospective

SDK-free full suite: 433 passed, 16 skipped, 75 subtests passed. SDK-enabled adapter and extracted-ZIP tests: 15 passed. Fresh Git export full suite and package-only guards passed. Committed beta ZIP build and isolated -I -S verification passed. Local verification used Windows/Python 3.14; Windows/Linux Python 3.11-3.14 coverage is configured in CI, not claimed as locally executed.
