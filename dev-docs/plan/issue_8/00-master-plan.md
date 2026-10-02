# Fair-play profile and interoperability audit

## Issue Target And Scope Summary

- Issue target: #8
- Title: Fair-play profile and interoperability audit
- Source plan: None
- Scope: Implement the fair-play route policy and save-context comparison, audit visibility limits, document the integration contract, and retain external acceptance evidence as an explicit gate.

## Strategy

- Preserve default behavior when the profile is omitted. The initial fair-play allowlist is only `inspect-save` plus a filtered `capabilities` inventory; globally block `nation-projection` pending an authoritative visibility audit; exclude all other analyses. Implement exact save identity comparison and pinned-only provisional matching. Keep the Companion MCP plus Codex-side two-server test as an unresolved acceptance gate.

## Phase Order

1. [Policy and API boundary](01-discovery.md)
2. [Contract and routing guidance](02-documentation.md)
3. [External interoperability validation](03-acceptance.md)

## Phase Dependencies

- Phase 1 has no phase dependency beyond resolved issue context.
- Phase 2 depends on completion and validation of phase 1.
- Phase 3 depends on completion and validation of phase 2.

## Current Phase Status

| Phase | Status | Note |
| --- | --- | --- |
| 1. Policy and API boundary | Complete | Profile and comparison implementation committed as `6be8b83`; coordinator reports 60 focused tests passed. Full suite and ZIP verification are being completed separately. |
| 2. Contract and routing guidance | Complete | Runtime user guide, API note, and developer audit/index updated. |
| 3. External interoperability validation | Pending | Actual Companion MCP and Codex-side two-server session remain unavailable; acceptance remains open. |

## Source Of Truth Decisions

- `00-master-plan.md` is the phased implementation plan source of truth.
- Phase files in this directory define phase-local scope and validation.
- Earlier monolithic plans are input material only unless explicitly retained.
- The public `--profile default|fair-play` contract and visibility limits are recorded in [the interoperability audit](../../fairplay_interoperability.md). Runtime profile implementation is in commit `6be8b83`; the Companion MCP/Codex two-server run remains an external acceptance gate.

## Global Validation Expectations

- python C:\\Users\\techn\\.codex\\skills\\phased-issue-implementation\\scripts\\phase_plan_helper.py validate --plan-dir dev-docs/plan/issue_8
- git diff --check

## Known Risks And Assumptions

- `nation-projection` visibility is not established by output schemas or redaction. Actual companion MCP and Codex-side server are unavailable in this checkout; retain acceptance as pending.
