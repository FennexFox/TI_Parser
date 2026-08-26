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

The audit confirmed the daily investment call path, monthly nation boundary,
priority enum completion traversal, CP weight allocation, priority bonuses,
Advisor attribute conversion and rank decay, and the implemented completion
handlers. The verified time-conversion literal is retained in Python rather
than treated as an undocumented domain constant.

## Rule index

| Rule ID | Audit | Coverage | Primary DLL symbol |
| --- | --- | --- | --- |
| `nation.ip.base` | verified | exact | `TINationState.SetBaseInvestmentPoints_month` |
| `nation.ip.control-point-allocation` | verified | exact | `TINationState.ControlPointWeightsTotalToPriorityIP` |
| `nation.ip.priority-bonus` | verified | exact | `TINationState.ControlPointPriorityBonuses_Uncached` |
| `nation.priority.completion-order` | verified | exact | `TINationState.ProcessPrioritySpending` |
| `nation.priority.knowledge.complete` | verified | exact | `TINationState.OnKnowledgePriorityComplete` |
| `nation.priority.government.complete` | verified | aggregateOnly | `TINationState.OnGovernmentPriorityComplete` |
| `nation.priority.unity.complete` | verified | aggregateOnly | `TINationState.OnUnityPriorityComplete` |
| `nation.priority.funding.complete` | verified | exact | `TINationState.OnFundingPriorityComplete` |
| `nation.periodic.cohesion` | verified | exact | `TINationState.GetMonthlyCohesionMovement` |
| `nation.periodic.unrest` | verified | exact | `TINationState.GetMonthlyUnrestMovement` |
| `nation.periodic.population` | verified | expected | `TIRegionState.GrowPopulationByMonth` |
| `nation.advisor.attribute-source` | verified | exact | `TICouncilorState.AdvisingBonus` |
| `nation.advisor.stacking` | verified | exact | `TINationState.GetAdvisingScore` |
| `nation.faction-contribution` | verified | exact | `TINationState.GetMonthlyResearchFromControlPoint` and peer contribution methods |

`aggregateOnly` means the projected national aggregate and its downstream
dependencies are retained, while omitted spatial or public-opinion detail is
not claimed to be replayed. `expected` means random draws are replaced by the
audited expected-value path and are labeled accordingly.

## Fail-closed completion rules

The following rule IDs are registered so code, diagnostics, tests, and audit
work use one stable vocabulary, but their completion/downstream mechanics are
not yet authoritative:

- `nation.priority.economy.complete`
- `nation.priority.welfare.complete`
- `nation.priority.environment.complete`
- `nation.priority.oppression.complete`
- `nation.priority.spoils.complete`
- `nation.priority.initiate-spaceflight.complete`
- `nation.priority.launch-facilities.complete`
- `nation.priority.mission-control.complete`
- `nation.priority.found-military.complete`
- `nation.priority.military.complete`
- `nation.priority.build-army.complete`
- `nation.priority.build-navy.complete`
- `nation.priority.initiate-nuclear-program.complete`
- `nation.priority.build-nuclear-weapons.complete`
- `nation.priority.build-space-defenses.complete`
- `nation.priority.build-sto-squadron.complete`

A nonzero pip for any of these priorities makes the plan `incomplete`. The
result reports `missingMechanicRules`, retains current allocation and coverage
diagnostics, sets `authoritativeFinalState` to null, and excludes the plan from
comparison. Unsupported effects are never silently treated as zero.

## User-facing transaction and metric semantics

- All allocations, completions, and immediate downstream effects in one game
  investment update form one transaction.
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
