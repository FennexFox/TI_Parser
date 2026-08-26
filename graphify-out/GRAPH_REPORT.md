# Graph Report - TI_Parser  (2026-08-26)

## Corpus Check
- 91 files · ~461,692 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1337 nodes · 4680 edges · 52 communities (45 shown, 7 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 134 edges (avg confidence: 0.73)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Save Indexing Core
- Runtime Catalog System
- Nation State Calculations
- Research Planning Pipeline
- Hab Catalog Builders
- Research Catalog Builder
- Nation Projection Engine
- Income Dependency Model
- Projection and Simulation Helpers
- Core Projection Tests
- Organization Planner
- Habitat Mechanics
- Hab Reference Resolution
- Hab UI and Resources
- CLI Save Loading
- AI Fleet Diagnostics
- Topbar and Research UI
- Org Planner Tests
- Hab Module Planning
- Research UI Tests
- Module Construction Analysis
- Hab Plan Tests
- Parser Reliability Design
- Package Runtime Migration
- Hab Power Tests
- Org Eligibility Design
- Nation Projection Audit
- Catalog Verification Tests
- Nation Claims Tests
- Org Parity Tests
- CLI Command Dispatch
- Hab Module Documentation
- Scenario Rules Tests
- Ship Planner Tests
- Project README Concepts
- Mission Control Projection
- Package Runtime Audit
- Scenario Rule Design
- Graphify Memory Model
- Parser Core Tests
- Strict Effect Tests
- Hab Slot Tests
- Package Runtime Tests
- Project Analysis Tests
- Research Plan Tests
- Recommendation Evidence Design
- Project Tooling Configuration
- Hab Parser Parity Tests
- Raw Loader Guard Tests
- Broken Earth Greece Query
- Income Wrapper Tests
- CLI Namespace

## God Nodes (most connected - your core abstractions)
1. `IndexedState` - 263 edges
2. `as_float()` - 186 edges
3. `ref_id()` - 86 edges
4. `clean_numbers()` - 63 edges
5. `state_value_by_id()` - 48 edges
6. `calculate_nation_ui()` - 40 edges
7. `type_entries()` - 34 edges
8. `first_value()` - 34 edges
9. `RuntimeCatalogs` - 33 edges
10. `resolve_ref()` - 33 edges

## Surprising Connections (you probably didn't know these)
- `Fail-Closed Calculation Dependencies` --semantically_similar_to--> `Unsupported Priority Incomplete Result`  [INFERRED] [semantically similar]
  dev-docs/plan/parser-portability-reliability-2/runtime-dependency-audit.md → docs/plan/nation_projection/02-projection-core.md
- `Missing org templates fail closed` --conceptually_related_to--> `Fail-closed calculations`  [INFERRED]
  dev-docs/plan/org-eligibility-output/06-recommendation-filtering.md → README.md
- `Package-Only Runtime` --semantically_similar_to--> `Audited Package-Only Projection`  [INFERRED] [semantically similar]
  dev-docs/plan/parser-portability-reliability-2/runtime-dependency-audit.md → docs/plan/nation_projection/00-master-plan.md
- `Sparse Exact Scenario Overrides` --semantically_similar_to--> `Base-Plus-Overlay Named Template Merge`  [INFERRED] [semantically similar]
  docs/research_catalog.md → dev-docs/plan/scenario-specific-rules/02-implementation.md
- `Data-Only Nation Development Catalog` --semantically_similar_to--> `Packaged Catalog Strategy`  [INFERRED] [semantically similar]
  docs/plan/nation_projection/01-audit-registry.md → dev-docs/plan/ti-parser-reliability/00-master-plan.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Package-Only Fail-Closed Calculation Data** — dev_docs_plan_parser_portability_reliability_2_runtime_dependency_audit_package_only_runtime, dev_docs_plan_parser_portability_reliability_2_runtime_dependency_audit_fail_closed_dependency_errors, dev_docs_plan_ti_parser_reliability_00_master_plan_packaged_catalog_strategy, dev_docs_plan_ti_parser_reliability_00_master_plan_location_data_fail_closed_contract, docs_plan_nation_projection_01_audit_registry_data_only_nation_development_catalog, docs_plan_nation_projection_02_projection_core_unsupported_priority_incomplete_result [INFERRED 0.95]
- **Exact Scenario Data Selection** — dev_docs_plan_scenario_specific_rules_00_master_plan_canonical_scenario_identity, dev_docs_plan_scenario_specific_rules_02_implementation_base_plus_overlay_merge, docs_research_catalog_sparse_exact_scenario_overrides, memory_query_20260814_010906_be_visions_of_greatness_greece_broken_earth_greece_naming_query [INFERRED 0.85]
- **Auditable Nation Projection Pipeline** — docs_nation_projection_mechanics_audit_shared_mechanics_rule_registry, docs_plan_nation_projection_01_audit_registry_data_only_nation_development_catalog, docs_plan_nation_projection_02_projection_core_projection_model_and_transactional_engine, docs_plan_nation_projection_03_cli_integration_cli_faction_contribution_and_diagnostics, docs_plan_nation_projection_04_verification_rule_linked_one_tick_fixtures [EXTRACTED 1.00]
- **Module-to-Project Unlock Chain** — docs_module_catalog_solar_collector [EXTRACTED 1.00]

## Communities (52 total, 7 thin omitted)

### Community 0 - "Save Indexing Core"
Cohesion: 0.06
Nodes (100): ParserSnapshotTests, Path, calculate_nation_claims(), _catalog_claim_metadata(), _catalog_for_scenario(), _deep_merge(), _nation_summary(), _number_or_none() (+92 more)

### Community 1 - "Runtime Catalog System"
Cohesion: 0.06
Nodes (67): Path, RuntimeCatalogTests, write_json(), build_all(), build_nation_claim_catalog(), build_nation_development_catalog(), build_row_catalog(), build_ship_catalog() (+59 more)

### Community 2 - "Nation State Calculations"
Cohesion: 0.07
Nodes (71): IndexedState, active_global_research_names(), active_owned_control_points(), active_scenario_rules(), available_global_research_templates(), average(), calculate_global_public_opinion(), calculate_nation_ui() (+63 more)

### Community 3 - "Research Planning Pipeline"
Cohesion: 0.07
Nodes (62): active_faction_councilors(), active_modules_in_sectors(), active_project_names(), active_project_research_names(), active_slots_with_category(), active_slots_with_hypothetical_project_category(), build_snapshot(), councilor_is_income_active() (+54 more)

### Community 4 - "Hab Catalog Builders"
Cohesion: 0.09
Nodes (46): CatalogGeneratorTests, Path, write_json(), write_text(), body_max_radius_km(), body_mean_radius_km(), build_catalog(), file_sha256() (+38 more)

### Community 5 - "Research Catalog Builder"
Cohesion: 0.09
Nodes (46): ResearchCatalogTests, build_catalog(), build_graph_links(), build_markdown(), canonical_json_bytes(), clean_value(), context_values(), discover_scenario_template_dirs() (+38 more)

### Community 6 - "Nation Projection Engine"
Cohesion: 0.11
Nodes (43): MechanicsRegistryTests, nation_monthly_research_from_values(), proportional_cp_contribution(), mechanic_diagnostics(), MechanicRule, Audited Terra Invicta mechanics registry shared by code, tests and diagnostics.…, Rules, validate_registry() (+35 more)

### Community 7 - "Income Dependency Model"
Cohesion: 0.12
Nodes (43): CalculationDependency, CalculationDependencyError, One required calculation input that could not be resolved safely., Raised instead of returning a value with required inputs omitted., active_owned_control_points(), adviser_attribute_bonus_from_values(), councilor_is_income_active(), councilor_monthly_income() (+35 more)

### Community 8 - "Projection and Simulation Helpers"
Cohesion: 0.09
Nodes (44): apply_effect_modifiers(), as_float(), faction_effect_contexts(), add_monthly_delta(), bottleneck_penalty_from_delta(), calculate_nation_projection(), candidate_focus_score(), faction_max_mission_control_components() (+36 more)

### Community 9 - "Core Projection Tests"
Cohesion: 0.10
Nodes (8): datetime, context(), NationProjectionPlanTests, NationProjectionTransactionTests, state(), add_state(), ParserReliabilityTests, ref()

### Community 10 - "Organization Planner"
Cohesion: 0.15
Nodes (42): apply_conditional_attribute_mods(), calculate_org_plan(), clamp_attribute(), compare_condition(), condition_eval_unknown(), condition_nation_summary(), councilor_attribute_breakdown(), councilor_org_plan_profile() (+34 more)

### Community 11 - "Habitat Mechanics"
Cohesion: 0.16
Nodes (40): ModuleCatalogError, Raised when authoritative hab-module data cannot be loaded safely., active_modules_in_sectors(), faction_active_org_mining_bonus(), faction_mining_multiplier(), faction_sector_states(), get_effective_module_state(), hab_administration_modifier() (+32 more)

### Community 12 - "Hab Reference Resolution"
Cohesion: 0.12
Nodes (41): Raised when location-aware solar output lacks authoritative location data., ref_id(), SolarPowerDataError, state_value_by_id(), faction_fleet_category_modifier(), faction_negative_yearly_income_from_unassigned_orgs(), faction_ship_designs(), faction_ship_states() (+33 more)

### Community 13 - "Hab UI and Resources"
Cohesion: 0.09
Nodes (40): faction_is_human_player(), Return whether faction is the uniquely resolved human player faction., calculate_hab_ui(), candidate_module_monthly_delta(), completion_datetime(), control_point_maintenance_gdp_scale(), current_save_datetime(), eta_from_daily() (+32 more)

### Community 14 - "CLI Save Loading"
Cohesion: 0.16
Nodes (39): build_index(), load_save(), print_json(), match_named(), calculate_hab_slots(), calculate_world_ui(), calculation_catalogs(), command_advise() (+31 more)

### Community 15 - "AI Fleet Diagnostics"
Cohesion: 0.16
Nodes (28): add_state(), AIFleetDiagnosticsTests, ref(), synthetic_index(), _age_days(), calculate_ai_fleet_diagnostics(), _entry_id(), _explicit_blockers() (+20 more)

### Community 16 - "Topbar and Research UI"
Cohesion: 0.13
Nodes (35): clean_numbers(), find_faction_state(), councilor_summary_maps(), calculate_hab_plan(), calculate_project_analysis(), calculate_research_breakdown(), calculate_research_plan(), calculate_research_ui() (+27 more)

### Community 17 - "Org Planner Tests"
Cohesion: 0.18
Nodes (5): eligibility_fixture(), org(), OrgPlanTests, profile(), ref()

### Community 18 - "Hab Module Planning"
Cohesion: 0.14
Nodes (27): load_hab_module_catalog(), Load packaged normalized hab modules; absence or corruption is fatal., annotate_candidate_opportunity_costs(), candidate_affordable(), hab_core_module_record(), hab_location_summary(), hab_module_active_record(), hab_module_candidate_rows() (+19 more)

### Community 19 - "Research UI Tests"
Cohesion: 0.21
Nodes (6): add_human_player(), add_state(), build_mission_control_fixture(), build_research_fixture(), ref(), ResearchUiTests

### Community 20 - "Module Construction Analysis"
Cohesion: 0.16
Nodes (20): faction_has_helium3_access(), faction_stockpile(), hab_module_build_materials(), hab_module_construction_analysis(), hab_module_construction_time_modifier(), hab_template_special_rules(), module_affordable_with_materials(), module_affordable_with_template_weights() (+12 more)

### Community 21 - "Hab Plan Tests"
Cohesion: 0.18
Nodes (3): add_state(), HabPlanTests, ref()

### Community 22 - "Parser Reliability Design"
Cohesion: 0.14
Nodes (18): Location Data Fail-Closed Contract, Packaged Catalog Strategy, TI Parser Reliability and Provenance, Player Identity and Packaged Module Catalog, Strict Human-Player Resolution, Metric-Specific Prior-Module Semantics, Unified Hab Module Effective State, CP Capacity and Event-Based Resource Forecast (+10 more)

### Community 23 - "Package Runtime Migration"
Cohesion: 0.17
Nodes (16): Package-only reliability master plan, Runtime and verification boundary, Exact scenario strictness, Runtime dependency audit phase, Raw-loader regression guard, Manifest and catalog integrity, Strict catalog foundation phase, Structured calculation dependencies (+8 more)

### Community 24 - "Hab Power Tests"
Cohesion: 0.25
Nodes (3): add_state(), HabPowerTests, ref()

### Community 25 - "Org Eligibility Design"
Cohesion: 0.18
Nodes (15): Org eligibility output master plan, Shared owner eligibility contract, Org eligibility rule discovery, Faction-scoped nation interest, Councilor owner trait rules, Enriched candidate eligibility contract, Org eligibility diagnostics implementation, Broken Earth eligibility evidence (+7 more)

### Community 26 - "Nation Projection Audit"
Cohesion: 0.16
Nodes (15): Fail-Closed Priority Coverage, Nation Projection Mechanics Audit, Shared Mechanics Rule Registry, Transactional Policy Observation, Strict and Observational Validation Boundary, Nation Priority and Conditional Advisor Projection, Mechanics Audit Registry and Data Catalog, Cloned Projection State (+7 more)

### Community 27 - "Catalog Verification Tests"
Cohesion: 0.27
Nodes (3): CatalogVerifyTests, Path, write_json()

### Community 29 - "Org Parity Tests"
Cohesion: 0.29
Nodes (5): org_state(), ParserOrgParityTests, profile(), ref(), save_state()

### Community 30 - "CLI Command Dispatch"
Cohesion: 0.18
Nodes (9): ModuleType, NationProjectionCliTests, build_parser(), main(), ArgumentParser, Command-line parser and dispatch for the Terra Invicta save parser., build_parser(), main() (+1 more)

### Community 31 - "Hab Module Documentation"
Cohesion: 0.17
Nodes (12): Energy Lab, Fission Pile, TIHabModuleTemplate Source, Hab Support Cost, High-Value Recommendation Inputs, Module Economic Metrics, Outpost Core, Save-Contextual Module Recommendations (+4 more)

### Community 34 - "Project README Concepts"
Cohesion: 0.24
Nodes (10): Current and projected MC separation, Core runtime catalogs phase, Normalized effect trait and org catalogs, Nation claims diagnostics phase, Claim mechanics evidence boundary, Terra Invicta Save Parser README, Fail-closed calculations, Modular parser architecture (+2 more)

### Community 35 - "Mission Control Projection"
Cohesion: 0.27
Nodes (10): Queued control centers master plan, Signed mission control headroom, Mission control omission discovery, Hab planning mission control gap, Prior module remains active during upgrade, Current-queue mission control implementation, Mission control effect consistency, Target versus prior template queue delta (+2 more)

### Community 36 - "Package Runtime Audit"
Cohesion: 0.20
Nodes (10): Fail-Closed Calculation Dependencies, Package-Only Runtime, Runtime Dependency and Silent-Fallback Audit, Base-Plus-Overlay Named Template Merge, Scenario Rules and DLC Template Overlays, Audited Package-Only Projection, Canonical Research Prerequisite Logic, Sparse Exact Scenario Overrides (+2 more)

### Community 37 - "Scenario Rule Design"
Cohesion: 0.28
Nodes (9): Campaign-Start GDP Scaling, Canonical Scenario Identity, Scenario-Specific Parser Rules, Broken Earth Rule Values, Scenario Identity and Rule Model, Installed Save Validation, Scenario Regression and Save-File Verification, Campaign-Start GDP CP-Maintenance Fix (+1 more)

### Community 38 - "Graphify Memory Model"
Cohesion: 0.36
Nodes (9): Dense Durable Agent Notes, Hierarchical Topic Folders, mem:core Root, Memory Maintenance, Memory Reference Graph, Memory Reference Syntax, Progressive Discovery, Stable Memory Update Threshold (+1 more)

### Community 41 - "Hab Slot Tests"
Cohesion: 0.46
Nodes (4): add_state(), build_hab_fixture(), HabSlotSummaryTests, ref()

### Community 42 - "Package Runtime Tests"
Cohesion: 0.50
Nodes (4): PackageOnlyRuntimeTests, Path, ref(), state()

### Community 43 - "Project Analysis Tests"
Cohesion: 0.32
Nodes (3): add_state(), ProjectAnalysisTests, ref()

### Community 44 - "Research Plan Tests"
Cohesion: 0.32
Nodes (3): add_state(), ref(), ResearchPlanTests

### Community 45 - "Recommendation Evidence Design"
Cohesion: 0.29
Nodes (7): Diagnostics separated from recommendations, Org recommendation filtering phase, Eligible councilors as recommendation basis, Candidate source normalization, Missing org templates fail closed, AI fleet diagnostics phase, Observed derived suspected and unknown layers

### Community 46 - "Project Tooling Configuration"
Cohesion: 0.29
Nodes (7): Gitignore-Aware File Filtering, Local Project Overrides, Python Language Server, Serena Project Configuration, TI_Parser Project, UTF-8 Text Encoding, Writable Project Configuration

### Community 47 - "Hab Parser Parity Tests"
Cohesion: 0.60
Nodes (4): add_state(), build_parity_fixture(), HabParserParityTests, ref()

### Community 48 - "Raw Loader Guard Tests"
Cohesion: 0.50
Nodes (3): Counter, runtime_raw_loader_calls(), RuntimeRawLoaderGuardTests

### Community 49 - "Broken Earth Greece Query"
Cohesion: 0.83
Nodes (4): Broken Earth Greece Naming Query, Dominion of Hellas, Owned-Region Union Naming Trigger, Visions of Greatness Claim Activation

## Knowledge Gaps
- **29 isolated node(s):** `Namespace`, `Stale Memory Check`, `Local Project Overrides`, `TI_Parser Project`, `Python Language Server` (+24 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **7 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `IndexedState` connect `Nation State Calculations` to `Scenario Rules Tests`, `Save Indexing Core`, `Research Planning Pipeline`, `Income Dependency Model`, `Projection and Simulation Helpers`, `Organization Planner`, `Habitat Mechanics`, `Hab Reference Resolution`, `Hab UI and Resources`, `CLI Save Loading`, `AI Fleet Diagnostics`, `Topbar and Research UI`, `Hab Module Planning`, `Module Construction Analysis`, `Nation Claims Tests`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Why does `CatalogError` connect `Runtime Catalog System` to `Save Indexing Core`, `Nation State Calculations`, `Income Dependency Model`, `Organization Planner`, `Topbar and Research UI`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Why does `as_float()` connect `Projection and Simulation Helpers` to `Save Indexing Core`, `Nation State Calculations`, `Research Planning Pipeline`, `Income Dependency Model`, `Organization Planner`, `Habitat Mechanics`, `Hab Reference Resolution`, `Hab UI and Resources`, `CLI Save Loading`, `Topbar and Research UI`, `Hab Module Planning`, `Module Construction Analysis`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `IndexedState` (e.g. with `_ResolutionStats` and `HabConfig`) actually correct?**
  _`IndexedState` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Namespace`, `Stale Memory Check`, `Local Project Overrides` to the rest of the system?**
  _29 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Save Indexing Core` be split into smaller, more focused modules?**
  _Cohesion score 0.05501675189560924 - nodes in this community are weakly interconnected._
- **Should `Runtime Catalog System` be split into smaller, more focused modules?**
  _Cohesion score 0.05672948791166952 - nodes in this community are weakly interconnected._