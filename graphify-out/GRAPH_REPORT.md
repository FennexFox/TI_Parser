# Graph Report - TI_Parser  (2026-09-02)

## Corpus Check
- 141 files · ~664,830 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2308 nodes · 5996 edges · 139 communities (130 shown, 9 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 163 edges (avg confidence: 0.69)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `74b24d12`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- state_value_by_id
- CatalogError
- ti_save_parser.py
- Any
- build_runtime_catalogs.py
- build_research_catalog.py
- ti_parser_nation_projection.py
- ti_parser_core.py
- as_float
- ParserReliabilityTests
- ti_parser_org.py
- ti_parser_hab.py
- ti_parser_snapshot.py
- evaluate_priority_validity
- Path
- type_entries
- ti_parser_claims.py
- org
- calculate_hab_ui
- ResearchUiTests
- ti_parser_catalogs.py
- HabPlanTests
- TI Parser Reliability and Provenance
- Package-only reliability master plan
- HabPowerTests
- Org eligibility output master plan
- Package-Only Runtime
- CatalogVerifyTests
- NationClaimsTests
- ParserOrgParityTests
- build_parser
- High-Value Recommendation Inputs
- ScenarioRuleTests
- ShipPlanTests
- Terra Invicta Save Parser README
- Queued control centers master plan
- Terra Invicta Research Catalog
- Scenario-Specific Parser Rules
- Memory Maintenance
- ParserCoreTests
- StrictEffectResolutionTests
- test_hab_slots.py
- ._save
- ProjectAnalysisTests
- ResearchPlanTests
- Org recommendation filtering phase
- Serena Project Configuration
- hab_research_and_mc
- runtime_raw_loader_calls
- CalculationDependencyError
- ref_id
- test_parser_snapshot.py
- context
- ti_parser_verify.py
- RuntimeCatalogTests
- Phase 05: Real-save mechanics registry and catalog extension
- Phase 01: Reproduce and bound the mission-control omission
- Phase 02: Add current-queue mission-control projection
- Phase 03: Regression and live-save verification
- Phase 01: Mechanics audit registry and data catalog
- Phase 02: Projection model and transactional engine
- Phase 03: CLI faction contribution and diagnostics integration
- Phase 04: Regression verification and documentation
- Phase 06: DLL-boundary runtime engine and priority mechanics
- Phase 07: Runtime diagnostics and CLI contract hardening
- Phase 08: Independent fixtures, real-save validation, and Graphify refresh
- Phase 09: Execution-based metric dependency graph
- Phase 01: Confirm authoritative nation-interest and owner-trait rules
- Phase 02: Expose candidate requirements and per-councilor eligibility
- Phase 03: Add regression coverage and validate the latest Broken Earth save
- Phase 04: Enforce the per-councilor 15-org assignment limit
- Phase 05: Enforce faction ideology restrictions
- Phase 06: Harden recommendation eligibility and end-to-end coverage
- Phase 01: Runtime dependency and silent-fallback audit
- Phase 02: Strict dependency and catalog foundation
- Phase 03: Effects traits and org catalogs
- Phase 04: Research runtime migration
- Phase 05: Ship runtime migration
- Phase 06: Package-only and raw-reference verification
- Phase 07: Nation claims diagnostics
- Phase 08: AI and fleet diagnostics
- Phase 09: Final regression documentation and audit
- Phase 01: Scenario identity and rule model
- Phase 02: Scenario rules and DLC template overlays
- Phase 03: Regression and save-file verification
- Phase 04: Campaign-start GDP CP-maintenance fix
- Phase 01: Player identity and packaged module catalog
- Phase 02: Unified hab module effective-state calculations
- Phase 03: CP capacity and event-based resource forecast
- Phase 04: Diagnostics and ExitSave regression verification
- Phase 05: Fail-closed location-aware solar power
- Phase 06: Packaged body and orbit location catalog
- Phase 07: Lagrange point catalog coverage
- Phase 10: Authoritative-prefix fail-closed diagnostics
- Nation projection mechanics audit
- Package-only reliability and diagnostics
- Phase 11: Shared priority validity and independent verification
- Include queued control centers in projected mission control
- Nation priority and conditional Advisor projection
- Org Eligibility Output
- Scenario-specific parser rules
- NationProjectionRealSaveTests
- TI Parser reliability and provenance
- Phase 12: Real-save matrix, documentation, and Graphify refresh
- Packaged Catalog Strategy
- Runtime dependency and silent-fallback audit
- Phase 01: Discovery and boundaries
- Phase 02: Implement mission lifecycle modeling
- Terra Invicta Save Parser
- Nation Priority and Conditional Advisor Projection
- Phase 03: Verification and cleanup
- test_parser_income.py
- Advise mission lifecycle projection
- Q: 2003, BE 시나리오 추가에 따른 시나리오별 규칙이 파서에 필요한지 판단하고 적용
- Q: 최신 세이브를 대상으로 내가 지금 통제하고 있는 국가의 우선순위 설정, 최우선적으로 추가 통제해야 하는 국가를 평가해줘. 국가 우선순위의 목표는 첫번째로 경제를 재건해서 충분한 IP를 확보하는 것, 두번째로 지식 12, 정부 10을 달성해서 연구력 산출을 극대화하는 거야.
- Q: 지상군 전쟁은 어떻게 하는 거야? 군사기술 0.2 차이 정도로는 상대국 영토에서 전투할 때 상대 병력의 "자국 방어" 보너스를 상쇄할 수 없어?
- Q: 호주를 통제해서 전쟁을 끝내는 데 성공했어. 지금 상태에서 다시 우선순위를 추천해줘. 우주 프로그램 설립에 투자하는 건 새로운 우주 레이스 기술 연구가 완료돼서 이제 우주 진출이 필요한 시점이기 때문이야.
- Q: 해당 세 국가만 보지 말고 전체적으로 검토해줘
- Q: 그리고 org 관련 파싱할 때, 해당 org가 특정 국가를 지배하지 않으면 획득 불가능하다던지, 위원에게 특정 속성이 없으면 할당 불가능하다던지 하는 것도 제대로 출력되고 있어?
- Q: 파서의 조직 추천에서 requiredOwnerTraits와 팩션 사용 제한을 필터링하고 eligibleCouncilors 기준으로 평가하도록 보완
- Q: MC 계산에 관제소가 누락되는 문제가 있는 것 같아. 해결해줘
- Q: TI Parser 신뢰성 보완: player/catalog/CP/hab/mining/forecast data flow
- Q: 관리노드 등의 정거장 모듈이 주는 CP캡 증가도 반영했어?
- Q: ExitSave solar-power audit: which Academy habs use Solar_Power_Variable_Output, do body/orbit templates resolve, and which power warnings remain after location-aware calculation?
- Q: 파서에는 추가 보완이 필요하다: 태양광 계산에 필요한 body/orbit template 누락 시 nominal fallback을 폐기하고 전력경고를 재평가하라
- Q: Read-only audit: enumerate every runtime load_named_templates call for TISpaceBodyTemplate.json/TIOrbitTemplate.json and propose packaged catalog API, scenario implications, diagnostics and tests.
- Q: packaged catalog도 추가해
- Q: Audit TILagrangePointState SunMarsL1 packaged location catalog coverage, runtime paths, normalized fields, and regression tests
- Q: Parser 8 packaged location_catalog.json에 SunMarsL1 같은 TILagrangePointState 위치를 추가하라
- Q: TI_Parser reliability / portability / diagnostics follow-up을 작업 가능한 계획으로 압축
- Q: How should nation claims resolve save nation and region ownership?
- Q: Implement TI_Parser package-only reliability catalogs diagnostics plan
- Q: noble metal을 쓸데없이 많이 소모하는 요소나, 지금 접근 가능한 지점 중 noble metal 산출량이 가장 많은 곳을 찾아줘
- Q: 최신 combat save에서 전투를 걸어오는 적 숫자를 줄인다던가 해서 승리로 바꿔줄 수 있어?
- Q: 서호주는 호주와 전쟁중인데, 군사력 수준은 높아도 물량이 적어. 호주갸 군사력에 투자하는만큼, 군사 우선순위를 아주 낮추면 믄제가 되지 않을까? 동티모르도 서호주가 군사적으로 불리해졌을 때 지원군을 보내기 위해 통제한 목적이 커.
- Q: 그리고 지식이 정부보다 선행되어야 한다는 건 알겠는데, 정부 투자를 지식 8.5부터 시작하는 이유는 뭐야? 해당 값에서 뭔가 변곡점같은 게 있어?
- Q: 호주를 내가 통제하고 있다면 강제로 평화협정을 맺을 수 있을텐데, 그렇지 못하다면 평화협정을 안 받아줄 수도 있어. 어떤 상황에 몰려야 호주가 평화협정을 수락할까? 그리고 평화협정을 체결하고 평화적 합병을 하는 게 나을까, 무력병탄을 하는 게 나을까?
- Q: BE 시나리오에서는 IP가 증가하는 산식이 달라져서 합산 IP가 적어지는 효과를 인구가 늘어나는 효과가 상쇄할 수도 있다던데 사실이야/

## God Nodes (most connected - your core abstractions)
1. `IndexedState` - 272 edges
2. `as_float()` - 187 edges
3. `ref_id()` - 87 edges
4. `clean_numbers()` - 63 edges
5. `NationProjectionState` - 50 edges
6. `state_value_by_id()` - 48 edges
7. `calculate_nation_ui()` - 42 edges
8. `context()` - 40 edges
9. `state()` - 40 edges
10. `NationProjectionTransactionTests` - 40 edges

## Surprising Connections (you probably didn't know these)
- `Fail-Closed Calculation Dependencies` --semantically_similar_to--> `Unsupported Priority Incomplete Result`  [INFERRED] [semantically similar]
  dev-docs/plan/parser-portability-reliability-2/runtime-dependency-audit.md → docs/plan/nation_projection/02-projection-core.md
- `Data-Only Nation Development Catalog` --semantically_similar_to--> `Packaged Catalog Strategy`  [INFERRED] [semantically similar]
  docs/plan/nation_projection/01-audit-registry.md → dev-docs/plan/ti-parser-reliability/00-master-plan.md
- `Missing org templates fail closed` --conceptually_related_to--> `Fail-closed calculations`  [INFERRED]
  dev-docs/plan/org-eligibility-output/06-recommendation-filtering.md → README.md
- `Sparse Exact Scenario Overrides` --semantically_similar_to--> `Base-Plus-Overlay Named Template Merge`  [INFERRED] [semantically similar]
  docs/research_catalog.md → dev-docs/plan/scenario-specific-rules/02-implementation.md
- `Package-Only Runtime` --semantically_similar_to--> `Audited Package-Only Projection`  [INFERRED] [semantically similar]
  dev-docs/plan/parser-portability-reliability-2/runtime-dependency-audit.md → docs/plan/nation_projection/00-master-plan.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Module-to-Project Unlock Chain** — docs_module_catalog_solar_collector [EXTRACTED 1.00]
- **Auditable Nation Projection Pipeline** — docs_nation_projection_mechanics_audit_shared_mechanics_rule_registry, docs_plan_nation_projection_01_audit_registry_data_only_nation_development_catalog, docs_plan_nation_projection_02_projection_core_projection_model_and_transactional_engine, docs_plan_nation_projection_03_cli_integration_cli_faction_contribution_and_diagnostics, docs_plan_nation_projection_04_verification_rule_linked_one_tick_fixtures [EXTRACTED 1.00]
- **Package-Only Fail-Closed Calculation Data** — dev_docs_plan_parser_portability_reliability_2_runtime_dependency_audit_package_only_runtime, dev_docs_plan_parser_portability_reliability_2_runtime_dependency_audit_fail_closed_dependency_errors, dev_docs_plan_ti_parser_reliability_00_master_plan_packaged_catalog_strategy, dev_docs_plan_ti_parser_reliability_00_master_plan_location_data_fail_closed_contract, docs_plan_nation_projection_01_audit_registry_data_only_nation_development_catalog, docs_plan_nation_projection_02_projection_core_unsupported_priority_incomplete_result [INFERRED 0.95]

## Communities (139 total, 9 thin omitted)

### Community 0 - "state_value_by_id"
Cohesion: 0.12
Nodes (36): state_value_by_id(), faction_is_active_human(), hab_barycenter_state(), hab_body_is_colonized(), hab_body_is_inhabited(), hab_body_is_irradiated(), hab_body_site_states(), hab_construction_surface_body() (+28 more)

### Community 1 - "CatalogError"
Cohesion: 0.18
Nodes (6): CatalogError, Any, RuntimeError, Validated, scenario-selected packaged calculation data., A packaged catalog is absent, corrupt, or incompatible., RuntimeCatalogs

### Community 2 - "ti_save_parser.py"
Cohesion: 0.06
Nodes (102): apply_effect_modifiers(), effect_modifier_delta(), IndexedState, raw_state_id(), faction_councilor_ids(), active_owned_control_points(), active_scenario_rules(), average() (+94 more)

### Community 3 - "Any"
Cohesion: 0.06
Nodes (82): faction_is_human_player(), find_faction_state(), first_value(), Return whether faction is the uniquely resolved human player faction., active_global_research_names(), active_project_names(), active_project_research_names(), active_slots_with_category() (+74 more)

### Community 4 - "build_runtime_catalogs.py"
Cohesion: 0.25
Nodes (29): _advisor_mission_payload(), build_all(), build_nation_claim_catalog(), build_nation_development_catalog(), build_row_catalog(), build_ship_catalog(), deterministic_json(), discover_supported_scenarios() (+21 more)

### Community 5 - "build_research_catalog.py"
Cohesion: 0.05
Nodes (92): CatalogGeneratorTests, Path, write_json(), write_text(), ResearchCatalogTests, body_max_radius_km(), body_mean_radius_km(), build_catalog() (+84 more)

### Community 6 - "ti_parser_nation_projection.py"
Cohesion: 0.05
Nodes (103): MechanicsRegistryTests, ProjectionCoverageTests, adviser_attribute_bonus_from_values(), mission_control_contribution_from_values(), nation_monthly_research_from_values(), proportional_cp_contribution(), Return the audited nation Advise stat/100 bonus with descending rank decay., CoverageResolver (+95 more)

### Community 7 - "ti_parser_core.py"
Cohesion: 0.14
Nodes (36): candidate_save_dirs(), candidate_templates_dirs(), _catalog_module_to_template(), clean_number(), file_fingerprint(), find_latest_save(), game_root_from_templates_dir(), json_default() (+28 more)

### Community 8 - "as_float"
Cohesion: 0.07
Nodes (68): as_float(), clean_numbers(), add_monthly_delta(), annotate_candidate_opportunity_costs(), bottleneck_penalty_from_delta(), calculate_ship_plan(), candidate_affordable(), candidate_focus_score() (+60 more)

### Community 9 - "ParserReliabilityTests"
Cohesion: 0.16
Nodes (3): add_state(), ParserReliabilityTests, ref()

### Community 10 - "ti_parser_org.py"
Cohesion: 0.16
Nodes (41): apply_conditional_attribute_mods(), calculate_org_plan(), clamp_attribute(), compare_condition(), condition_eval_unknown(), condition_nation_summary(), councilor_attribute_breakdown(), councilor_org_plan_profile() (+33 more)

### Community 11 - "ti_parser_hab.py"
Cohesion: 0.13
Nodes (44): add_state(), build_parity_fixture(), HabParserParityTests, ref(), Raised when location-aware solar output lacks authoritative location data., SolarPowerDataError, active_modules_in_sectors(), faction_active_org_mining_bonus() (+36 more)

### Community 12 - "ti_parser_snapshot.py"
Cohesion: 0.19
Nodes (29): cache_key(), ref_summary(), region_nation_summary(), resolve_ref(), average(), build_snapshot(), clamp_attribute(), control_point_summary() (+21 more)

### Community 13 - "evaluate_priority_validity"
Cohesion: 0.23
Nodes (9): NationPriorityValidityTests, _boolean(), evaluate_priority_validity(), _number(), PriorityValidityResult, Any, Shared value-only nation priority validity contract., Evaluate only validity; callers precompute mechanics-specific derived inputs. (+1 more)

### Community 14 - "Path"
Cohesion: 0.22
Nodes (32): build_index(), load_save(), print_json(), match_named(), command_advise(), command_ai_fleet_diagnostics(), command_catalog_verify(), command_councilor() (+24 more)

### Community 15 - "type_entries"
Cohesion: 0.16
Nodes (29): add_state(), AIFleetDiagnosticsTests, ref(), synthetic_index(), _age_days(), calculate_ai_fleet_diagnostics(), _entry_id(), _explicit_blockers() (+21 more)

### Community 16 - "ti_parser_claims.py"
Cohesion: 0.22
Nodes (19): calculate_nation_claims(), _catalog_claim_metadata(), _catalog_for_scenario(), _deep_merge(), _nation_summary(), _number_or_none(), _numeric_rule(), Any (+11 more)

### Community 17 - "org"
Cohesion: 0.18
Nodes (5): eligibility_fixture(), org(), OrgPlanTests, profile(), ref()

### Community 18 - "calculate_hab_ui"
Cohesion: 0.08
Nodes (61): faction_effect_contexts(), load_hab_module_catalog(), Load packaged normalized hab modules; absence or corruption is fatal., councilor_summary_maps(), calculate_hab_plan(), calculate_hab_slots(), calculate_hab_ui(), calculate_topbar() (+53 more)

### Community 19 - "ResearchUiTests"
Cohesion: 0.21
Nodes (6): add_human_player(), add_state(), build_mission_control_fixture(), build_research_fixture(), ref(), ResearchUiTests

### Community 20 - "ti_parser_catalogs.py"
Cohesion: 0.23
Nodes (14): canonical_json_bytes(), envelope_payload(), file_sha256(), _is_sha256(), _load_json(), load_runtime_catalogs(), _merge_overlay(), Path (+6 more)

### Community 21 - "HabPlanTests"
Cohesion: 0.18
Nodes (3): add_state(), HabPlanTests, ref()

### Community 22 - "TI Parser Reliability and Provenance"
Cohesion: 0.16
Nodes (14): Location Data Fail-Closed Contract, TI Parser Reliability and Provenance, Metric-Specific Prior-Module Semantics, Unified Hab Module Effective State, CP Capacity and Event-Based Resource Forecast, Negative-Power Incomplete Forecast, Diagnostics and ExitSave Regression Verification, External Save Fixture Policy (+6 more)

### Community 23 - "Package-only reliability master plan"
Cohesion: 0.17
Nodes (16): Package-only reliability master plan, Runtime and verification boundary, Exact scenario strictness, Runtime dependency audit phase, Raw-loader regression guard, Manifest and catalog integrity, Strict catalog foundation phase, Structured calculation dependencies (+8 more)

### Community 24 - "HabPowerTests"
Cohesion: 0.25
Nodes (3): add_state(), HabPowerTests, ref()

### Community 25 - "Org eligibility output master plan"
Cohesion: 0.18
Nodes (15): Org eligibility output master plan, Shared owner eligibility contract, Org eligibility rule discovery, Faction-scoped nation interest, Councilor owner trait rules, Enriched candidate eligibility contract, Org eligibility diagnostics implementation, Broken Earth eligibility evidence (+7 more)

### Community 26 - "Package-Only Runtime"
Cohesion: 0.40
Nodes (5): Fail-Closed Calculation Dependencies, Package-Only Runtime, Runtime Dependency and Silent-Fallback Audit, Audited Package-Only Projection, Strict Runtime Research Rows

### Community 27 - "CatalogVerifyTests"
Cohesion: 0.27
Nodes (3): CatalogVerifyTests, Path, write_json()

### Community 29 - "ParserOrgParityTests"
Cohesion: 0.29
Nodes (5): org_state(), ParserOrgParityTests, profile(), ref(), save_state()

### Community 30 - "build_parser"
Cohesion: 0.16
Nodes (9): ModuleType, NationProjectionCliTests, build_parser(), main(), ArgumentParser, Command-line parser and dispatch for the Terra Invicta save parser., build_parser(), main() (+1 more)

### Community 31 - "High-Value Recommendation Inputs"
Cohesion: 0.14
Nodes (13): All Normally Buildable Human Modules, Energy Lab, Fission Pile, TIHabModuleTemplate Source, Hab Support Cost, High-Value Recommendation Inputs, Module Economic Metrics, Outpost Core (+5 more)

### Community 34 - "Terra Invicta Save Parser README"
Cohesion: 0.24
Nodes (10): Current and projected MC separation, Core runtime catalogs phase, Normalized effect trait and org catalogs, Nation claims diagnostics phase, Claim mechanics evidence boundary, Terra Invicta Save Parser README, Fail-closed calculations, Modular parser architecture (+2 more)

### Community 35 - "Queued control centers master plan"
Cohesion: 0.27
Nodes (10): Queued control centers master plan, Signed mission control headroom, Mission control omission discovery, Hab planning mission control gap, Prior module remains active during upgrade, Current-queue mission control implementation, Mission control effect consistency, Target versus prior template queue delta (+2 more)

### Community 36 - "Terra Invicta Research Catalog"
Cohesion: 0.25
Nodes (7): Base-Plus-Overlay Named Template Merge, Scenario Rules and DLC Template Overlays, Canonical Research Prerequisite Logic, Faction Projects, Global Techs, Sparse Exact Scenario Overrides, Terra Invicta Research Catalog

### Community 37 - "Scenario-Specific Parser Rules"
Cohesion: 0.28
Nodes (9): Campaign-Start GDP Scaling, Canonical Scenario Identity, Scenario-Specific Parser Rules, Broken Earth Rule Values, Scenario Identity and Rule Model, Installed Save Validation, Scenario Regression and Save-File Verification, Campaign-Start GDP CP-Maintenance Fix (+1 more)

### Community 38 - "Memory Maintenance"
Cohesion: 0.36
Nodes (9): Dense Durable Agent Notes, Hierarchical Topic Folders, mem:core Root, Memory Maintenance, Memory Reference Graph, Memory Reference Syntax, Progressive Discovery, Stable Memory Update Threshold (+1 more)

### Community 41 - "test_hab_slots.py"
Cohesion: 0.46
Nodes (4): add_state(), build_hab_fixture(), HabSlotSummaryTests, ref()

### Community 42 - "._save"
Cohesion: 0.50
Nodes (4): PackageOnlyRuntimeTests, Path, ref(), state()

### Community 43 - "ProjectAnalysisTests"
Cohesion: 0.32
Nodes (3): add_state(), ProjectAnalysisTests, ref()

### Community 44 - "ResearchPlanTests"
Cohesion: 0.32
Nodes (3): add_state(), ref(), ResearchPlanTests

### Community 45 - "Org recommendation filtering phase"
Cohesion: 0.29
Nodes (7): Diagnostics separated from recommendations, Org recommendation filtering phase, Eligible councilors as recommendation basis, Candidate source normalization, Missing org templates fail closed, AI fleet diagnostics phase, Observed derived suspected and unknown layers

### Community 46 - "Serena Project Configuration"
Cohesion: 0.29
Nodes (7): Gitignore-Aware File Filtering, Local Project Overrides, Python Language Server, Serena Project Configuration, TI_Parser Project, UTF-8 Text Encoding, Writable Project Configuration

### Community 47 - "hab_research_and_mc"
Cohesion: 0.16
Nodes (18): active_faction_councilors(), active_modules_in_sectors(), diminishing_research_modifier(), faction_category_modifier_components(), faction_fleet_category_modifier(), faction_hab_category_modifier(), faction_has_helium3_access(), faction_investigations_modifier() (+10 more)

### Community 48 - "runtime_raw_loader_calls"
Cohesion: 0.50
Nodes (3): Counter, runtime_raw_loader_calls(), RuntimeRawLoaderGuardTests

### Community 49 - "CalculationDependencyError"
Cohesion: 0.23
Nodes (14): CalculationDependency, CalculationDependencyError, LocationCatalogError, RuntimeError, Raised when authoritative body/orbit data cannot be loaded safely., One required calculation input that could not be resolved safely., Raised instead of returning a value with required inputs omitted., SnapshotConfig (+6 more)

### Community 50 - "ref_id"
Cohesion: 0.20
Nodes (32): ref_id(), active_owned_control_points(), councilor_is_income_active(), councilor_monthly_income(), councilor_research_and_mc(), councilor_resource_income(), councilor_yearly_income(), faction_ideology_key() (+24 more)

### Community 52 - "context"
Cohesion: 0.13
Nodes (7): advisor_schedule(), context(), NationProjectionPlanTests, NationProjectionTransactionTests, state(), mechanic_rule_test(), Attach stable mechanic rule IDs and the assertion evidence kind.

### Community 53 - "ti_parser_verify.py"
Cohesion: 0.27
Nodes (18): _compare_values(), _comparison_check(), _display(), _load_json(), _parity_check(), Any, Path, Explicit raw-reference verification for packaged TI parser catalogs. This… (+10 more)

### Community 54 - "RuntimeCatalogTests"
Cohesion: 0.17
Nodes (3): Path, RuntimeCatalogTests, write_json()

### Community 55 - "Phase 05: Real-save mechanics registry and catalog extension"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 56 - "Phase 01: Reproduce and bound the mission-control omission"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 57 - "Phase 02: Add current-queue mission-control projection"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 58 - "Phase 03: Regression and live-save verification"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 59 - "Phase 01: Mechanics audit registry and data catalog"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 60 - "Phase 02: Projection model and transactional engine"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 61 - "Phase 03: CLI faction contribution and diagnostics integration"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 62 - "Phase 04: Regression verification and documentation"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 63 - "Phase 06: DLL-boundary runtime engine and priority mechanics"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 64 - "Phase 07: Runtime diagnostics and CLI contract hardening"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 65 - "Phase 08: Independent fixtures, real-save validation, and Graphify refresh"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 66 - "Phase 09: Execution-based metric dependency graph"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 67 - "Phase 01: Confirm authoritative nation-interest and owner-trait rules"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 68 - "Phase 02: Expose candidate requirements and per-councilor eligibility"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 69 - "Phase 03: Add regression coverage and validate the latest Broken Earth save"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 70 - "Phase 04: Enforce the per-councilor 15-org assignment limit"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 71 - "Phase 05: Enforce faction ideology restrictions"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 72 - "Phase 06: Harden recommendation eligibility and end-to-end coverage"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 73 - "Phase 01: Runtime dependency and silent-fallback audit"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 74 - "Phase 02: Strict dependency and catalog foundation"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 75 - "Phase 03: Effects traits and org catalogs"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 76 - "Phase 04: Research runtime migration"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 77 - "Phase 05: Ship runtime migration"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 78 - "Phase 06: Package-only and raw-reference verification"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 79 - "Phase 07: Nation claims diagnostics"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 80 - "Phase 08: AI and fleet diagnostics"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 81 - "Phase 09: Final regression documentation and audit"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 82 - "Phase 01: Scenario identity and rule model"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 83 - "Phase 02: Scenario rules and DLC template overlays"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 84 - "Phase 03: Regression and save-file verification"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 85 - "Phase 04: Campaign-start GDP CP-maintenance fix"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 86 - "Phase 01: Player identity and packaged module catalog"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 87 - "Phase 02: Unified hab module effective-state calculations"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 88 - "Phase 03: CP capacity and event-based resource forecast"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 89 - "Phase 04: Diagnostics and ExitSave regression verification"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 90 - "Phase 05: Fail-closed location-aware solar power"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 91 - "Phase 06: Packaged body and orbit location catalog"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 92 - "Phase 07: Lagrange point catalog coverage"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 93 - "Phase 10: Authoritative-prefix fail-closed diagnostics"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 94 - "Nation projection mechanics audit"
Cohesion: 0.14
Nodes (14): Audited build, Completion-specific boundaries, Fail-closed completion rules, Fail-Closed Priority Coverage, Metric dependency evidence, Nation projection mechanics audit, Rule index, Shared live priority validity (+6 more)

### Community 95 - "Package-only reliability and diagnostics"
Cohesion: 0.20
Nodes (9): Completion, Global Validation Expectations, Issue Target And Scope Summary, Known Risks And Assumptions, Package-only reliability and diagnostics, Phase Dependencies, Phase Order, Source Of Truth Decisions (+1 more)

### Community 96 - "Phase 11: Shared priority validity and independent verification"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 97 - "Include queued control centers in projected mission control"
Cohesion: 0.22
Nodes (8): Global Validation Expectations, Include queued control centers in projected mission control, Issue Target And Scope Summary, Known Risks And Assumptions, Phase Dependencies, Phase Order, Source Of Truth Decisions, Strategy

### Community 98 - "Nation priority and conditional Advisor projection"
Cohesion: 0.22
Nodes (8): Global Validation Expectations, Issue Target And Scope Summary, Known Risks And Assumptions, Nation priority and conditional Advisor projection, Phase Dependencies, Phase Order, Source Of Truth Decisions, Strategy

### Community 99 - "Org Eligibility Output"
Cohesion: 0.22
Nodes (8): Global Validation Expectations, Issue Target And Scope Summary, Known Risks And Assumptions, Org Eligibility Output, Phase Dependencies, Phase Order, Source Of Truth Decisions, Strategy

### Community 100 - "Scenario-specific parser rules"
Cohesion: 0.22
Nodes (8): Global Validation Expectations, Issue Target And Scope Summary, Known Risks And Assumptions, Phase Dependencies, Phase Order, Scenario-specific parser rules, Source Of Truth Decisions, Strategy

### Community 102 - "TI Parser reliability and provenance"
Cohesion: 0.22
Nodes (8): Global Validation Expectations, Issue Target And Scope Summary, Known Risks And Assumptions, Phase Dependencies, Phase Order, Source Of Truth Decisions, Strategy, TI Parser reliability and provenance

### Community 103 - "Phase 12: Real-save matrix, documentation, and Graphify refresh"
Cohesion: 0.14
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 104 - "Packaged Catalog Strategy"
Cohesion: 0.33
Nodes (6): Packaged Catalog Strategy, Player Identity and Packaged Module Catalog, Strict Human-Player Resolution, Shared Mechanics Rule Registry, Data-Only Nation Development Catalog, Mechanics Audit Registry and Data Catalog

### Community 105 - "Runtime dependency and silent-fallback audit"
Cohesion: 0.33
Nodes (5): Allowed raw IO, Final audit result, Normal-runtime raw sources, Runtime dependency and silent-fallback audit, Silent correctness degradation

### Community 106 - "Phase 01: Discovery and boundaries"
Cohesion: 0.15
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 107 - "Phase 02: Implement mission lifecycle modeling"
Cohesion: 0.15
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 109 - "Nation Priority and Conditional Advisor Projection"
Cohesion: 0.29
Nodes (7): Strict and Observational Validation Boundary, Nation Priority and Conditional Advisor Projection, CLI Faction Contribution and Diagnostics Integration, Hypothetical Advisor Policy, Target-Nation Faction Contribution, Projection Regression Verification, Rule-Linked One-Tick Fixtures

### Community 110 - "Phase 03: Verification and cleanup"
Cohesion: 0.15
Nodes (13): Acceptance criteria, Affected files, Decision log, Goal, Implementation steps, Manual smoke tests, Non-goals, Outcomes / Retrospective (+5 more)

### Community 112 - "Advise mission lifecycle projection"
Cohesion: 0.22
Nodes (9): Advise mission lifecycle projection, Global Validation Expectations, Issue Target And Scope Summary, Known Risks And Assumptions, Overall Progress, Phase Dependencies, Phase Order, Source Of Truth Decisions (+1 more)

### Community 114 - "Q: 2003, BE 시나리오 추가에 따른 시나리오별 규칙이 파서에 필요한지 판단하고 적용"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: 2003, BE 시나리오 추가에 따른 시나리오별 규칙이 파서에 필요한지 판단하고 적용, Source Nodes

### Community 115 - "Q: 최신 세이브를 대상으로 내가 지금 통제하고 있는 국가의 우선순위 설정, 최우선적으로 추가 통제해야 하는 국가를 평가해줘. 국가 우선순위의 목표는 첫번째로 경제를 재건해서 충분한 IP를 확보하는 것, 두번째로 지식 12, 정부 10을 달성해서 연구력 산출을 극대화하는 거야."
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: 최신 세이브를 대상으로 내가 지금 통제하고 있는 국가의 우선순위 설정, 최우선적으로 추가 통제해야 하는 국가를 평가해줘. 국가 우선순위의 목표는 첫번째로 경제를 재건해서 충분한 IP를 확보하는 것, 두번째로 지식 12, 정부 10을 달성해서 연구력 산출을 극대화하는 거야., Source Nodes

### Community 116 - "Q: 지상군 전쟁은 어떻게 하는 거야? 군사기술 0.2 차이 정도로는 상대국 영토에서 전투할 때 상대 병력의 "자국 방어" 보너스를 상쇄할 수 없어?"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: 지상군 전쟁은 어떻게 하는 거야? 군사기술 0.2 차이 정도로는 상대국 영토에서 전투할 때 상대 병력의 "자국 방어" 보너스를 상쇄할 수 없어?, Source Nodes

### Community 117 - "Q: 호주를 통제해서 전쟁을 끝내는 데 성공했어. 지금 상태에서 다시 우선순위를 추천해줘. 우주 프로그램 설립에 투자하는 건 새로운 우주 레이스 기술 연구가 완료돼서 이제 우주 진출이 필요한 시점이기 때문이야."
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: 호주를 통제해서 전쟁을 끝내는 데 성공했어. 지금 상태에서 다시 우선순위를 추천해줘. 우주 프로그램 설립에 투자하는 건 새로운 우주 레이스 기술 연구가 완료돼서 이제 우주 진출이 필요한 시점이기 때문이야., Source Nodes

### Community 118 - "Q: 해당 세 국가만 보지 말고 전체적으로 검토해줘"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: 해당 세 국가만 보지 말고 전체적으로 검토해줘, Source Nodes

### Community 119 - "Q: 그리고 org 관련 파싱할 때, 해당 org가 특정 국가를 지배하지 않으면 획득 불가능하다던지, 위원에게 특정 속성이 없으면 할당 불가능하다던지 하는 것도 제대로 출력되고 있어?"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: 그리고 org 관련 파싱할 때, 해당 org가 특정 국가를 지배하지 않으면 획득 불가능하다던지, 위원에게 특정 속성이 없으면 할당 불가능하다던지 하는 것도 제대로 출력되고 있어?, Source Nodes

### Community 120 - "Q: 파서의 조직 추천에서 requiredOwnerTraits와 팩션 사용 제한을 필터링하고 eligibleCouncilors 기준으로 평가하도록 보완"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: 파서의 조직 추천에서 requiredOwnerTraits와 팩션 사용 제한을 필터링하고 eligibleCouncilors 기준으로 평가하도록 보완, Source Nodes

### Community 121 - "Q: MC 계산에 관제소가 누락되는 문제가 있는 것 같아. 해결해줘"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: MC 계산에 관제소가 누락되는 문제가 있는 것 같아. 해결해줘, Source Nodes

### Community 122 - "Q: TI Parser 신뢰성 보완: player/catalog/CP/hab/mining/forecast data flow"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: TI Parser 신뢰성 보완: player/catalog/CP/hab/mining/forecast data flow, Source Nodes

### Community 123 - "Q: 관리노드 등의 정거장 모듈이 주는 CP캡 증가도 반영했어?"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: 관리노드 등의 정거장 모듈이 주는 CP캡 증가도 반영했어?, Source Nodes

### Community 124 - "Q: ExitSave solar-power audit: which Academy habs use Solar_Power_Variable_Output, do body/orbit templates resolve, and which power warnings remain after location-aware calculation?"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: ExitSave solar-power audit: which Academy habs use Solar_Power_Variable_Output, do body/orbit templates resolve, and which power warnings remain after location-aware calculation?, Source Nodes

### Community 125 - "Q: 파서에는 추가 보완이 필요하다: 태양광 계산에 필요한 body/orbit template 누락 시 nominal fallback을 폐기하고 전력경고를 재평가하라"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: 파서에는 추가 보완이 필요하다: 태양광 계산에 필요한 body/orbit template 누락 시 nominal fallback을 폐기하고 전력경고를 재평가하라, Source Nodes

### Community 126 - "Q: Read-only audit: enumerate every runtime load_named_templates call for TISpaceBodyTemplate.json/TIOrbitTemplate.json and propose packaged catalog API, scenario implications, diagnostics and tests."
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Read-only audit: enumerate every runtime load_named_templates call for TISpaceBodyTemplate.json/TIOrbitTemplate.json and propose packaged catalog API, scenario implications, diagnostics and tests., Source Nodes

### Community 127 - "Q: packaged catalog도 추가해"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: packaged catalog도 추가해, Source Nodes

### Community 128 - "Q: Audit TILagrangePointState SunMarsL1 packaged location catalog coverage, runtime paths, normalized fields, and regression tests"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Audit TILagrangePointState SunMarsL1 packaged location catalog coverage, runtime paths, normalized fields, and regression tests, Source Nodes

### Community 129 - "Q: Parser 8 packaged location_catalog.json에 SunMarsL1 같은 TILagrangePointState 위치를 추가하라"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Parser 8 packaged location_catalog.json에 SunMarsL1 같은 TILagrangePointState 위치를 추가하라, Source Nodes

### Community 130 - "Q: TI_Parser reliability / portability / diagnostics follow-up을 작업 가능한 계획으로 압축"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: TI_Parser reliability / portability / diagnostics follow-up을 작업 가능한 계획으로 압축, Source Nodes

### Community 131 - "Q: How should nation claims resolve save nation and region ownership?"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: How should nation claims resolve save nation and region ownership?, Source Nodes

### Community 132 - "Q: Implement TI_Parser package-only reliability catalogs diagnostics plan"
Cohesion: 0.40
Nodes (4): Answer, Outcome, Q: Implement TI_Parser package-only reliability catalogs diagnostics plan, Source Nodes

### Community 135 - "Q: noble metal을 쓸데없이 많이 소모하는 요소나, 지금 접근 가능한 지점 중 noble metal 산출량이 가장 많은 곳을 찾아줘"
Cohesion: 0.50
Nodes (3): Answer, Q: noble metal을 쓸데없이 많이 소모하는 요소나, 지금 접근 가능한 지점 중 noble metal 산출량이 가장 많은 곳을 찾아줘, Source Nodes

### Community 136 - "Q: 최신 combat save에서 전투를 걸어오는 적 숫자를 줄인다던가 해서 승리로 바꿔줄 수 있어?"
Cohesion: 0.50
Nodes (3): Answer, Q: 최신 combat save에서 전투를 걸어오는 적 숫자를 줄인다던가 해서 승리로 바꿔줄 수 있어?, Source Nodes

### Community 137 - "Q: 서호주는 호주와 전쟁중인데, 군사력 수준은 높아도 물량이 적어. 호주갸 군사력에 투자하는만큼, 군사 우선순위를 아주 낮추면 믄제가 되지 않을까? 동티모르도 서호주가 군사적으로 불리해졌을 때 지원군을 보내기 위해 통제한 목적이 커."
Cohesion: 0.50
Nodes (3): Answer, Q: 서호주는 호주와 전쟁중인데, 군사력 수준은 높아도 물량이 적어. 호주갸 군사력에 투자하는만큼, 군사 우선순위를 아주 낮추면 믄제가 되지 않을까? 동티모르도 서호주가 군사적으로 불리해졌을 때 지원군을 보내기 위해 통제한 목적이 커., Source Nodes

### Community 138 - "Q: 그리고 지식이 정부보다 선행되어야 한다는 건 알겠는데, 정부 투자를 지식 8.5부터 시작하는 이유는 뭐야? 해당 값에서 뭔가 변곡점같은 게 있어?"
Cohesion: 0.50
Nodes (3): Answer, Q: 그리고 지식이 정부보다 선행되어야 한다는 건 알겠는데, 정부 투자를 지식 8.5부터 시작하는 이유는 뭐야? 해당 값에서 뭔가 변곡점같은 게 있어?, Source Nodes

### Community 139 - "Q: 호주를 내가 통제하고 있다면 강제로 평화협정을 맺을 수 있을텐데, 그렇지 못하다면 평화협정을 안 받아줄 수도 있어. 어떤 상황에 몰려야 호주가 평화협정을 수락할까? 그리고 평화협정을 체결하고 평화적 합병을 하는 게 나을까, 무력병탄을 하는 게 나을까?"
Cohesion: 0.50
Nodes (3): Answer, Q: 호주를 내가 통제하고 있다면 강제로 평화협정을 맺을 수 있을텐데, 그렇지 못하다면 평화협정을 안 받아줄 수도 있어. 어떤 상황에 몰려야 호주가 평화협정을 수락할까? 그리고 평화협정을 체결하고 평화적 합병을 하는 게 나을까, 무력병탄을 하는 게 나을까?, Source Nodes

### Community 140 - "Q: BE 시나리오에서는 IP가 증가하는 산식이 달라져서 합산 IP가 적어지는 효과를 인구가 늘어나는 효과가 상쇄할 수도 있다던데 사실이야/"
Cohesion: 0.50
Nodes (3): Answer, Q: BE 시나리오에서는 IP가 증가하는 산식이 달라져서 합산 IP가 적어지는 효과를 인구가 늘어나는 효과가 상쇄할 수도 있다던데 사실이야/, Source Nodes

## Knowledge Gaps
- **693 isolated node(s):** `CoverageResolvers`, `Issue Target And Scope Summary`, `Strategy`, `Phase Order`, `Phase Dependencies` (+688 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **9 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Work-memory lessons

**Preferred sources** — corroborated by past sessions; start here.
- `load_named_templates()` (4× useful, score=2.934660215)
- `hab_location_summary()` (4× useful, score=2.852465203) _(code changed — re-verify)_
- `orbit_template_semi_major_axis_km()` (4× useful, score=2.85211256) _(code changed — re-verify)_
- `calculate_org_plan()` (3× useful, score=2.034089704)
- `lagrange_solar_visibility()` (2× useful, score=1.426750322) _(code changed — re-verify)_
- `calculate_topbar()` (2× useful, score=1.387064451) _(code changed — re-verify)_
- `org_plan_best_assignment()` (2× useful, score=1.238750834)
- `org_plan_owner_eligibility()` (2× useful, score=1.238750834)

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `IndexedState` connect `ti_save_parser.py` to `ScenarioRuleTests`, `state_value_by_id`, `Any`, `ti_parser_core.py`, `as_float`, `ti_parser_org.py`, `ti_parser_hab.py`, `ti_parser_snapshot.py`, `Path`, `type_entries`, `ti_parser_claims.py`, `CalculationDependencyError`, `calculate_hab_ui`, `ref_id`, `hab_research_and_mc`, `NationClaimsTests`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Why does `Rules` connect `ti_parser_nation_projection.py` to `CalculationDependencyError`, `ti_save_parser.py`, `context`, `evaluate_priority_validity`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Why does `NationProjectionTransactionTests` connect `context` to `ti_parser_nation_projection.py`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `IndexedState` (e.g. with `_ResolutionStats` and `HabConfig`) actually correct?**
  _`IndexedState` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `CoverageResolvers`, `Issue Target And Scope Summary`, `Strategy` to the rest of the system?**
  _693 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `state_value_by_id` be split into smaller, more focused modules?**
  _Cohesion score 0.11904761904761904 - nodes in this community are weakly interconnected._
- **Should `ti_save_parser.py` be split into smaller, more focused modules?**
  _Cohesion score 0.05549450549450549 - nodes in this community are weakly interconnected._