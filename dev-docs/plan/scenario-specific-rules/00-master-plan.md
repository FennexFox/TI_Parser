# Scenario-specific parser rules

## Issue Target And Scope Summary

- Issue target: apply rules and template data for the 2003 and Broken Earth scenarios.
- Title: Scenario-specific parser rules
- Source plan: installed Dark Skies scenario templates, current save files, and the installed game assembly.
- Scope: canonical scenario detection, scenario template overlays, nation investment costs,
  control-point maintenance, public-opinion Influence effects, snapshot/cache metadata, and tests.

## Strategy

- Use `TITimeState.scenarioMetaTemplateName` as the canonical scenario identifier.
- Keep the standard/2003 national-rule defaults and apply a narrow `BrokenEarthScenario`
  override for values changed by the DLC's scenario-specific global config.
- Reconstruct control-point maintenance with the save's fixed campaign-start GDP scale,
  matching `TIGlobalValuesState.PCGDPToRaiseBaseCPMaintenanceCostBy1`, before applying
  the scenario's CP-maintenance modifier.
- Resolve matching DLC `Templates` directories and merge named templates after the base
  `StreamingAssets/Templates` directory, so scenario entries override or extend base entries.
- Preserve scenario identity and all template sources in the snapshot/cache fingerprint.
- Validate with synthetic fixtures and installed standard, 2003, and Broken Earth saves.

## Phase Order

1. [Scenario identity and rule model](01-discovery.md)
2. [Scenario rules and DLC template overlays](02-implementation.md)
3. [Regression and save-file verification](03-verification.md)
4. [Campaign-start GDP CP-maintenance fix](04-cp-maintenance-gdp-scaling.md)

## Phase Dependencies

- Phase 1 has no phase dependency beyond resolved issue context.
- Phase 2 depends on completion and validation of phase 1.
- Phase 3 depends on completion and validation of phase 2.
- Phase 4 corrects the CP-maintenance formula discovered after phase 3 and depends on the
  scenario rule model from phase 2.

## Source Of Truth Decisions

- `00-master-plan.md` is the phased implementation plan source of truth.
- Phase files in this directory define phase-local scope and validation.
- Earlier monolithic plans are input material only unless explicitly retained.

## Global Validation Expectations

- `python -m unittest discover -s tests -v`

## Known Risks And Assumptions

- `TIGlobalConfig.json` contains comments and is not part of the named-template loader; the
  Broken Earth army cost is therefore a documented, explicit rule override.
- The Broken Earth control-point maintenance multiplier is also fixed in its start-time
  template. It is modeled by canonical scenario id so calculations do not depend on a year prefix.
- CP-maintenance GDP scaling comes from the save's
  `fixedPCGDPToRaiseBaseCPMaintenanceCostBy1`. When absent or uninitialized, the parser
  derives it from `globalGDP_CampaignStart * 6.26e-06`, with the historical 1-billion
  divisor retained as the final compatibility fallback.
- Scenario overlay discovery assumes DLC templates live below the game's `DLC_Content` directory.
- Raw values already stored in saves, such as `baseInvestmentPoints_month`, are not recalculated.
