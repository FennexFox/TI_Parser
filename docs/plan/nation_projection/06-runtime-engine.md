# Phase 06: DLL-boundary runtime engine and priority mechanics

## Goal

- Replace approximate projection timing and static preflight assumptions with clone-and-commit DLL-boundary transactions that implement the approved Population, Government, Welfare, Mission Control, and BuildArmy paths and fail closed on runtime dependencies.

## Scope

- Schedule monthly nation work at day 1 00:00, daily investment at 10:30, daily resting-cache work at 12:00, and PCGDP tracking at verified quarterly boundaries.
- Define checkpoint day N as the state after every event within N days from the start timestamp completes.
- Recompute economy score, PCGDP, priority scaling, base IP, maintenance, regional/federation/resource bonus, priority validity, fallback pips, and resting caches at their verified mutation boundaries.
- Run transactions on cloned state and commit only after all runtime dependencies resolve; otherwise discard all mutations and retain `lastAuthoritativeState`.
- Implement Population annual/monthly formulas and ordered-region feedback with deterministic mean-input stochastic handling.
- Implement Government cap validity and legitimize claim behavior, Welfare child dependencies, Mission Control per-instance placement and no-candidate mutation order, and deterministic BuildArmy placement/next-tick maintenance.
- Revalidate raw pips, weight, diversity, validity, and newly activated dependencies after policy or completion changes.

## Non-goals

- Do not implement Economy completion, global market mutation, environmental feedback, or region transformation.
- Do not implement Unity public-opinion side effects or claim its dependent resting metrics are authoritative.
- Do not mutate control-point count during monthly `UpdateControlPoints`; fail closed before such a change.
- Do not replay missions, external events, notifications, UI names, or whole-faction future totals.

## Affected files

- `tools/ti_parser_nation_projection.py`
- `tools/ti_parser_mechanics.py`
- `tests/test_nation_projection.py`
- `tests/test_mechanics_registry.py`

## Implementation steps

1. Introduce a chronologically ordered event scheduler from the save timestamp and make policy transitions apply immediately before the next 10:30 investment transaction.
2. Clone the complete state for each event, collect dependencies and rule executions, and commit only when all dependencies resolve; otherwise populate runtime-stop information from the pre-transaction state.
3. Recompute derived values at the verified DLL boundaries, including immediate economy score after GDP changes, PCGDP/scaling after population changes, daily IP/maintenance/bonuses, noon resting caches, and live checkpoint/condition contribution values.
4. Implement Population using the audited annual formula, clamp, monthly compound literal, floor, and nation-region iteration order. At each update replace the stochastic term by its expected input `0` and propagate the result to every dependent metric.
5. Record the exact Population semantics: `stochasticTreatment: "deterministicMeanInput"`, `provenance: "meanPath"`, `coverage: "expected"`, and `expectationGuarantee: false`. This is a deterministic mean-input trajectory and, because of nonlinear feedback, is not guaranteed to equal the mathematical expectation over complete stochastic trajectories.
6. Implement Government below-cap delta, at-cap invalid fallback, and at-cap hostile-region Knowledge plus deterministic legitimize counter/claim removal, with next-cache resting-state propagation.
7. Execute Welfare inequality and colony trigger independently. Add decolonization and downstream dependencies only for the completion that reaches 1000; resolve every required state change before committing or roll the whole completion back.
8. Resolve Mission Control execution coverage from candidates: one candidate is exact, equivalent multiple candidates are aggregate-only, differing future dependencies are unsupported before placement. Implement and trace the no-candidate order exactly: guard progress/validity; evaluate candidates; set no asset; set every CP raw MC pip to zero; immediately validate each CP and create persistent Economy fallback if needed; return; deduct cost; repeat while allowed; then perform final validation.
9. Reproduce BuildArmy's deterministic core-economic filter, population maximum, stable region-list tie, and reverse CP tie. When all inputs resolve, mark the execution exact, record home/current region and CP, and apply home maintenance only to the next daily base-IP calculation.
10. Preserve the existing raw-nonzero unsupported preflight rule, distinguish active/dormant priorities, and check newly activated or fallback dependencies immediately before use.

## Acceptance criteria

- Monthly, daily investment, noon cache, quarterly tracker, checkpoints, and conditions execute in verified chronological order.
- No incomplete transaction leaks GDP, pips, progress, assets, claims, counters, caches, or contributions into authoritative state.
- Population output and all transitively dependent metrics carry mean-path provenance and explicitly deny an expectation guarantee.
- Government, Welfare, Mission Control, and BuildArmy match the audited branches and dependency timing.
- The MC no-candidate test proves asset, progress, pips, fallback, cache, and trace mutation order.
- A fully resolved BuildArmy execution is exact even with multiple candidates; missing selection input stops before mutation.
- Monthly CP-count mutation and any newly required unsupported rule fail closed.

## Validation commands

- py -3 -m unittest tests.test_nation_projection
- py -3 -m unittest tests.test_mechanics_registry
- py -3 -m unittest discover -s tests -p 'test_*.py'

## Manual smoke tests

- Start just before each monthly, 10:30, 12:00, and quarterly boundary and inspect event/rule order and checkpoint inclusion.
- Run a Government-at-cap fixture with and without a hostile region, then verify persistent Economy fallback and deterministic claim removal.
- Run Welfare at counters 998 and 999 to show the decolonization dependencies are absent on the former and checked atomically on the latter.
- Run MC with one candidate, equivalent multiple candidates, divergent multiple candidates, and no candidate; inspect the detailed mutation trace.
- Complete BuildArmy and compare base IP on the completion day and the next investment tick.

## Rollback risks

- Event ordering changes every long-horizon result; retain one-boundary fixtures so rollback cannot accidentally restore approximate daily order.
- Mean-path provenance must be transitive. Rolling back only diagnostics would make expected results appear exact.
- Persistent pip fallback and while-loop semantics can alter later completions in the same traversal; tests must keep intermediate mutation order visible.
- Clone depth omissions could leak state on failure; transaction tests must compare every mutable nested object before and after rollback.

## Progress

- Completed: DLL-boundary scheduler, clone-and-commit transactions, Population mean-input path, Government, Welfare, Mission Control, BuildArmy, cache refresh, and runtime fail-closed handling are implemented.

## Decision log

- Player policy is observed between investment transactions, never between priority completions inside one transaction.
- Population uses deterministic mean input, not a Monte Carlo estimate and not a claim about the nonlinear stochastic trajectory's expected value.
- Welfare coverage is decomposed into child rules so an unreachable decolonization edge does not invalidate ordinary inequality projection.
- BuildArmy coverage is execution-specific and exact whenever its deterministic input set is complete.

## Outcomes / Retrospective

- One-tick fixtures cover MC's no-candidate mutation order, non-equivalent candidate rollback, deterministic BuildArmy selection, next-tick maintenance, Welfare dependency rollback, monthly CP-count rollback, and nonlinear Population provenance.
- Runtime rule executions are checked against the registry before commit. An unsupported branch reports the exact event timestamp and preserves the last authoritative state.
