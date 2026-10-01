# Schema regression and distribution verification

## Goal
Verify the completed schema contract in both SDK-free and MCP-enabled distributions.
## Scope
Protocol/regression coverage, archive requirements, docs and graph refresh.
## Non-goals
Fixing pre-existing ordinary Windows CI failures, remote MCP or catalog regeneration.
## Affected files
MCP/distribution tests, package builder, MCP setup docs, phase records and generated graphify outputs.
## Implementation steps
Use real contract-shaped fixtures; validate output failures explicitly; verify extracted archive and SDK-free CLI; record checks and refresh repository graph.
## Acceptance criteria
Targeted and broad local checks pass; cross-platform CI matrix remains intact; unrelated known Windows CI failure is recorded separately.
## Validation commands
python -m pytest -q
python tools/verify_fresh_export.py
python tools/build_beta_distribution.py --ref HEAD --output dist/beta.zip
python tools/verify_beta_distribution.py dist/beta.zip
SDK environment: python -m pytest -q tests/test_mcp_adapter.py tests/test_mcp_distribution.py
## Manual smoke tests
Real extracted-ZIP stdio client; missing-SDK stderr-only startup; graph query for canonical schemas.
## Rollback risks
Archive requirements must track schema helper availability; regenerated graph must match committed sources.
## Progress
Pending phases 4 and 5.
## Decision log
No push or external publication. Existing ordinary Windows matrix failures predate MCP; investigate only new regressions in this change.
## Outcomes / Retrospective
Pending validation.
