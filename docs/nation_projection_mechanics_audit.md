# Nation projection mechanics audit

This document indexes the mechanics implemented by `nation-projection`. It does
not contain an executable copy of any formula. The Python implementation is the
runtime behavior; the registry connects that implementation to DLL symbols,
catalog data, diagnostics, and tests.

## Audited build

- Assembly: `Assembly-CSharp.dll`
- SHA-256: `5ec67c601a6ce39d985aa9830a99faa9844aee7d7e12ec5e28ea46ff020ba982`
- Runtime data: packaged `nation_development_catalog.json`, selected by the
  save's exact scenario and verified through `catalog_manifest.json`
- Source of truth: the installed DLL and templates used during the audit and
  catalog generation. A changed source hash requires a new audit before the
  projection can claim parity with that build.

The audit confirmed the event boundaries and call order used by the projection:
monthly nation work at month-day 1 00:00, daily investment at 10:30, and the
resting cohesion/unrest cache at 12:00. It also confirmed priority enum
completion traversal, persistent Economy fallback when a CP has no valid
weight, live priority validity, Advisor conversion and rank decay, and the
completion handlers listed below. Verified time-conversion and compound
literals remain in Python rather than being treated as undocumented domain
constants.

Coverage is attached to an executed path, not only to a mechanic name. Static
rules have one registry coverage. Conditional rules name a registered resolver
and enumerate every result it may return. A runtime rule execution records the
resolver, effective coverage, provenance, and dependency rule IDs. An outcome
outside that closed set is an error rather than an implicit downgrade.

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
| `nation.priority.unity.complete` | partial | unsupported | `TINationState.OnUnityPriorityComplete` |
| `nation.priority.funding.complete` | verified | exact | `TINationState.OnFundingPriorityComplete` |
| `nation.priority.welfare.complete` | verified | exact | `TINationState.OnWelfarePriorityComplete` |
| `nation.priority.welfare.inequality` | verified | exact | `TINationState.welfarePriorityInequalityChange` |
| `nation.priority.welfare.colony-trigger` | verified | exact | `TINationState.GetNextRegionToDecolonize` |
| `nation.priority.welfare.decolonization` | verified | exact | `TIRegionState.SetColonialStatus` |
| `nation.priority.welfare.decolonization-downstream` | verified | exact | `TINationState.CacheRegionValues` |
| `nation.priority.mission-control.complete` | verified | conditional | `TINationState.OnMissionControlPriorityComplete` |
| `nation.priority.mission-control.placement` | verified | conditional | `TINationState.OnMissionControlPriorityComplete` |
| `nation.priority.build-army.complete` | verified | conditional | `TINationState.OnBuildArmyPriorityComplete` |
| `nation.priority.build-army.placement` | verified | conditional | `TINationState.GetNextArmyRegion` |
| `nation.asset.army.maintenance` | verified | exact | `TINationState.SetBaseInvestmentPoints_month` |
| `nation.periodic.cohesion` | verified | exact | `TINationState.GetMonthlyCohesionMovement` |
| `nation.periodic.unrest` | verified | exact | `TINationState.GetMonthlyUnrestMovement` |
| `nation.periodic.derived-cache` | verified | exact | `TINationState.DailyNationUpdate2` |
| `nation.periodic.control-points` | partial | conditional | `TINationState.UpdateControlPoints` |
| `nation.periodic.population` | verified | expected | `TIRegionState.GrowPopulationByMonth` |
| `nation.population.annual-growth` | verified | exact | `TIRegionState.get_annualPopulationGrowth` |
| `nation.population.monthly-growth` | verified | expected | `TIRegionState.GrowPopulationByMonth` |
| `nation.advisor.attribute-source` | verified | exact | `TICouncilorState.AdvisingBonus` |
| `nation.advisor.stacking` | verified | exact | `TINationState.GetAdvisingScore` |
| `nation.faction-contribution` | verified | exact | `TINationState.GetMonthlyResearchFromControlPoint` and peer contribution methods |

Mission Control placement uses resolver
`nation.priority.mission-control.placement.v1`: one candidate is `exact`,
multiple candidates that are equivalent for all future projected dependencies
are `aggregateOnly`, and distinguishable candidates are `unsupported` before a
random choice or mutation. BuildArmy uses
`nation.priority.build-army.placement.v1`: its audited selection is
deterministic, so a fully resolved execution is `exact`; a missing region-order,
occupation, army-home, CP, or related input is `unsupported` before mutation.
Monthly CP reconciliation uses resolver
`nation.periodic.control-points.v1`: an unchanged CP count is `exact`; a path
that would add or remove a CP is `unsupported` before mutation in this version.

`aggregateOnly` means the national aggregate and every modeled downstream
dependency are retained while placement identity is not claimed. Population
`expected` coverage has the narrower `meanPath` provenance: the uniform jitter
input is replaced by zero at each update. This is a deterministic mean-input
trajectory and is not guaranteed to equal the mathematical expectation of all
stochastic trajectories after nonlinear feedback. Diagnostics therefore also
record `stochasticTreatment: "deterministicMeanInput"` and
`expectationGuarantee: false`.

## Completion-specific boundaries

Welfare activates child rules only as the executed path needs them. Inequality
and colony-candidate handling do not depend on reaching decolonization. A
completion that would reach the threshold checks both decolonization and every
downstream dependency before mutation; a missing dependency rolls back only
that transaction. This keeps ordinary Welfare paths authoritative without
silently approximating the distant state transition.

Mission Control's no-candidate path is an audited exact mutation order: the
handler finds no candidate, sets each CP's raw MC pip to zero, each setter
immediately revalidates weights and may persist the Economy fallback, and only
after the handler returns is completion cost deducted. The completion loop may
then repeat if remaining progress and live validity permit it.

BuildArmy preserves the selected home/current region, reverse-tie CP position,
faction, strength, and operations state. The new army does not retroactively
alter the already calculated daily base IP; its scenario maintenance starts at
the next base-IP update. Omitted UI naming and notifications do not reduce
mechanic coverage.

## Fail-closed completion rules

The following completion/downstream rules remain non-authoritative:

- `nation.priority.economy.complete`
- `nation.priority.environment.complete`
- `nation.priority.unity.complete`
- `nation.priority.oppression.complete`
- `nation.priority.spoils.complete`
- `nation.priority.initiate-spaceflight.complete`
- `nation.priority.launch-facilities.complete`
- `nation.priority.found-military.complete`
- `nation.priority.military.complete`
- `nation.priority.build-navy.complete`
- `nation.priority.initiate-nuclear-program.complete`
- `nation.priority.build-nuclear-weapons.complete`
- `nation.priority.build-space-defenses.complete`
- `nation.priority.build-sto-squadron.complete`
- `nation.periodic.control-points` when monthly reconciliation would mutate CP
  count

A raw nonzero pip for an unsupported completion remains a preflight blocker,
even if it is currently dormant or invalid; diagnostics separate active and
dormant pips. Conditional or newly activated dependencies are checked again
before use. A blocker rolls back the cloned transaction, retains
`lastAuthoritativeState`, reports the dependency trace, sets
`authoritativeFinalState` to null, and excludes the plan from comparison.
Unsupported effects are never silently treated as zero.

## User-facing transaction and metric semantics

- All allocations, completions, and immediate downstream effects in one game
  investment update form one transaction.
- Monthly, daily 10:30 investment, daily 12:00 cache, and quarterly events run
  in timestamp order. A checkpoint includes every event no later than its
  elapsed-day boundary.
- Conditions and goals are evaluated only after that transaction or a verified
  periodic transaction. A newly satisfied segment is applied immediately
  before the next investment transaction.
- `nation.*` is national state. `factionContribution.*` is only the selected
  faction's contribution from the target nation, never the faction-wide total.
- Advisor plans carry `inputProvenance: "hypotheticalPolicy"`: travel, mission
  failure, opportunity cost, and renewal gaps are outside the replay model.
- Other nations, wars, missions, events, ownership changes, and player actions
  are held fixed.

## Validation boundary

One-tick expected-value fixtures keyed by the same registry IDs are the primary
regression evidence. A save A to save B comparison is strict only when B was
created by advancing A through a controlled number of updates with no other
actions or external events. Ordinary campaign endpoints are observational
validation only; matching tolerances do not prove the intervening policy was
unchanged. Metric tolerances must be derived from the DLL numeric types,
serialization precision, cadence, and controlled pairs rather than fixed in
advance.
