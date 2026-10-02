# Terra Invicta Save Parser

## Beta: standalone LLM analysis and simulation engine

Start with [한국어 Quickstart](docs/QUICKSTART_KO.md), the
[ChatGPT execution guide](docs/CHATGPT_START.md), or the optional [local MCP
stdio setup](docs/MCP_SETUP.md). The normal CLI ZIP needs Python only; no
companion, installed game, API key, or third-party runtime package is required.
Python 3.11–3.14 on Windows/Linux is the CI target, not a claim that every
platform or ChatGPT account has been manually validated.

```text
python tools/ti_save_parser.py --version
python tools/ti_save_parser.py capabilities
python tools/ti_save_parser.py --save campaign.gz inspect-save
python tools/ti_save_parser.py --save campaign.gz analyze --output bootstrap.json
# Only after accepting unverified version/mod compatibility:
python tools/ti_save_parser.py --save campaign.gz --allow-unverified topbar
```

`analyze` is bounded LLM bootstrap context: save/campaign/player identity,
compatibility, core resource/research/CP context and `availableAnalyses`.
Use specialized commands on demand. This beta does not add dashboards,
history, previous-save diffs, alerts, or companion integration. An optional
local MCP stdio adapter is documented in [MCP_SETUP.md](docs/MCP_SETUP.md) and
is not imported by the normal CLI.

`saveIdentity` schema 1 uses `sha256-canonical-save-json-v1`: SHA-256 of the
parsed save serialized with sorted keys, UTF-8 and compact JSON separators.
The hash serialization preserves Python JSON NaN/Infinity tokens found in game
saves; it is not an RFC canonical JSON format. Strings with those names remain
distinct. Bootstrap output represents any non-finite values explicitly.
Copies and differently compressed equivalent JSON have the same identity;
changed saved content has a different fingerprint. Path and mtime are excluded.
Campaign start and player resolution evidence remain explicit when unknown.

All calculation commands (including legacy summary/export/cache) require
verified compatibility or per-invocation `--allow-unverified`. The initial
compatibility registry intentionally contains no verified tuples. Raw/type
inspection and capabilities do not require calculation consent. Opt-in never
bypasses missing dependencies, unsupported scenarios or catalog integrity.
Existing successful result fields are retained, with compatibility metadata added.
`catalog-verify` and generator examples require the source checkout; their
development helpers are intentionally absent from the runtime ZIP.
Named primary subjects accept a positional name or `--entity-id`, never both.
Expected errors now return JSON/exit 2 instead of domain `SystemExit`; internal
errors return exit 1. `analyze` returns a usable JSON report with exit 2 when
calculations are deferred or incomplete. Its optional file output matches stdout.

For Python integrations, add the bundled `tools/` directory to the import path
and use `ti_parser_session.AnalysisSession`. `run()` provides the versioned
machine boundary; `inspect()`, `analyze()`, and `calculate()` retain their existing
payload/exception contracts. `calculation_scope()` yields
the indexed save for existing domain `calculate_*` functions while sharing a
validated catalog lifetime. Sessions are single-threaded and represent one
immutable save/runtime snapshot; create another after either input changes.

`ti_parser_registry.get_input_schema()` returns the canonical public argument
schema for each callable analysis. MCP consumes that schema and declares the
existing machine envelopes using the SDK-independent `ti_parser_schema` module.

```python
from pathlib import Path
from ti_parser_session import AnalysisSession

session = AnalysisSession(Path("campaign.gz"))
inspection = session.run("inspect-save")
# Explicit consent is required for an unverified version/mod/runtime tuple.
research = session.run("research-plan", allow_unverified=True, top=8)
resources = session.run("topbar", allow_unverified=True)
```

`run()` schema 1 includes `analysis`, `parserVersion`, `saveIdentity`,
`compatibility`, and `status`, with `result`, `missingDependencies`, or `error`
as applicable. Status is `complete`, `deferred` (compatibility consent required),
`incomplete` (missing dependencies or partial/unsupported calculation), or `error`
(invalid analysis/arguments/input). Partial results retain their full projection
prefix, scope status and diagnostics. Unexpected programming exceptions propagate;
save loading failures before session construction also remain exceptions.
The CLI keeps its existing output shapes and exit codes.

`capabilities` lists application argument names/defaults and `routingClass`.
Primary routes are available through `run()` and `calculate()`; `inspect-save`
and `analyze` are available through `run()`. Entity selectors accept a name or
integer ID. Projection receives `plan_payload` as parsed JSON and `checkpoints`
as a list of integer days, rather than a CLI file path or comma-separated string.
Do not pass CLI output/cache/template options to the Python boundary.
Sessions reuse their save index, lazy snapshot and validated catalog bundles
across calls. Treat inputs and returned domain state as read-only; use separate
sessions for different saves, changed runtime data, or concurrent work.

MIT applies to project code; see [game-derived data notice](docs/BETA_DATA_NOTICE.md)
for excluded assets and the unresolved redistribution review. No external
publication or ChatGPT acceptance is implied by a local test pass.


Small local parser for Terra Invicta `.gz` saves. It reads the full save once,
builds a compact indexed snapshot, and reuses a cache keyed by save path, size,
modification time, and packaged runtime catalog bytes. Cache hits validate the
current runtime bundle; malformed cache entries rebuild automatically, and
completed cache files replace previous entries atomically.

Implementation layout (current ownership):

- `tools/ti_parser_core.py` owns save loading, template loading, indexing, and reference helpers.
- `tools/ti_parser_snapshot.py` owns compact snapshot summaries and snapshot cache handling.
- `tools/ti_parser_income.py` owns councilor and nation income calculations.
- `tools/ti_parser_hab.py` owns hab module, support, mining, and power calculations.
- `tools/ti_parser_org.py` owns org-plan parsing, conditional evaluation, and committee assignment search.
- `tools/ti_parser_ship.py` owns pure ship component, resource, power, armor, and ranking helpers.
- `tools/ti_parser_ship_plan.py` owns saved-design simulation, shipyard timing, and ship plans.
- `tools/ti_parser_hab_ui.py` owns hab location, solar power, UI, and slot calculations.
- `tools/ti_parser_hab_construction.py` owns build requirements, materials, timing, and economic deltas.
- `tools/ti_parser_hab_plan.py` owns module candidate scoring, upgrade selection, and fill plans.
- `tools/ti_parser_research.py` owns research income, category modifiers, distribution, and current research UI.
- `tools/ti_parser_research_plan.py` owns available research candidates and planning scores.
- `tools/ti_parser_project_analysis.py` owns project consequences, module unlocks, and resource tradeoffs.
- `tools/ti_parser_topbar.py` owns faction income aggregation, maintenance, and resource forecasts.
- `tools/ti_parser_world.py` owns world population, environment, markets, wars, and atrocities.
- `tools/ti_parser_nation_ui.py` owns nation display values and priority-validity presentation.
- `tools/ti_parser_projection_adapter.py` extracts save state and assembles inputs for the projection engine.
- `tools/ti_parser_config.py` owns shared constants and configured calculation settings.
- `tools/ti_parser_runtime.py` owns configured snapshot/income/hab adapters and shared save-state helpers.
- `tools/ti_parser_commands.py` owns CLI input loading, domain calls, and output rendering.
- `tools/ti_parser_cli.py` owns argument parsing and command dispatch.
- `tools/ti_parser_catalogs.py` validates the packaged runtime bundle, manifest, exact scenario overlays, and fingerprints.
- `tools/ti_parser_mechanics.py` owns stable mechanics rule IDs and DLL/catalog/test provenance.
- `tools/ti_parser_nation_validity.py` owns the shared value-only, tri-state priority-validity evaluator.
- `tools/ti_parser_nation_projection.py` owns cloned projection state, plan parsing, transactional updates, and fail-closed coverage.
- `tools/ti_parser_projection_coverage.py` owns execution-derived metric evidence and dependency propagation.
- `tools/ti_save_parser.py` keeps only the public script entrypoint and explicit compatibility exports. Existing function names and signatures remain available.
- `tools/catalog_utils.py` contains shared catalog-generator helpers.
- `tools/ti_parser_compatibility.py` assesses save compatibility; `tools/ti_parser_errors.py` defines structured expected input errors; `tools/ti_parser_version.py` defines the distribution version.
- `tools/ti_parser_registry.py` owns stable machine-facing analysis metadata and argument contracts; `tools/ti_parser_application.py` maps analysis IDs to executable handlers; `tools/ti_parser_session.py` provides the reusable one-save API and versioned `run()` boundary.
- `tools/ti_parser_analysis.py` builds the bounded LLM bootstrap report, and `tools/ti_parser_capabilities.py` publishes the registry inventory.
- `tools/ti_parser_mcp.py` is the optional stdio MCP adapter. Its SDK dependency is isolated in `requirements-mcp.txt`; the normal CLI and Python API do not import it.
- `tools/ti_parser_schema.py` describes application machine envelopes and save-free capabilities without importing the MCP SDK.
- `tools/build_beta_distribution.py` builds the runtime ZIP; `tools/verify_beta_distribution.py` validates it.

The runtime ZIP includes the CLI, Python API, MCP adapter source, and MCP requirements file. The MCP SDK itself is optional and installed separately only in an environment that launches the adapter. Normal CLI and Python API use remain package-only and do not require it. Raw game templates and `Assembly-CSharp.dll` remain generation, audit, or `catalog-verify` inputs rather than normal runtime dependencies.
Domain modules import their dependencies directly and do not import the public
facade. Their dependency graph is acyclic. Tests or integrations that replace a
dependency with a mock should patch the module where it is used, rather than
rebinding the facade export.

Examples:

```powershell
python .\tools\ti_save_parser.py summary
python .\tools\ti_save_parser.py faction ResistCouncil
python .\tools\ti_save_parser.py nation KOR
python .\tools\ti_save_parser.py councilor Hanna
python .\tools\ti_save_parser.py councilor Hanna --target-nation USA --details
python .\tools\ti_save_parser.py councilor Hanna --current-location-context
python .\tools\ti_save_parser.py org-plan --focus balanced
python .\tools\ti_save_parser.py org-plan --focus science --market-only --top 3
python .\tools\ti_save_parser.py nation-ui "유럽 연합"
python .\tools\ti_save_parser.py hab-ui "제303기초연구단"
python .\tools\ti_save_parser.py hab-slots --faction ResistCouncil
python .\tools\ti_save_parser.py hab-plan --upgrading-to-tier 3 --focus research
python .\tools\ti_save_parser.py ship-plan --role colony --top 5
python .\tools\ti_save_parser.py ship-plan --role combat --include-obsolete
python .\tools\ti_save_parser.py ship-plan --design "PKG Defiant"
python .\tools\ti_save_parser.py project-analysis --top 10 --sort research-sustainable
python .\tools\ti_save_parser.py research --details
python .\tools\ti_save_parser.py research-ui
python .\tools\ti_save_parser.py research-plan --top 5
python .\tools\ti_save_parser.py topbar --details
python .\tools\ti_save_parser.py nation-claims KOR --target PRK --diagnostics
python .\tools\ti_save_parser.py nation-projection KOR --days 365
python .\tools\ti_save_parser.py nation-projection KOR --days 365 --plan-file plans.json --checkpoints 30,90,180,365
python .\tools\ti_save_parser.py nation-projection KOR --days 365 --plan-file plans.json --details --diagnostics
python .\tools\ti_save_parser.py ai-fleet-diagnostics --stale-days 365
python .\tools\build_research_catalog.py
python .\tools\build_runtime_catalogs.py --templates-dir "C:\...\StreamingAssets\Templates"
python .\tools\ti_save_parser.py --templates-dir "C:\...\StreamingAssets\Templates" catalog-verify --scenario ModernScenario
python .\tools\build_module_catalog.py
python .\tools\build_location_catalog.py
python .\tools\verify_fresh_export.py
python .\tools\ti_save_parser.py world-ui
python .\tools\ti_save_parser.py advise "Lati Wirya" "중화민국"
python .\tools\ti_save_parser.py types --limit 30
python .\tools\ti_save_parser.py raw --type TIFactionState --template ResistCouncil --keys displayName,resources,baseIncomes_year,missionControlUsage
```

The legacy examples below assume a verified tuple or explicit `--allow-unverified`.
Use global options such as `--save <path>` and `--refresh-cache` before the
subcommand.

## Package-only runtime and incomplete results

Normal commands do not discover or read an installed Terra Invicta template tree. Calculation data comes from the packaged effect, trait, org, research, ship, nation-claim, hab-module, and location catalogs under `data/`. Raw base/DLC templates and `Assembly-CSharp.dll` are generation or `catalog-verify` inputs only. `--templates-dir` is verification-only and is rejected for normal commands.

The common `catalog_manifest.json` records each new runtime catalog's file SHA-256, schema version, payload fingerprint, and a bundle fingerprint. Catalog envelopes contain deterministic source hashes, supported canonical scenarios, base data, and exact scenario overrides; timestamps and mtimes are excluded. Unsupported scenarios never inherit another scenario's values.

Each CLI invocation reuses its validated runtime bundles for matching scenario,
data directory, and requested catalogs. The next invocation validates files
again. Library callers can opt into the same lifetime with
`ti_parser_catalogs.runtime_catalog_scope()`; otherwise loads remain fresh.

If a save references a required effect, trait, applying org, active hab module/body location, weighted research row, saved ship component, or packaged shipyard that cannot be resolved, the CLI exits with code 2 and prints `status: "incomplete"` plus structured `missingDependencies`. Valid absence remains valid: empty source lists, non-applying orgs, zero-weight or locked research slots, and empty optional ship slots do not require catalog rows. Successful command JSON keeps its existing result shape.

Commands with `--diagnostics` include the selected scenario and catalog fingerprints. `nation-claims --diagnostics` keeps runtime provenance and rule-domain evidence separately under `calculationDiagnostics.runtime` and `.claims`, so scenario/fingerprint data cannot overwrite threshold, formula, assumptions, limitations, or missing-dependency evidence.

Ship catalogs are generated by resolving each component family against the exact scenario template tree and storing recursive minimal deltas. Weapon names are checked for cross-family collisions for base and every scenario. If the installed DLC supplies no ship overrides, the corresponding packaged scenario correctly reuses the base rows and reports no ship override applied.

`catalog-verify` is the only command that consumes raw templates. It rebuilds normalized reference catalogs, checks source hashes and scenario overlays, and—when a matching save is available—compares Mercury solar, CP cap, MC, research, org eligibility, and saved-design simulation with `rel_tol=1e-9` and `abs_tol=1e-6`.

`catalog-verify` exits with code 0 only when every check passes. Failed or
unavailable checks produce code 2 and preserve the detailed `failed` or `partial`
JSON report. With no local save, catalog checks still run and save-dependent
checks are reported as unavailable; an explicitly requested missing save is an
error.

`verify_fresh_export.py` is the cross-platform release gate. It creates a temporary `git -c core.autocrlf=false archive HEAD`, runs the full and package-only suites inside that export, and loads every packaged supported scenario. This verifies committed bytes and manifest hashes rather than trusting the current checkout's line-ending conversion.

Councilor attributes are calculated from save base values plus unconditional
trait and active-org modifiers, then clamped to the game's normal 25 cap.
Conditional trait modifiers are not mixed into `finalAttributes`; use
`--target-nation <name/code>` or `--current-location-context` to get
`contextualAttributes` for a specific situation.

The `org-plan` command evaluates the faction's currently acquirable
`availableOrgs` against every councilor. It reports per-councilor views for
balanced stats and each individual stat, applies the Administration capacity
limit, checks acquisition costs, required/prohibited owner traits, nation
interest, and faction ideology restrictions, and recommends a committee-wide
assignment sequence. `candidateSources` is a diagnostic inventory rather than
a recommendation list; each row's `recommendationEligibility` is derived from
its actual `eligibleCouncilors`, while actionable stat views are emitted under
`councilors.goalViews` and `committeePlan`. Already-owned unassigned orgs are
included by default so useful inventory is assigned before spending resources;
pass `--market-only` to evaluate acquisitions only. The committee plan uses a
bounded beam search with practical defaults; increase `--max-actions` or
`--beam-width` when a slower, broader search is useful.

The `research` command recalculates the UI's daily research tooltip from raw
save values, including councilor trait/org income, CP research effects,
knowledge-sector bonuses, hab efficiency modules, excess MC research, and
research-distribution bonuses. The `advise` command applies one hypothetical
Advise assignment to a nation and reports both the direct source increase and
the final increase after research-distribution bonuses.

The `research-ui` command reconstructs the Research screen's active slots. It
reads the three global techs from `TIGlobalResearchState.techProgress`, active
faction projects from `TIFactionState.currentProjectProgress` slots 3-5, slot
weights from `researchWeights`, category/project-facility modifiers, current
progress, daily slot output, faction contribution bars, and ETA dates. Project
records in slots 6+ are reported separately as paused/stored progress, not as
currently active project research slots.

The `research-plan` command builds an LLM-ready report for the question "what
global tech or faction project should I research next?" It automates objective
candidate collection and evidence shaping: currently active slots, paused
projects, available global techs, available projects, research costs, ETA
estimates at current slot weights, category synergy, downstream unlock counts,
critical template flags, resource-deficiency coverage, and existing progress.
It intentionally does not collapse those signals into a final strategic utility
ranking; the output includes goal-specific score views and source notes so an
LLM can make the value judgment explicitly.

The `topbar` command reconstructs the top resource bar from the save, including
current stockpiles, monthly/yearly net resource income, research distribution,
mission-control usage/capacity, and control-point maintenance usage/cap. Its
MissionControl row keeps current values separate from
`projectedAfterCurrentQueue`; habitat and project planning use that queued
projection while current research and excess-MC calculations use only operating
sources.

Factioned commands resolve the human player from `TIPlayerState.isAI == false`
and cross-check `TIMetadataState.playerFactionName`. They fail closed when the
player is missing, ambiguous, or conflicting; an explicit faction argument or
`--faction` remains an override. Faction identity output includes display name,
internal template, and `player` status.

`topbar --diagnostics` adds module/location catalog and effect provenance, mining formula samples,
and explicit calculation assumptions. `topbar --forecast-resource Volatiles`
recalculates faction-hab production and support after each module completion,
reports the completing modules and resulting hab power balance, and identifies
the first sustained positive event. A projected negative-power hab marks the
forecast `incomplete` instead of silently treating every completed module as
operational.

The packaged `data/module_catalog.json` is the runtime source of truth for hab
module income, upkeep, crew, power, MC, CP cap, build cost, requirements, and
bonuses. Missing catalogs or referenced templates are fatal calculation-data
errors, never zero-valued modules. The catalog generator reads raw templates
from the local Terra Invicta install and refreshes that JSON plus the
human-readable `docs/module_catalog.md`; raw module templates are generator
inputs, not an implicit runtime fallback.

The packaged `data/location_catalog.json` is the runtime source of truth for
location-aware body, Lagrange-point navigable, and orbit values used by solar
output, gravity, irradiation, construction, and mining calculations. Missing,
corrupt, empty, or incompatible
catalogs are fatal calculation-data errors. Variable-output solar modules also
fail when their exact body/orbit dependency cannot be resolved; they never use
nominal power as a fallback because that value can be wrong by several times
near Mercury. `build_location_catalog.py` reads the raw
`TISpaceBodyTemplate.json`, `TINavigableTemplate.json`, and
`TIOrbitTemplate.json` files only to regenerate the packaged catalog. Normal
parser execution does not read those raw files.

The research catalog v2 generator reads global tech and faction project templates
from the local Terra Invicta install and writes `data/research_catalog.json`
plus `docs/research_catalog.md`. The JSON stores research prerequisites as
explicit `all`/`any` boolean trees, plus derived graph indexes such as `edges`
and `childrenByPrereq`. Save-specific completion, objectives, milestones,
faction gates, and nation gates should be evaluated against that static catalog
rather than baked into it.

The `world-ui` command reconstructs the Intel screen's world tab values:
population, GDP, global public opinion, resource market prices, environmental
damage, active wars, and faction atrocity counts.

The `nation-ui` command reconstructs the nation panel values used for UI
validation, including federation-pooled funding/boost income, faction research
share, control-point priority weights, accumulated investment points, public
opinion, army/navy limits, nukes, and diplomacy lists.

The `nation-projection` command simulates conditional control-point priority and
Advisor policies without mutating the loaded save. Segment conditions are
observed only after a complete investment or verified periodic transaction; a
satisfied segment takes effect immediately before the next investment tick.
`nation.*` metrics describe the nation, while `factionContribution.*` describes
only the selected faction's share from that target nation. Advisor placement is
a desired repeat-order policy. The projection reads the save's mission-phase
cadence, clears active advisors at each phase, and reapplies them at the audited
expected order-0 resolution time. Actionable Advise has automatic 100% success
and `MoveToTarget` moves on assignment, so its travel duration is zero rather
than distance-based. `advisorMissionProjection` reports every renewal, the
inactive gap, and required Influence; future resource availability, target
invalidation, detention, and competing orders remain held fixed.

Projection mechanics are fail closed. Economy, Knowledge, Government, Welfare,
Unity, Funding, Mission Control, BuildArmy, and BuildNavy have supported paths; MC and
BuildArmy coverage is resolved from the actual execution path. Economy keeps
GDP, inequality, and region effects authoritative even when only its independent
world-market branch is unavailable. Unity requires a plan-level
`stochasticPolicy.unityPublicOpinion: "meanPath"` opt-in. Its direct cohesion,
education, and legitimize branches remain exact when their own inputs are exact,
while CP-owner propaganda is a sequential conditional expected transition.
BuildNavy converts the DLL-selected Human Standard army to Naval without creating
a new army. It preserves identity and location, updates live maintenance and
eligibility, and keeps its mean-input market effect independently covered.

Population and Unity both use `coverage: expected`, `provenance: meanPath`, and
`expectationGuarantee: false`, but they are not the same approximation.
Population reports `stochasticTreatment: deterministicMeanInput` because each
random scalar input is replaced by its mean. Unity reports
`deterministicExpectedTransition` because each integer-sample transition kernel
is replaced by its conditional expected flow and then fed sequentially to the
next CP owner. Neither is claimed to equal the mathematical expectation across
the complete nonlinear stochastic trajectory. `metricCoverage` is built from
the inputs and outputs actually executed, so each treatment reaches only its
real descendants. Rule-level placement/branch coverage remains separate from
placement-independent aggregate metric coverage.

Unsupported priorities or newly activated blocking dependencies return an `incomplete`
plan and are excluded from comparison/ranking. A completed handler, its cost,
and CP fallback/cache repair remain in the authoritative prefix; an unsupported
next allocation/effect is never executed. A missing independent Economy or
BuildArmy/BuildNavy market value instead leaves nation/faction scopes complete and marks
only `scopeStatus.worldMarket` incomplete. `runtimeStop` identifies the exact
timestamp/day/transaction/phase, trigger, authoritative mutations, unsupported
next step, state context, affected metrics, and attempted transaction.
`lastAuthoritativeState` and successful `authoritativeFinalState` include CP raw
and effective pips plus weight caches. `nation-ui` uses the same tri-state live
priority-validity evaluator and reports every CP's serialized/recomputed weight
consistency; missing inputs remain `valid: null`, not silently false. See
`docs/nation_projection_mechanics_audit.md` for the current rule index, coverage
resolvers, and validation boundary.

The `hab-ui` command reconstructs a hab panel from raw sector/module state and
module templates, including crew, location-adjusted solar power with active
solar-mirror bonuses, monthly net resources, research
category bonuses, Earth LEO priority bonuses, construction modifiers, and
`modules.slots` slot accounting. Raw saves can include locked future sector
placeholders with empty module slots; these should not be treated as currently
available build slots.

The `hab-slots` command lists faction habs with currently usable empty slots.
It defaults to the player faction, excludes habs with zero usable empty slots
unless `--all` is passed, and reports raw, usable, occupied, empty, locked, and
locked-empty slot counts for each hab.

The `hab-plan` command is a save-derived planning view for current and future
hab slots. It can scan the player's habs, filter to cores currently upgrading
to a target tier, and rank buildable module candidates for `balanced`,
`research`, `projects`, `category-bonus`, or `resources` focus. `research`
means monthly `Research` output only; `Projects` output and tech category
bonuses are separate score axes and are not silently converted into research.
Its `suggestedFill` output aggregates a transparent heuristic fill plan by
module count and includes projected final power, MC availability, and monthly
resource/research deltas. Candidate rows and suggested fills include slot
opportunity costs: for each focus, the best affordable candidate's score is
treated as the per-slot alternative value, and selected modules are charged for
the focus score they give up. If every candidate is non-positive for that
focus, the alternative value is zero. Locked placeholder slots are only
included in `plannedEmpty` when the current core module is actively upgrading
to a higher tier that will unlock those sectors. Candidate and upgrade rows
also report location-adjusted construction materials, build time, and
market-value break-even estimates. Location costs include gravity scaling,
solar-mirror distance scaling, irradiated-location extra metals, and the
two-thirds module-upgrade discount. Helium-3 access substitutes water for
eligible fissiles costs. Build time includes hab construction-speed modifiers
and any minimum wait for an in-progress core upgrade to complete.

`hab-plan` is intentionally not a full optimizer yet. It filters out combat and
objective-only modules for the economic planning view and should be treated as
a shortlist generator before committing construction in-game.
Candidate monthly deltas are calculated by comparing the whole hab before and
after a hypothetical completed module. For farm-style modules, negative support
means reduced existing crew upkeep rather than resource production.

The `project-analysis` command ranks available and stored faction projects on
multiple transparent heuristic axes instead of choosing a final answer. It
combines the current research slot model, active resource bottlenecks, direct
project effects/resource grants, and hab modules that a project would unlock.
Unlocked-module samples pretend the project is complete, scan current/planned
empty hab slots, and report 1/2/4-module effects using the best current hab
option. Treat those samples as LLM/human decision inputs: they do not solve the
global construction queue, reserve power-support modules, or enforce global MC
across every hypothetical build.

The `ship-plan` command builds an LLM-ready ship-design report from the player's
finished projects, obsolete-part settings, existing designs, resource state, and
packaged ship-component catalog. It reports unlocked hulls and core components,
separate drive shortlists for thrust and exhaust velocity, legal power-plant
pairings, weapon shortlists, and role-specific utility modules for `balanced`,
`combat`, `intercept`, `transfer`, `colony`, `assault`, or `science` planning.
Use `--include-obsolete` when a hidden legacy component is still useful and
`--all-components` when the full unlocked drive, utility, and weapon lists are
needed. Pass `--design <name-or-template-fragment>` to inspect one saved design
without printing the large candidate catalog.

Saved designs include a non-combat ship-builder simulation reconstructed from
the packaged catalog. It reports crew; wet, dry, propellant, component, and
armor mass; cruise and combat acceleration; delta-v; angular acceleration;
power demand; waste heat; radiator mass; battery and heat-sink storage;
construction resources with component breakdowns; tier 1/2/3 shipyard build
times; MC; and monthly money upkeep. It intentionally excludes combat
performance ratings. Drive and weapon shortlist scores remain transparent
comparison proxies rather than a transfer or combat simulation.

The `nation-claims` command distinguishes peaceful, statically hostile, and democracy-conditional hostile claims. It reports the strict comparison `target.democracy > claimant.democracy + democracyDecreaseToMakeHostileClaim` with values and provenance. Permanence and post-annexation/unification/independence succession remain `unknown / not reconstructed` unless directly evidenced.

The `ai-fleet-diagnostics` command inspects supported attack/transport goals, assigned and pending fleets, ships, habs, shipyards, queues, resources, and mission-control evidence for one or all AI factions. It separates observed, derived, suspected, and unknown facts. An empty queue never implies a resource shortage, and stale suspicion is added only when `--stale-days` is supplied.

Module and location catalogs carry embedded canonical payload fingerprints. Runtime loaders reject altered payloads and duplicate module IDs; provenance timestamps are excluded from the fingerprint. Regenerate older custom catalogs with `tools/build_module_catalog.py` or `tools/build_location_catalog.py` before use. These standalone fingerprints are separate from the runtime bundle manifest.
