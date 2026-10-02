# Phase 01: Policy and API boundary

## Goal

- Define and implement the fair-play routing contract from registry evidence, and identify visibility risks that block projection.

## Scope

- Review registry metadata, public API/MCP behavior, existing save identity, and projection extraction/mechanics evidence.
- Implement the default-preserving profile policy, initial allowlist, global projection block, exact fingerprint comparison, and conservative pinned-only provisional matching.

## Non-goals

- Expand the fair-play route allowlist without new authoritative visibility evidence.
- Treat read-only appearance or output redaction as proof of visibility safety.

## Affected files

- Profile policy/helper implementation, MCP/API route integration, focused tests, projection adapter and existing mechanics audit.

## Implementation steps

- Inventory all registry routing categories and route IDs.
- Trace target, faction, region, public-opinion, market, and output reads; keep parser evidence distinct from game visibility evidence and scenario assumptions.
- Compare exact schema-1 supported fingerprints and required context; permit provisional comparison only for pinned saves when the fingerprint algorithm is unknown and every context field is known and equal.
- Run focused profile and comparison tests; coordinator records command results after implementation integration.

## Acceptance criteria

- The profile policy admits only `inspect-save`; `capabilities` lists only `inspect-save` in fair-play.
- `nation-projection` is blocked for every fair-play caller pending authoritative visibility evidence.
- Missing, unresolved, or changed provisional match fields reject matching; fingerprint mismatch never falls back.

## Validation commands

- python C:\\Users\\techn\\.codex\\skills\\phased-issue-implementation\\scripts\\phase_plan_helper.py validate --plan-dir dev-docs/plan/issue_8
- git diff --check

## Manual smoke tests

- Real stdio startup and inspection passed for both profiles, including the ZIP built from committed bytes. These protocol checks do not establish real-client tool selection; the external Companion/Codex session is phase 3.

## Rollback risks

- Rollback is limited to the new profile/helper boundary; preserve default behavior and its existing response contract.

## Progress

- Complete. Runtime profile/comparison implementation committed as `6be8b83`. `python -m pytest tests/test_fairplay.py tests/test_mcp_adapter.py -q` passed (60 tests). `python -m pytest -q` passed (521 tests, 13 skipped, 75 subtests), including committed ZIP/default/fair-play stdio verification.

## Decision log

- `default` remains the default and preserves existing route behavior.
- Fair-play analysis allowlist is only `inspect-save`; filtered capabilities metadata lists only that route. All other routes are excluded, with projection globally blocked.
- Exact comparison requires schema 1, supported matching fingerprint, and equal campaign/date/player/selected-nation context. Unknown algorithms may use pinned-only provisional comparison; invalid supported digests or any missing, changed, or unequal context reject.

## Outcomes / Retrospective

- Source inventory and policy boundary are documented. Focused implementation tests and the external integration gate are separate evidence items.
