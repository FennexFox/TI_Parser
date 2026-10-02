# Phase 03: External interoperability validation

## Goal

- Complete acceptance using runtime checks and the actual companion MCP/Codex two-server integration, preserving the unresolved gates until evidence exists.

## Scope

- Run the 180-day A/B prompt against the same pinned save and record exact identity comparison and route outcomes.
- Verify all registry entries are denied in fair-play except `inspect-save` and `capabilities`, and denial precedes handler execution.
- Exercise exact and provisional match acceptance/rejection conditions.
- Complete authoritative visibility tracing before reconsidering projection access.

## Non-goals

- Substitute local unit or schema checks for the unavailable companion integration evidence.
- Treat a passing default projection as proof of fair-play safety.

## Affected files

- Profile implementation, tests, companion MCP, Codex server configuration, pinned save fixture, visibility audit evidence.

## Implementation steps

- Run the implementation's focused test suite and the 180-day prompt in both configured servers.
- Preserve logs without exposing sensitive save contents.
- Close only the gates supported by recorded evidence.

## Acceptance criteria

- Local implementation gates have test evidence, or are explicitly reported as pending; external Companion/Codex acceptance remains separately open.
- Default behavior remains unchanged when profile is omitted or set to `default`.
- Fair-play blocks all unapproved routes before handler execution.
- Companion and Codex-side server produce the expected same-save comparison outcomes.

## Validation commands

- python C:\\Users\\techn\\.codex\\skills\\phased-issue-implementation\\scripts\\phase_plan_helper.py validate --plan-dir dev-docs/plan/issue_8
- git diff --check

## Manual smoke tests

- Not run. Neither the actual companion MCP nor a configured Codex two-server session is available in this repository task.

## Rollback risks

- Rollback external test artifacts only; preserve profile implementation and its local regression tests. Keep unresolved gates explicit if product access remains unavailable.

## Progress

- Pending external integration and implementation evidence. Do not mark Issue #8 release acceptance complete.

## Decision log

- The expected fair-play outcome for the 180-day request is refusal to execute `nation-projection`; fair-play capabilities lists only `inspect-save`.
- Source-level and local test results cannot close the actual two-server acceptance gate.

## Outcomes / Retrospective

- No acceptance claim made. Continue when both integrations and a pinned test save are available.
