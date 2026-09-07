# Phase 11: Shared priority validity and independent verification

## Goal

- Make projection and nation UI use the same value-based priority-validity contract and require direct mechanic evidence for supported registry rules.

## Scope

- Add `PriorityValidityResult` and a pure evaluator in a shared module.
- Replace projection-local validity decisions and static nation-UI inactive grouping with the shared result.
- Report every CP's raw/effective pips, validity, recomputed weights, serialized totals, and consistency.
- Add registry evidence kinds and reject contract-only support claims.
- Add independent literal/state-transition fixtures and full same-date scheduler phase ordering.

## Non-goals

- Do not infer missing validity inputs as false.
- Do not change existing nation-UI row or `_inactiveRawWeights` keys.

## Affected files

- `tools/ti_parser_nation_validity.py`
- `tools/ti_parser_nation_projection.py`
- `tools/ti_save_parser.py`
- `tools/ti_parser_mechanics.py`
- `tests/test_nation_projection.py`
- `tests/test_mechanics_registry.py`
- nation-UI tests

## Implementation steps

1. Define a minimal value-only validity view and return valid/invalid/unknown with reason and dependency paths.
2. Delegate projection validity to the evaluator; convert unknown to a structured projection stop before use.
3. Build a nation-UI view for every CP and emit dynamic inactive raw pips plus `validityByPriority` and CP weight consistency diagnostics.
4. Extend `@mechanic_rule_test` with `expectedValue`, `stateTransition`, `ordering`, `coverageBranch`, and `contract` evidence.
5. Require every supported rule to link at least one direct non-contract test; replace generic registry-only links.
6. Add literal one-tick fixtures and a same-date phase trace through monthly, quarterly, investment, noon-cache, condition, and checkpoint observation points.

## Acceptance criteria

- Active CAL Mission Control pips included in serialized total are not reported as inactive.
- Truly invalid program/asset pips remain in `_inactiveRawWeights` and missing dependencies produce `valid: null`.
- All supported rules have a direct non-contract evidence test declaring the same rule ID.
- Ordering tests prove state produced by each phase is read by the following phase.

## Validation commands

- py -3 -m unittest tests.test_mechanics_registry tests.test_nation_projection
- py -3 -m unittest discover -s tests -p 'test_*.py'

## Manual smoke tests

- Inspect CAL nation-ui all-CP validity and serialized/effective weight consistency.
- Run a same-day details projection spanning monthly, investment, noon-cache, and checkpoint events.

## Rollback risks

- Nation UI has less dependency context than projection; unknown must remain visible rather than silently changing weight semantics.
- Test metadata migration can temporarily expose supported rules with only historical contract coverage.

## Progress

- Completed: shared tri-state validity, all-CP nation-UI diagnostics, typed registry evidence, independent mechanic fixtures, and same-timestamp scheduler traces are implemented and verified.

## Decision log

- UI grouping, raw pip presence, validity, and allocation participation are separate reported concepts.

## Outcomes / Retrospective

- Added a value-only `PriorityValidityResult` evaluator shared by projection and nation UI. Projection converts unknown to a structured stop; nation UI preserves `valid: null` and dependency details.
- Nation UI now emits `validityByPriority` and every CP's raw/effective weights, serialized/recomputed totals and counts, consistency, and unknown priority list. `_inactiveRawWeights` contains only live-invalid positive pips.
- The opt-in CAL save reports Mission Control as live-valid, includes its raw
  pips in every CP's recomputed effective total, and matches each serialized
  cache; only actually invalid positive raw pips remain inactive. No current
  save count, pip value, or serialized total is a committed fixture.
- Registry test metadata now requires one of `expectedValue`, `stateTransition`, `ordering`, `coverageBranch`, or `contract`; supported rules fail validation unless at least one linked test is direct and non-contract.
- Literal fixtures now cover exact Knowledge/Government/rest-cache/economy-score deltas, monthly Population/GDP compound and floor, MC branches/order, BuildArmy selection and maintenance, and CP fallback state.
- `--details` now exposes transaction-local and flattened phase traces. A single timestamp fixture proves monthly movement, region-order population/GDP, quarterly tracking, condition evaluation, investment/segment application, noon rest cache, rest condition, and checkpoint capture order and state transfer.
- Validation at the phase boundary: focused registry/validity/projection and
  nation-UI tests, the full suite, and the opt-in local-save observational smoke
  suite passed. Phase 12 records the final aggregate counts.
