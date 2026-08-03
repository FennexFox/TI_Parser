# Phase 02: Scenario rules and DLC template overlays

## Goal

- Make parser calculations and template lookup scenario-aware without changing standard campaigns.

## Scope

- Scenario identity helpers and DLC template-source resolution.
- Base-plus-overlay named-template merging and cache fingerprinting.
- Broken Earth army cost and CP-maintenance multiplier.
- Campaign customization scaling and public-opinion Influence effects.

## Non-goals

- Recompute save-owned values such as base national investment-point production.
- Model global rules not consumed by an existing parser output.

## Affected files

- `tools/ti_parser_core.py`
- `tools/ti_parser_cli.py`
- `tools/ti_parser_snapshot.py`
- `tools/ti_save_parser.py`
- focused unit tests

## Implementation steps

- Add canonical scenario and template-source helpers.
- Merge named templates in base-to-scenario order.
- Add an immutable scenario-rule profile and apply it to nation calculations.
- Apply the active national IP multiplier and Influence effect context.
- Expose scenario/template provenance in parser output and cache identity.

## Acceptance criteria

- Standard and 2003 army costs remain 60; Broken Earth is 40.
- Custom national IP multiplier scales all priority costs exactly once.
- Broken Earth CP usage is multiplied by 0.7 before cap/overage calculations.
- Scenario-only tech/project/effect templates resolve from the active DLC overlay.
- 2003/BE public-opinion Influence modifiers affect nation income.

## Validation commands

- `python -m unittest discover -s tests -v`

## Manual smoke tests

- `python -m tools.ti_parser_cli --help`

## Rollback risks

- Reverting only part of the template-source changes can desynchronize cache identity from reads.

## Progress

- Not started.

## Decision log

- No decisions recorded yet.

## Outcomes / Retrospective

- Not completed yet.
