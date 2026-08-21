# Runtime dependency and silent-fallback audit

## Normal-runtime raw sources

- CLI startup resolves a Steam install and DLC template overlay before every non-`raw` command.
- Snapshot uses raw traits; org-plan uses raw traits and orgs; hab/topbar/nation/world/advise use raw traits/effects.
- Research uses raw traits, effects, orgs, utilities, techs, and projects despite the packaged research graph.
- Ship planning/simulation/upkeep uses raw hull, drive, plant, radiator, armor, battery, heat-sink, utility,
  weapon, and effect templates.

`tests/test_runtime_raw_loader_guard.py` records these exact AST edges. It permits removal but fails if a new edge
is introduced. The final phase must reduce the audited runtime counter to zero; builders and explicit verification
tools are outside the runtime module set.

## Silent correctness degradation

- `load_named_templates()` returns an empty mapping for missing or malformed sources.
- `apply_effect_modifiers()` skipped missing effects and treated malformed values/operations as no modifier.
- Missing snapshot traits, councilor-income org/trait references, and research tech/project/org/trait definitions
  could become warnings, zero bonuses, zero costs, or omitted candidates.
- Empty ship catalogs could still produce a normal planning report; missing hull rows could make upkeep zero.
- Unknown scenarios selected default rules and raw overlay discovery swallowed malformed metadata.

## Allowed raw IO

- `build_*_catalog.py` and `build_runtime_catalogs.py`: deterministic packaged-data generation.
- `catalog-verify`: explicit developer comparison of packaged output against an installed game.
- Generator fixture tests and raw-reference verification tests.

Normal CLI commands and calculation modules are not allowed to use raw template or DLC paths after migration.

## Final audit result

- CLI startup, snapshot, org, income, hab, topbar, nation/world/advise, research, project analysis, ship planning,
  simulation, and upkeep now have zero prohibited raw-loader calls.
- The only AST-allowlisted edges are `load_trait_templates -> load_named_templates` and
  `scenario_template_sources -> load_named_templates` inside the legacy raw utility module. No normal command
  reaches either helper; they remain for generator/raw inspection compatibility.
- Missing relevant effects, traits, org state/catalog rows, active research rows, saved designs, and ship
  components now fail closed through `CalculationDependencyError`. Empty optional ship slots remain valid.
- Unsupported scenarios fail exact catalog selection and are returned by the CLI as structured incomplete output.
