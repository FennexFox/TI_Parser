# Guarded projection policy

## Goal

Enable only a proven execution shape after every predecessor gate passes.

## Scope

Application/registry-owned policy identity, scope predicates, dependency approval, profile schemas and preservation of normal result evidence.

## Non-goals

Activate the route based on A/B fixture success or unconditional own-subject classification.

## Affected files

tools/ti_parser_fairplay.py; tools/ti_parser_registry.py; profile tests.

## Implementation steps

Require complete structural trace and authority approval; only then add own-subject classification plus guard policy and approved input-domain tests.

## Acceptance criteria

All approved inputs must have proven source-read, branch, completion and output closure. allow_unverified cannot bypass policy. Otherwise preserve global denial.

## Validation commands

- `python -m pytest tests/test_fairplay.py tests/test_mcp_adapter.py -q`
- `git diff --check`

## Manual smoke tests

Confirm current fair-play lists inspect-save only and denies projection before save loading.

## Rollback risks

Broad input approval can disclose derived hidden state; preserve default behavior.

## Progress

Not activated: broader source closure, current-build mechanics, visibility and
a production input predicate remain unproved. Strict raw-save projection
requires exact xenoforming, which the inspected current-DLL UI does not expose
as a number; this is a mandatory denial, not a safe-default inference.

Registry metadata references `fair-play-projection-v1` separately from the
unchanged visibility-dependent classification. Application/MCP capabilities
identify it as pending and disabled; profile schemas remain application-owned.
No input domain or successful guarded execution is approved. The private
guarded entrypoint delegates to the existing profile admission path; changing
policy metadata alone cannot enable execution.

## Decision log

Do not build an unused alternate calculator or fake successful projection.

## Outcomes / Retrospective

Pre-handler denial and default compatibility tests pass. Approval remains
blocked; fixture parity and `allow_unverified` do not bypass the evidence gate.
Setter regressions establish only local post-setter behavior; canonical A/B
runs do not exercise the setter callbacks, whose full closure is not approved. Exact
xenoforming remains denied for raw-save projection. Any later visible-input
plus explicit-assumption path needs its own policy and evidence; it is not
implemented or approved here.
Current-DLL findings and instrumented execution blockers are reproducible via
`tools/audit_projection_reads.py` with an explicitly supplied assembly. Review
findings expire on source/build changes and cannot serve as approval packets.
Public guard activation and its acceptance scenarios are deferred until these
specific predecessor gates pass; the issue remains open.
