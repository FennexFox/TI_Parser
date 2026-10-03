# Real Companion and Codex acceptance

## Goal

Close the issue only with an approved projection and actual Companion end-to-end evidence.

## Scope

Replace the mock with a testable actual Companion server; rerun the same canonical cases and generation sequence.

## Non-goals

Require a public release or close the issue based on the mock.

## Affected files

docs/MCP_SETUP.md; maintained interoperability acceptance matrix.

## Implementation steps

Use a pinned save and both real servers; record tool choices, result identities, observed versus simulated evidence and unsupported conclusions.

## Acceptance criteria

Approved guarded projection, matching intended generation, correct routing and separated evidence must all succeed.

## Validation commands

- `python -m pytest tests/test_mcp_distribution.py -q`
- `git diff --check`

## Manual smoke tests

Run the actual two-server Codex scenario after the real Companion becomes available.

## Rollback risks

Do not reuse old context with a new projection or replace blocked fair-play with default tools.

## Progress

Pending actual Companion and approved projection.

## Decision log

A local server or branch is sufficient; no public release requirement.

## Outcomes / Retrospective

Acceptance is pending the evidence and checks above; implementation completion
is not release acceptance. Exact xenoforming is not exposed as an exact value by
the inspected current-DLL UI, so strict raw-save projection remains denied.
Canonical A/B runs do not exercise the setter callbacks, whose full closure
remains unapproved. A future visible-input
plus explicit-assumption extension is a distinct, unimplemented policy path and
does not satisfy or bypass these acceptance gates.
