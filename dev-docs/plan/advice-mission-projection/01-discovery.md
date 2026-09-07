# Phase 01: Discovery and boundaries

## Goal

- Establish the authoritative Advise lifecycle and the smallest projection boundary.

## Scope

- Audit assignment, movement, success, persistent-effect clearing, repeat cadence, resolution staggering, cost, save fields, and current projection flow.

## Non-goals

- No production behavior changes, generic mission simulator, or faction-income forecast.

## Affected files

- `tools/ti_parser_nation_projection.py`
- `tools/ti_save_parser.py`
- `tools/ti_parser_mechanics.py`
- installed DLL/templates (read-only)

## Implementation steps

1. Decompile the relevant DLL types and inspect Advise/time-event templates.
2. Inspect a local save's `CouncilorMissionUpdate` event and current advising state.
3. Trace segment application into base IP and research calculations.

## Acceptance criteria

- Every behavior is grounded in a DLL symbol or template field.
- Automatic success is distinguished from invalid/unaﬀordable orders.
- The recurring resolution gap is identified as the numeric correction.

## Validation commands

- Read-only DLL/template/save inspection commands recorded in the session.

## Manual smoke tests

- Inspect one local mission event without persisting save-specific values.

## Rollback risks

- None; discovery is documentation-only.

## Progress

- Completed.

## Decision log

- `TIMissionResolution_Automatic` makes actionable Advise success exactly 100%.
- `MoveToTarget` changes location during assignment; there is no distance-derived travel duration.
- `StartofTurnBookkeeping` clears advisors every phase, and repeat orders reapply them after resolution.
- Random order-0 placement is represented by the neutral mean stagger time implied by the audited segment spacing.

## Outcomes / Retrospective

- Current segment handling incorrectly mutates active advisors immediately and keeps them continuously active. Desired orders and active effects must be separate states.
