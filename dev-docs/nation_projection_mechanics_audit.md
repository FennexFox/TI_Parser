# Nation projection mechanics audit

This document indexes mechanics implemented by `nation-projection`; it does not duplicate
formulas. Python is the runtime behavior, while the registry connects it to DLL symbols,
catalog data, diagnostics, and tests.

## Audited builds

- Historical mechanics baseline: `Assembly-CSharp.dll`; SHA-256: `ff7916c2085ddbafa5acf1e8ea185d37e629096752be388ba6fa1f627f027bb5`.
- Runtime data: packaged `nation_development_catalog.json`, selected by the save's exact scenario and verified through `catalog_manifest.json`.
- The installed DLL and templates used for the audit/catalog are authoritative. A changed source hash requires a new audit before claiming parity with that build.

The packaged catalog baseline has been refreshed against DLL SHA-256
`4a4b9aae4154e444e9727204205d2d42ae8ed9e1c5f92cdc1280074a259d8350`.
This does not revalidate every historical mechanics rule. Each registry rule's
`sourceHash` identifies the actual reviewed build; unchanged historical rules
retain their old hash and are not certified for the refreshed build.

The current-build review covers `nation.priority.knowledge.complete` (revision
2), `nation.priority.welfare.complete`, `nation.priority.welfare.colony-trigger`
and `nation.priority.welfare.decolonization`. Knowledge uses
`TINationState.OnKnowledgePriorityComplete`, the education/cohesion change
properties, population scaling, `AddToEducation` and `AddToCohesion`.
`AddToEducation` clamps completion updates to `[1, 255]`; the former parser
lower bound of zero and missing upper bound were corrected. Initialization's
separate clamp is not evidence for completion behavior.

The Welfare coordinator calls inequality before colony selection.
`CandidateDecolonizeRegions`/`GetNextDecolonizeRegion` provide the deterministic
candidate path; `OnDecolonizeRegionPriorityComplete` handles threshold removal,
counter reset and permanent decolonization. The registry now cites these actual
symbols. Welfare inequality effects and decolonization downstream recalculation
retain their historical hashes because their full effect/call closure has not
been re-audited. The coordinator's current evidence does not certify its child
rules by inheritance.

The call-order claims below describe the historical reviewed build unless a
rule has explicit current-build evidence. See [catalogs](catalogs.md) for the
refreshed data baseline and [interoperability](fairplay_interoperability.md) for
separate structural, authority and visibility acceptance.

The subsequent bounded closure review found current-build mismatches and
unclosed dependencies in monthly live rest getters, diversity gating and
priority validity. No additional rules were rebound. See the [execution
findings](projection_execution_evidence.json) for scoped method comparisons and
[interoperability audit](fairplay_interoperability.md#bounded-execution-closure-and-current-build-findings)
for the blocked approval decision. Historical `verified` metadata below is not
current-build closure acceptance.

Verified call order includes monthly nation work at month-day 1 00:00, daily investment at
10:30, and the resting cohesion/unrest cache at 12:00. It also includes priority-enum
completion traversal; persistent Economy fallback when a CP has no valid weight; live priority
validity; Advisor conversion and rank decay; and recurring Advise lifecycle. Advise resolves
automatically and moves at assignment. Mission-phase bookkeeping clears its persistent effect
until the order-0 resolution segment reapplies it. Verified time conversions and compound
literals remain in Python rather than becoming undocumented domain constants.

Coverage follows the executed path. Static rules have one registry coverage; conditional rules
name a resolver and its closed set of outcomes. Each runtime execution records resolver,
effective coverage, inputs, outputs, provenance, and direct dependency rule IDs. An outcome
outside the declared set is an error, not an implicit downgrade.

## Rule index

| Rule ID | Audit | Coverage | Primary DLL symbol |
| --- | --- | --- | --- |
| `nation.ip.base` | verified | exact | `TINationState.SetBaseInvestmentPoints_month` |
| `nation.ip.economy-score` | verified | exact | `TINationState.ModifyGDP` |
| `nation.ip.control-point-allocation` | verified | exact | `TINationState.ControlPointWeightsTotalToPriorityIP` |
| `nation.ip.priority-bonus` | verified | exact | `TINationState.ControlPointPriorityBonuses_Uncached` |
| `nation.ip.control-point-default-economy` | verified | exact | `TIControlPoint.RecordAndFixControlPointValues` |
| `nation.priority.validity` | verified | exact | `TINationState.ValidPriority` |
| `nation.priority.completion-order` | verified | exact | `TINationState.ProcessPrioritySpending` |
| `nation.priority.knowledge.complete` | verified | exact | `TINationState.OnKnowledgePriorityComplete` |
| `nation.priority.government.complete` | verified | exact | `TINationState.OnGovernmentPriorityComplete` |
| `nation.priority.government.legitimize` | verified | exact | `TINationState.GetNextRegionToLegitimizeClaim` |
| `nation.priority.economy.complete` | verified | exact | `TINationState.OnEconomyPriorityComplete` |
| `nation.priority.economy.gdp` | verified | exact | `TINationState.economyPriorityPerCapitaGDPChange` |
| `nation.priority.economy.inequality` | verified | exact | `TINationState.economyPriorityInequalityChange` |
| `nation.priority.economy.market` | verified | conditional | `TIGlobalValuesState.ModifyMarketValuesForEconomyPriority` |
| `nation.priority.economy.region-trigger` | verified | exact | `TINationState.OnEconomyPriorityComplete` |
| `nation.priority.economy.region-transition` | verified | exact | `TIRegionState.SetCore*Region` |
| `nation.priority.economy.downstream-cache` | verified | exact | `TINationState.ModifyGDP` |
| `nation.priority.unity.complete` | verified | expected | `TINationState.OnUnityPriorityComplete` |
| `nation.priority.unity.public-opinion` | verified | conditional | `TINationState.PropagandaOnPop` |
| `nation.priority.unity.cohesion` | verified | exact | `TINationState.unityPriorityCohesionChange` |
| `nation.priority.unity.education` | verified | exact | `TINationState.unityPriorityEducationChange` |
| `nation.priority.unity.legitimize` | verified | exact | `TINationState.OnLegitimizeClaimPriorityComplete` |
| `nation.cohesion.public-opinion` | verified | exact | `TINationState.publicOpinionImpactOnCohesion` |
| `nation.priority.funding.complete` | verified | exact | `TINationState.OnFundingPriorityComplete` |
| `nation.priority.welfare.complete` | verified | exact | `TINationState.OnWelfarePriorityComplete` |
| `nation.priority.welfare.inequality` | verified | exact | `TINationState.welfarePriorityInequalityChange` |
| `nation.priority.welfare.colony-trigger` | verified | exact | `TINationState.GetNextDecolonizeRegion` |
| `nation.priority.welfare.decolonization` | verified | exact | `TINationState.OnDecolonizeRegionPriorityComplete` |
| `nation.priority.welfare.decolonization-downstream` | verified | exact | `TINationState.CacheRegionValues` |
| `nation.priority.mission-control.complete` | verified | conditional | `TINationState.OnMissionControlPriorityComplete` |
| `nation.priority.mission-control.placement` | verified | conditional | `TINationState.OnMissionControlPriorityComplete` |
| `nation.priority.build-army.complete` | verified | conditional | `TINationState.OnBuildArmyPriorityComplete` |
| `nation.priority.build-army.placement` | verified | conditional | `TINationState.GetNextArmyRegion` |
| `nation.priority.build-army.market` | verified | conditional | `TIGlobalValuesState.ModifyMarketValuesForArmyPriority` |
| `nation.priority.build-navy.complete` | verified | exact | `TINationState.GetNextNavy`, `TIArmyState.AddNavy` |
| `nation.priority.build-navy.market` | verified | conditional | `TIGlobalValuesState.ModifyMarketValuesForArmyPriority` |
| `nation.asset.army.maintenance` | verified | exact | `TINationState.SetBaseInvestmentPoints_month` |
| `nation.effect.context-expiration` | verified | exact | `TIFactionState.RemoveExpiredEffectContexts` |
| `nation.priority.validation-trigger` | verified | exact | `TINationState.PossiblePriorityValidationChange` |
| `nation.periodic.region-cache` | verified | exact | `TINationState.CacheRegionValues` |
| `nation.periodic.cohesion` | verified | exact | `TINationState.GetMonthlyCohesionMovement` |
| `nation.periodic.unrest` | verified | exact | `TINationState.GetMonthlyUnrestMovement` |
| `nation.periodic.derived-cache` | verified | exact | `TINationState.DailyNationUpdate2` |
| `nation.periodic.control-points` | partial | conditional | `TINationState.UpdateControlPoints` |
| `nation.periodic.population` | verified | expected | `TIRegionState.GrowPopulationByMonth` |
| `nation.population.annual-growth` | verified | exact | `TIRegionState.get_annualPopulationGrowth` |
| `nation.population.monthly-growth` | verified | expected | `TIRegionState.GrowPopulationByMonth` |
| `nation.advisor.attribute-source` | verified | exact | `TICouncilorState.AdvisingBonus` |
| `nation.advisor.stacking` | verified | exact | `TINationState.GetAdvisingScore` |
| `nation.advisor.mission-lifecycle` | verified | expected | `TIMissionPhaseState.StartofTurnBookkeeping` and `FinalizeCouncilorMissions.StaggerMissionResolutions` |
| `nation.faction-contribution` | verified | exact | `TINationState.GetMonthlyResearchFromControlPoint` and peer contribution methods |

Mission Control placement resolver `nation.priority.mission-control.placement.v1` returns
`exact` for one candidate, `aggregateOnly` for multiple candidates equivalent across all
future projected dependencies, and `unsupported` for distinguishable candidates before random
choice or mutation. BuildArmy resolver `nation.priority.build-army.placement.v1` is
deterministic and `exact` when fully resolved; missing region order, occupation, army home,
CP, or related input is `unsupported` before mutation. Monthly CP resolver
`nation.periodic.control-points.v1` is `exact` when count is unchanged and `unsupported`
before any add/remove.

`aggregateOnly` retains the national aggregate and all modeled downstream dependencies without
claiming placement identity. Population `expected` uses `meanPath`: uniform jitter is set to
zero on each update. It is a deterministic mean-input trajectory, not guaranteed to equal the mathematical expectation of stochastic trajectories after nonlinear
feedback; diagnostics say
`stochasticTreatment: "deterministicMeanInput"` and `expectationGuarantee: false`.

Unity public opinion resolver `nation.priority.unity.public-opinion.v1` requires a
materialized plan with explicit `meanPath` policy (`expected`); a possible Unity segment
without it is preflight `unsupported`. Unity applies the DLL integer-sample kernel's
conditional expected flow sequentially for each distinct CP owner. This is
`deterministicExpectedTransition`, not a complete-trajectory expectation under nonlinear
sequential feedback. Direct Unity cohesion, education, and legitimize outputs do not consume
propaganda and remain exact until an expected upstream input (such as population scaling)
reaches them.

Economy and BuildArmy market mutation use `world-market.mean-input.v1`: available Metals and
Noble Metals receive the audited uniform-input midpoint (`expected` / `meanPath` /
`deterministicMeanInput`). If only those values are missing, nation/faction mutation and
completion cost remain authoritative, only world-market scope is incomplete, and nation
ranking is not withheld. A later mechanic that reads a missing market value blocks at that
read.

## Metric dependency evidence

`MetricDependencyTracker` records each output against metrics actually read. Evidence includes
direct `dependsOn` edges, transitive rule IDs, provenance, blockers, and least-authoritative
path coverage (`exact < expected < aggregateOnly < unsupported`). Public coverage includes
per-capita GDP, cohesion/unrest rest caches, base IP, every asset count, research, each
priority's progress, and each target-nation faction contribution. Population-unaffected
metrics stay exact; completion timing dependent on mean-path allocation inherits
`expected/meanPath` as a control dependency. Every public mean-path row records deterministic
mean input and `expectationGuarantee: false`.

Rule execution coverage and metric coverage differ. Equivalent multi-candidate MC placement
can be `aggregateOnly` while national MC `+1` is exact because every candidate has the same
aggregate; mean-path completion timing can separately lower that metric to expected.

## Completion-specific boundaries

Welfare activates child rules only as needed. Inequality and colony-candidate handling do not
depend on decolonization. A threshold-reaching completion checks decolonization and all
downstream dependencies before mutation; a missing dependency rolls back only that incomplete
completion to its start boundary.

Mission Control's no-candidate path is exact: find no candidate; set each CP's raw MC pip to
zero (each setter immediately revalidates weights and may persist Economy fallback); then
deduct completion cost after the handler returns. The completion loop may repeat if progress
remains and live validity permits.

BuildArmy preserves selected home/current region, reverse-tie CP position, faction, strength,
and operations state. A new army does not alter the already-calculated daily base IP; its
scenario maintenance begins at the next base-IP update. Omitted UI naming/notifications do not
lower mechanic coverage.

Economy order is GDP and PCGDP, economy-score refresh, inequality and overshoot, independent
market branch, then cached Oil-before-Mining-before-Core region trigger. Selection uses live
candidates in nation-region order but does not fall through to another resource type after
same-day exhaustion. GDP validity is rechecked only at the audited trigger; daily region
counts stay cached until the next daily region-cache phase.

Unity resolves the Religion CP owner, then visits distinct owned factions in nation CP order.
Owned strength excludes disabled CPs but includes permanent allies; the separate Religion
bonus still applies if its CP is disabled. Opinion feeds the 12:00 cohesion-rest cache and
later monthly movement, not that completion's direct cohesion/education branch.

## Fail-closed completion rules

These completions/downstream rules remain non-authoritative:

- `nation.priority.environment.complete`
- `nation.priority.oppression.complete`
- `nation.priority.spoils.complete`
- `nation.priority.initiate-spaceflight.complete`
- `nation.priority.launch-facilities.complete`
- `nation.priority.found-military.complete`
- `nation.priority.military.complete`
- `nation.priority.initiate-nuclear-program.complete`
- `nation.priority.build-nuclear-weapons.complete`
- `nation.priority.build-space-defenses.complete`
- `nation.priority.build-sto-squadron.complete`
- `nation.periodic.control-points` when monthly reconciliation would mutate CP count

A raw nonzero pip for an unsupported completion blocks preflight even when dormant or invalid;
diagnostics distinguish active/dormant pips. Conditional or newly activated dependencies are
checked before use. CP revalidation/fallback, a successful handler plus cost consumption, and
a successful periodic phase are authoritative boundaries; only mutations since the last
verified boundary roll back. Thus a Government completion reaching the cap preserves its
effect, consumed cost, Economy raw pip 1, and repaired cache, allowing Economy to
allocate/complete on the next investment tick. Interrupted multi-completion records prior
successes as `authoritativePrefix` under `runtimeStop.attemptedTransaction`. Every blocker
nulls `authoritativeFinalState` and excludes the plan from comparison; unsupported effects are
never zero.

`runtimeStop` keeps `at`, `reason`, and `ruleIds`, and records timestamp, simulation day,
transaction kind, phase, trigger, last-authoritative transaction, authoritative mutations,
unsupported next step, state context, dependency descendants, and affected metrics.
Unsupported monthly CP-count paths report current, required, and unclamped counts plus
GDP/scaling inputs before mutation.

## Shared live priority validity

Projection and `nation-ui` share a value-only tri-state evaluator: unresolved inputs yield
`valid: null` with dependencies and stop projection before use; UI also preserves unknown. UI
reports every CP's raw/effective weights, serialized/recomputed total and count, consistency,
and unknown priorities. `_inactiveRawWeights` remains compatible but includes only positive
raw pips explicitly invalid under live validity; the former static-key grouping that
mislabeled active Government/MC pips is not used for UI results.

`Military_BuildNavy` is reconstructed from `TINationState.canBuildNavy` in the audited DLL: a military
nation needs a live non-naval army, a coastal region, and four CPs. The three-CP exception
requires PCGDP >= 40,000 and permits only the first navy. Coastal state comes from serialized
`TIRegionState.oceanType`; `Yes` and `Seasonal` match `TIRegionState.isCoastal`; missing/unsupported values
stay unknown in UI and fail closed during projection extraction.

BuildNavy follows `TINationState.GetNextNavy`, `TINationState.OnBuildSealiftPriorityComplete`, and
`TIArmyState.AddNavy`: count Human armies by CP, scan CPs descending for an unconverted army,
then select the first Standard Human army in saved order at that position. Conversion changes
deployment to Naval while preserving identity, strength, home/current region, faction, and CP.
Live naval/non-naval counts and later maintenance follow conversion. Naval armies remain
military assets for BuildArmy capacity, placement, and unrest suppression; public non-naval
count does not define those mechanics. Destroyed references are excluded from live selection.
Completion consumes cost and revalidates weights; its market mutation uses BuildArmy's
independent mean-input branch under `nation.priority.build-navy.market`, not exact RNG replay.
Movement, combat, accessibility graphs, and notifications are not simulated.

Mission Control accepts the nation's or federation's spaceflight program.
`TIFederationState.SetSpaceProgramValue` derives it from `members.Any(x => x.spaceFlightProgram)`; missing federation/member data is unknown unless a known program
satisfies the predicate. External member programs stay fixed during projection. Maximum navy
capacity is separate from current BuildNavy eligibility.

## User-facing transaction and metric semantics

One game investment update's allocations, completions, and immediate downstream effects form
one transaction. Monthly, daily 10:30 investment, daily 12:00 cache, and quarterly events run
in timestamp order; a checkpoint includes events no later than its elapsed-day boundary.
Conditions/goals run after that or a verified periodic transaction, and a newly satisfied
segment applies before the next investment transaction.

`nation.*` is national state; `factionContribution.*` is only the selected faction's
contribution from the target nation, not its faction-wide total. Advisor plans carry
`inputProvenance: "hypotheticalPolicy"`; an active/pending adviser policy under the
reconstructed lifecycle propagates `expectedMissionTiming` and `expected` coverage through
base IP, research, and consuming allocations. Schedules without adviser policy do not lower
coverage. Actionable Advise has 100% success; `MoveToTarget` moves at assignment (zero travel
time). Mission-phase bookkeeping clears active effects and renews at neutral mean order-0
stagger time; renewal Influence is reported. Future affordability, target validity, detention,
and competing orders are outside replay. Other nations, wars, missions, events, ownership
changes, and player actions are held fixed.

## Validation boundary

One-tick expected-value fixtures keyed by registry IDs are primary regression evidence.
Registry links classify tests as `expectedValue`, `stateTransition`, `ordering`,
`coverageBranch`, or `contract`; supported rules need direct non-contract evidence. Save
A-to-B comparison is strict only when B advances A by controlled updates without other
actions/events. Ordinary campaign endpoints are observational only; matching tolerances do not
prove intervening policy was unchanged. Derive metric tolerances from DLL numeric types,
serialization precision, cadence, and controlled pairs rather than fixing them in advance.
