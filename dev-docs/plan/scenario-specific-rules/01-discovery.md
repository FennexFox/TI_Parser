# Phase 01: Scenario identity and rule model

## Goal

- Establish authoritative scenario identity, changed nation rules, and parser gaps.

## Scope

- Compare base, 2003, and Broken Earth templates.
- Confirm relevant game formulas in the installed assembly.
- Trace parser template loading and nation calculations.

## Non-goals

- Reimplement every nation simulation rule that the parser does not currently calculate.
- Infer scenarios from nation or date prefixes.

## Affected files

- `dev-docs/plan/scenario-specific-rules/*`

## Implementation steps

- Inspect `TITimeState`, scenario metadata, `TIGlobalConfig.json`, and `TIStartTimeTemplate.json`.
- Reproduce current output against real saves.
- Record the minimum rule and template-loading changes that affect parser output.

## Acceptance criteria

- Canonical scenario ids and rule differences are identified from primary local sources.
- Each planned parser change has a concrete incorrect-output reproduction.

## Validation commands

- `python -m unittest discover -s tests -v`

## Manual smoke tests

- `python -m tools.ti_parser_cli --help`

## Rollback risks

- Documentation-only phase; reverting removes the recorded evidence and decisions.

## Progress

- Complete.

## Decision log

- `scenarioMetaTemplateName` is authoritative: `2003Scenario` and `BrokenEarthScenario`.
- 2003 retains the standard army cost (60) and CP-maintenance multiplier (1.0).
- Broken Earth uses army cost 40 and CP-maintenance multiplier 0.7.
- Required investment costs are divided by an active positive `nationalIPMultiplier`.
- Scenario effect/project/tech files must be overlaid; base-only loading loses active data.
- Public-opinion Influence must consume the already-saved `PublicOpinionInfluence` effects.

## Outcomes / Retrospective

- Current Broken Earth output reports army cost 60 instead of 40 and CP usage about
  60.986339 instead of 42.690437.
- Follow-up correction: the earlier CP comparison isolated the scenario multiplier but
  missed `TIGlobalValuesState.PCGDPToRaiseBaseCPMaintenanceCostBy1`. On the current BE
  save, using a fixed 1-billion GDP divisor reports 173.907334; the saved campaign-start
  divisor 323,869,500 reconstructs 342.054941, displayed by the game as 342.
- Current Broken Earth research output resolves active DLC tech/project cost and category as
  zero/unknown because only base templates are loaded.
- 2003 permanent research, CP-maintenance, and Influence effects are likewise absent from the
  base template directory.
