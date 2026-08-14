# Graph Report - C:\Users\techn\source\repos\FennexFox\TI_Parser  (2026-08-03)

## Corpus Check
- 19 files · ~184,305 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 834 nodes · 3065 edges · 56 communities (34 shown, 22 thin omitted)
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 129 edges (avg confidence: 0.77)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Parser Core Snapshot
- Save State Analysis
- Module Catalog Builder
- Faction Resource Analysis
- Research Project Analysis
- Faction State Modifiers
- Councilor Organization Planning
- Habitat Economy Effects
- Habitat Operational Constraints
- Habitat Mining Systems
- Faction Income Analysis
- CLI Commands and Snapshots
- Habitat Construction Costs
- Habitat Planning Tests
- Module Recommendation Inputs
- Organization Planning Tests
- Research Dependency Reasoning
- UI Reconstruction Systems
- Organization Parser Parity
- Research UI Tests
- Ship Design Tests
- Habitat Module Planning
- CLI Parser Dispatch
- Agent Memory Architecture
- Parser Core Tests
- Scenario Rule Tests
- Habitat Power Tests
- Habitat Slot Tests
- Project Analysis Tests
- Research Planning Tests
- Serena Project Configuration
- Catalog Generator Tests
- Habitat Parser Parity
- Research Catalog Tests
- Space Propulsion Research
- Snapshot Cache Tests
- Scenario Parser Lifecycle
- Broken Earth Verification
- Income Parser Tests
- Scenario Template Overlays
- Scenario Identity
- Noble Metal Costs
- Noble Metal Mining
- Alien Combat Fleet
- Combat Save Validation
- Broken Earth Rules
- Australia Control Priority
- Controlled Nation Priorities
- East Timor Support
- Western Australia Strategy
- Education Catch-up Threshold
- Knowledge Government Investment
- Australia Peace Acceptance
- Peaceful Australian Unification
- Broken Earth Population Scaling
- Broken Earth Unification Tradeoff

## God Nodes (most connected - your core abstractions)
1. `IndexedState` - 196 edges
2. `as_float()` - 172 edges
3. `ref_id()` - 65 edges
4. `clean_numbers()` - 57 edges
5. `calculate_nation_ui()` - 40 edges
6. `state_value_by_id()` - 37 edges
7. `calculate_hab_ui()` - 31 edges
8. `first_value()` - 30 edges
9. `load_named_templates()` - 29 edges
10. `resolve_ref()` - 29 edges

## Surprising Connections (you probably didn't know these)
- `Memory Reference Graph` --semantically_similar_to--> `Derived Prerequisite Graph`  [INFERRED] [semantically similar]
  .serena/memories/memory_maintenance.md → docs/research_catalog.md
- `Terra Invicta Save Parser` --conceptually_related_to--> `TI_Parser Project`  [INFERRED]
  README.md → .serena/project.yml
- `Terra Invicta Save Parser` --conceptually_related_to--> `Python Language Server`  [INFERRED]
  README.md → .serena/project.yml
- `Research Screen Reconstruction` --conceptually_related_to--> `Terra Invicta Research Catalog`  [INFERRED]
  README.md → docs/research_catalog.md
- `Faction Project Analysis` --conceptually_related_to--> `Terra Invicta Hab Module Catalog`  [INFERRED]
  README.md → docs/module_catalog.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Catalog-Driven Hab Planning** — readme_hab_panel_reconstruction, readme_hab_slot_planning, docs_module_catalog_terra_invicta_hab_module_catalog, docs_research_catalog_faction_projects [INFERRED 0.85]
- **Evidence-Shaped Research Planning** — readme_research_decision_report, readme_faction_project_analysis, docs_research_catalog_canonical_requirements, docs_research_catalog_derived_prerequisite_graph [INFERRED 0.85]
- **Module-to-Project Unlock Chain** — docs_module_catalog_solar_collector, docs_research_catalog_solar_collector_project, docs_research_catalog_platform_core_project, docs_research_catalog_outpost_core_project [EXTRACTED 1.00]

## Communities (56 total, 22 thin omitted)

### Community 0 - "Parser Core Snapshot"
Cohesion: 0.07
Nodes (84): cache_key(), campaign_code(), candidate_save_dirs(), candidate_templates_dirs(), clean_number(), clean_numbers(), effect_modifier_delta(), file_fingerprint() (+76 more)

### Community 1 - "Save State Analysis"
Cohesion: 0.07
Nodes (74): IndexedState, scenario_template_name(), active_owned_control_points(), active_scenario_rules(), average(), calculate_global_public_opinion(), calculate_hab_plan(), calculate_nation_ui() (+66 more)

### Community 2 - "Module Catalog Builder"
Cohesion: 0.09
Nodes (53): build_catalog(), build_cost(), build_markdown(), crew_support(), derive_tags(), format_resource_map(), load_module_localizations(), main() (+45 more)

### Community 3 - "Faction Resource Analysis"
Cohesion: 0.07
Nodes (48): as_float(), add_monthly_delta(), annotate_candidate_opportunity_costs(), candidate_affordable(), candidate_focus_score(), faction_excess_mission_control_yearly_income(), faction_investigations_modifier(), faction_resource_components_yearly() (+40 more)

### Community 4 - "Research Project Analysis"
Cohesion: 0.09
Nodes (45): datetime, active_global_research_names(), active_project_names(), active_project_research_names(), active_slots_with_category(), active_slots_with_hypothetical_project_category(), available_global_research_templates(), available_project_research_templates() (+37 more)

### Community 5 - "Faction State Modifiers"
Cohesion: 0.12
Nodes (43): ref_id(), state_value_by_id(), active_faction_councilors(), active_modules_in_sectors(), diminishing_research_modifier(), faction_category_modifier_components(), faction_fleet_category_modifier(), faction_hab_category_modifier() (+35 more)

### Community 6 - "Councilor Organization Planning"
Cohesion: 0.16
Nodes (39): apply_conditional_attribute_mods(), calculate_org_plan(), clamp_attribute(), compare_condition(), condition_eval_unknown(), condition_nation_summary(), councilor_attribute_breakdown(), councilor_org_plan_profile() (+31 more)

### Community 7 - "Habitat Economy Effects"
Cohesion: 0.11
Nodes (37): apply_effect_modifiers(), faction_effect_contexts(), calculate_hab_ui(), candidate_module_monthly_delta(), faction_max_mission_control_components(), faction_mining_rate(), faction_yearly_income_from_habs(), hab_administration_modifier() (+29 more)

### Community 8 - "Habitat Operational Constraints"
Cohesion: 0.08
Nodes (36): bottleneck_penalty_from_delta(), councilor_is_income_active(), faction_control_point_maintenance(), faction_public_opinion(), hab_control_point_capacity(), hab_core_completion_minimum_days(), hab_core_module_record(), hab_module_functional() (+28 more)

### Community 9 - "Habitat Mining Systems"
Cohesion: 0.19
Nodes (33): active_modules_in_sectors(), faction_active_org_mining_bonus(), faction_mining_multiplier(), faction_sector_states(), hab_administration_modifier(), hab_control_point_capacity(), hab_core_module_record(), hab_crew() (+25 more)

### Community 10 - "Faction Income Analysis"
Cohesion: 0.23
Nodes (32): active_owned_control_points(), councilor_is_income_active(), councilor_monthly_income(), councilor_research_and_mc(), councilor_resource_income(), councilor_yearly_income(), faction_ideology_key(), faction_public_opinion() (+24 more)

### Community 11 - "CLI Commands and Snapshots"
Cohesion: 0.19
Nodes (32): Namespace, build_index(), load_save(), print_json(), build_snapshot(), calculate_hab_slots(), calculate_world_ui(), command_advise() (+24 more)

### Community 12 - "Habitat Construction Costs"
Cohesion: 0.15
Nodes (22): faction_has_helium3_access(), faction_stockpile(), hab_body_is_irradiated(), hab_module_build_materials(), hab_module_construction_analysis(), hab_template_special_rules(), module_affordable_with_materials(), module_affordable_with_template_weights() (+14 more)

### Community 13 - "Habitat Planning Tests"
Cohesion: 0.18
Nodes (3): add_state(), HabPlanTests, ref()

### Community 14 - "Module Recommendation Inputs"
Cohesion: 0.24
Nodes (13): Energy Lab, Fission Pile, High-Value Recommendation Inputs, Outpost Core, Solar Collector, Xenology Lab, Energy Lab Project, Faction Projects (+5 more)

### Community 15 - "Organization Planning Tests"
Cohesion: 0.39
Nodes (4): org(), OrgPlanTests, profile(), ref()

### Community 16 - "Research Dependency Reasoning"
Cohesion: 0.25
Nodes (11): Alternative Prerequisite OR, Canonical Research Requirements, Derived Prerequisite Graph, Save-Specific Gate Omission, Terra Invicta Research Template Source, Terra Invicta Research Catalog, Evidence-Shaped Research Judgment, Faction Project Analysis (+3 more)

### Community 17 - "UI Reconstruction Systems"
Cohesion: 0.18
Nodes (11): Contextual Councilor Attributes, Daily Research Tooltip Reconstruction, Indexed Snapshot Cache, Nation Panel Reconstruction, Non-Combat Ship-Builder Simulation, Org Committee Assignment Search, Research Screen Reconstruction, Ship Design Report (+3 more)

### Community 18 - "Organization Parser Parity"
Cohesion: 0.33
Nodes (5): org_state(), ParserOrgParityTests, profile(), ref(), save_state()

### Community 19 - "Research UI Tests"
Cohesion: 0.35
Nodes (4): add_state(), build_research_fixture(), ref(), ResearchUiTests

### Community 21 - "Habitat Module Planning"
Cohesion: 0.20
Nodes (10): TIHabModuleTemplate Source, Hab Support Cost, Module Economic Metrics, Save-Contextual Module Recommendations, Template Income, Terra Invicta Hab Module Catalog, Hab Panel Reconstruction, Hab Slot Planning (+2 more)

### Community 22 - "CLI Parser Dispatch"
Cohesion: 0.28
Nodes (8): ModuleType, build_parser(), main(), ArgumentParser, Command-line parser and dispatch for the Terra Invicta save parser., build_parser(), main(), ArgumentParser

### Community 23 - "Agent Memory Architecture"
Cohesion: 0.36
Nodes (9): Dense Durable Agent Notes, Hierarchical Topic Folders, mem:core Root, Memory Maintenance, Memory Reference Graph, Memory Reference Syntax, Progressive Discovery, Stable Memory Update Threshold (+1 more)

### Community 26 - "Habitat Power Tests"
Cohesion: 0.50
Nodes (3): add_state(), HabPowerTests, ref()

### Community 27 - "Habitat Slot Tests"
Cohesion: 0.46
Nodes (4): add_state(), build_hab_fixture(), HabSlotSummaryTests, ref()

### Community 28 - "Project Analysis Tests"
Cohesion: 0.32
Nodes (3): add_state(), ProjectAnalysisTests, ref()

### Community 29 - "Research Planning Tests"
Cohesion: 0.32
Nodes (3): add_state(), ref(), ResearchPlanTests

### Community 30 - "Serena Project Configuration"
Cohesion: 0.29
Nodes (7): Gitignore-Aware File Filtering, Local Project Overrides, Python Language Server, Serena Project Configuration, TI_Parser Project, UTF-8 Text Encoding, Writable Project Configuration

### Community 31 - "Catalog Generator Tests"
Cohesion: 0.67
Nodes (4): CatalogGeneratorTests, Path, write_json(), write_text()

### Community 32 - "Habitat Parser Parity"
Cohesion: 0.60
Nodes (4): add_state(), build_parity_fixture(), HabParserParityTests, ref()

### Community 34 - "Space Propulsion Research"
Cohesion: 0.40
Nodes (5): Deep Space Propulsion Concepts, Electrothermal Propulsion, Global Techs, Nuclear Fission in Space, Solid Core Fission Systems

### Community 36 - "Scenario Parser Lifecycle"
Cohesion: 0.67
Nodes (4): Scenario-specific parser scope, Authoritative scenario metadata, Scenario-aware parser, Scenario regression validation

### Community 37 - "Broken Earth Verification"
Cohesion: 0.50
Nodes (4): Broken Earth rule differences, Immutable scenario-rule profile, Broken Earth output assertions, Real-save scenario checks

### Community 39 - "Scenario Template Overlays"
Cohesion: 0.67
Nodes (3): Missing scenario template data, Base-to-scenario template merging, Scenario template overlays

## Knowledge Gaps
- **35 isolated node(s):** `Namespace`, `Namespace`, `Stale Memory Check`, `Local Project Overrides`, `UTF-8 Text Encoding` (+30 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **22 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `file_fingerprint()` connect `Parser Core Snapshot` to `Save State Analysis`, `Module Catalog Builder`?**
  _High betweenness centrality (0.092) - this node is a cross-community bridge._
- **Why does `source_fingerprint()` connect `Module Catalog Builder` to `Parser Core Snapshot`?**
  _High betweenness centrality (0.090) - this node is a cross-community bridge._
- **Why does `IndexedState` connect `Save State Analysis` to `Parser Core Snapshot`, `Faction Resource Analysis`, `Research Project Analysis`, `Faction State Modifiers`, `Councilor Organization Planning`, `Habitat Economy Effects`, `Habitat Operational Constraints`, `Habitat Mining Systems`, `Faction Income Analysis`, `CLI Commands and Snapshots`, `Habitat Construction Costs`, `Scenario Rule Tests`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Are the 12 inferred relationships involving `IndexedState` (e.g. with `HabConfig` and `Any`) actually correct?**
  _`IndexedState` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 41 inferred relationships involving `as_float()` (e.g. with `faction_active_org_mining_bonus()` and `hab_administration_modifier()`) actually correct?**
  _`as_float()` has 41 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `ref_id()` (e.g. with `faction_active_org_mining_bonus()` and `hab_module_records()`) actually correct?**
  _`ref_id()` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 3 inferred relationships involving `clean_numbers()` (e.g. with `calculate_org_plan()` and `org_plan_best_assignment()`) actually correct?**
  _`clean_numbers()` has 3 INFERRED edges - model-reasoned connections that need verification._