# Mock Companion and real TI Parser integration

## Goal

Validate local orchestration and generation sequencing with two actual stdio servers.

## Scope

Test-only current-state, history and bound identity fixture server; canonical prompts; automatic protocol tests; separate real Codex routing runs.

## Non-goals

Treat the mock as visibility oracle or automated chosen calls as LLM routing success.

## Affected files

tests/support/mock_companion_mcp.py; tests/test_fairplay_interoperability.py; application generation helper.

## Implementation steps

Read bound peer context, TI inspection, projection result, TI reinspection and bound peer reobservation. Reject mismatch/missing observations and dispose the advice batch; test current blocked behavior.

## Acceptance criteria

Exact/provisional/rejected are explicit. A blocked projection or missing bound nation ID cannot produce an accepted prediction. Routing/correlation/policy/mechanics failures are separately recorded.

## Validation commands

- `python -m pytest tests/test_fairplay.py tests/test_fairplay_interoperability.py -q`
- `git diff --check`

## Manual smoke tests

Connect both servers through the MCP client and run canonical prompts through Codex with temporary per-run configuration.

## Rollback risks

Weak identities can collide; reobservation is not exact proof. Synthetic fixtures must never be presented as real campaign advice.

## Progress

Implemented the synthetic response-bound Companion server and two real stdio
client probes. Added the application generation helper with independent
save-generation and discard-on-mismatch tests. Save-only inspections no longer
need invented nation fields. A private application operation issues an opaque,
process-local receipt after strict player/CP ownership resolution and actual
projection execution. It seals the exact envelope, resolved country and save
identity; guessed IDs, copied or altered results cannot attest the subject.
Real AnalysisSession contract tests cover exact/provisional correlation and
save replacement. This is a correlation primitive, not a new MCP tool or
fair-play approval; the public guarded projection remains disabled.

Real Codex CLI runs used isolated per-run configuration and six canonical
prompts against the pre-refresh baseline. Those retained observations are
protocol/routing evidence only and do not certify current-build mechanics or
visibility. Initial approval/routing failures were separated from calculation
failures; application-owned descriptions/instructions corrected unnecessary
TI calls. Retained call and answer-review evidence is in
[routing-evidence.json](routing-evidence.json).

## Decision log

The mock and audit helpers remain excluded from the runtime ZIP.

## Outcomes / Retrospective

Local mock protocol and blocked-behavior routing checks pass. This does not
prove game visibility, complete generation-safe prediction, or actual Companion
acceptance. The successful prediction case remains blocked by earlier gates.
