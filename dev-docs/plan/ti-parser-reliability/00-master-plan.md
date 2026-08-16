# TI Parser reliability and provenance

## Issue Target And Scope Summary

- Issue target: TI Parser 신뢰성 보완
- Title: TI Parser reliability and provenance
- Source plan: None
- Scope: Human-player resolution, packaged module-catalog runtime loading, CP-cap provenance,
  shared hab state interpretation, mining diagnostics, completion-event forecasts, location-aware
  solar-power validation, packaged natural-location catalog runtime loading, and fail-closed tests.

## Strategy

- Resolve the player only from `TIPlayerState.isAI == false`, cross-checked with metadata.
- Rehydrate `data/module_catalog.json` into the existing template-shaped calculation API.
- Centralize lifecycle interpretation in `get_effective_module_state()` while preserving game-code
  distinctions between target crew upkeep, active production/power, and prior-module MC.
- Keep CP effect values template-driven and expose a summing breakdown plus effect provenance.
- Simulate future hab resource balances at each saved completion date and surface power uncertainty.
- Reject nominal solar output when required body/orbit template context cannot be resolved.
- Generate normalized body/orbit data into `data/location_catalog.json` and make it the only runtime
  source for location-dependent calculations.
- Include `TINavigableTemplate` Lagrange points in the same atomic catalog so all saved hab barycenters resolve.
- Verify synthetic cases and the installed `ExitSave(3).gz` fixture.

## Phase Order

1. [Player identity and packaged module catalog](01-identity-catalog.md)
2. [Unified hab module effective-state calculations](02-effective-state.md)
3. [CP capacity and event-based resource forecast](03-cp-forecast.md)
4. [Diagnostics and ExitSave regression verification](04-verification.md)
5. [Fail-closed location-aware solar power](05-solar-power-fail-closed.md)
6. [Packaged body and orbit location catalog](06-packaged-location-catalog.md)
7. [Lagrange point catalog coverage](07-lagrange-location-coverage.md)

## Phase Dependencies

- Phase 1 has no phase dependency beyond resolved issue context.
- Phase 2 depends on completion and validation of phase 1.
- Phase 3 depends on completion and validation of phase 2.
- Phase 4 depends on completion and validation of phase 3.
- Phase 5 is a reliability follow-up and depends on the effective-state and forecast work from phases 2-4.
- Phase 6 depends on phase 5's strict location-data contract and replaces its installed-template runtime dependency.
- Phase 7 corrects the natural-location coverage gap discovered after phase 6 and depends on its schema and loader.

## Source Of Truth Decisions

- `00-master-plan.md` is the phased implementation plan source of truth.
- Phase files in this directory define phase-local scope and validation.
- Earlier monolithic plans are input material only unless explicitly retained.

## Global Validation Expectations

- python -m unittest discover -s tests -v

## Known Risks And Assumptions

- Installed raw effect templates remain necessary for dynamic effects. Raw body/orbit templates are generator
  inputs only; the packaged location catalog is mandatory at runtime and missing location data fails closed.
- Raw `TINavigableTemplate` data is also generator-only input; its Lagrange rows must not be confused with
  physical space bodies when radius, mass, atmosphere, or irradiation fields are interpreted.
- Decompiled installed game code confirms construction crew uses the target template, while direct
  support/production/power require active completion. `priorModuleCompleted` remains relevant to MC.
- Forecast power management priority cannot be reconstructed exactly from a static save, so negative
  projected power marks a row and overall forecast incomplete.
