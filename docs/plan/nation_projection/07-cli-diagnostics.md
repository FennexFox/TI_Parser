# Phase 07: Runtime diagnostics and CLI contract hardening

## Goal

- Expose the actual preflight/runtime dependency graph, effective coverage, authoritative-state boundary, and provenance through the existing `nation-projection` JSON contract without weakening fail-closed behavior.

## Scope

- Preserve existing output keys and `authoritativeFinalState: null` for incomplete plans.
- Add `preflight.activePriorities`, `preflight.dormantPriorities`, `preflight.implicitFallbacks`, `metricCoverage`, `ruleExecutions`, `runtimeStop`, `lastAuthoritativeState`, `missingMechanicRules`, `missingDependencies`, `dependencyTrace`, and `affectedMetrics`.
- Calculate metric coverage from actual rule executions and dependencies, including effective coverage, provenance, rule IDs, blockers, and transitive mean-path propagation.
- Keep `--faction` limited to target-nation faction contribution and Advisor perspective; use the DLL executive/CP-owner faction context for nation effects.
- Preserve `inputProvenance: "hypotheticalPolicy"` for Advisor-affected results.
- Include BuildArmy placement fields and detailed completion/mutation events under `--details`.

## Non-goals

- Do not produce authoritative final state, comparison, or ranking for incomplete plans.
- Do not project whole-faction future totals.
- Do not reinterpret `--faction` as ownership of nation mechanics.
- Do not hide unsupported effects by applying zero or by downgrading an error to a limitation.

## Affected files

- `tools/ti_parser_nation_projection.py`
- `tools/ti_save_parser.py`
- `tests/test_nation_projection.py`
- `tests/test_nation_projection_cli.py`
- `tests/test_package_only_runtime.py`
- user-facing projection documentation

## Implementation steps

1. Separate raw-pip preflight findings into active priorities, dormant/invalid priorities, implicit Economy fallbacks, and hard blockers without changing the existing nonzero-unsupported contract.
2. Serialize committed rule executions with rule ID, implementation revision, static or conditional mode, resolver result, effective coverage, provenance, DLL symbols, source hashes, and actual dependencies.
3. Build per-metric coverage from the executed dependency graph and propagate the worst effective coverage, blockers, and provenance into dependent nation and faction-contribution metrics.
4. For Population-derived paths emit `coverage: "expected"`, `provenance: ["meanPath"]`, `stochasticTreatment: "deterministicMeanInput"`, and `expectationGuarantee: false`; never label them exact or imply a trajectory-expectation guarantee.
5. On runtime failure serialize the uncommitted rule/dependency trace separately, return the state before the failed transaction as `lastAuthoritativeState`, and keep final/comparison/ranking absent or null.
6. Expose MC mutation order and BuildArmy `homeRegionId`/`controlPointPosition` in detailed completion events.
7. Verify that nation effects use the save's executive/CP-owner faction context while `--faction` selects only faction contribution and Advisor lookup.
8. Retain stable existing top-level keys and package-only startup behavior for existing consumers.

## Acceptance criteria

- Complete plans retain authoritative output and incomplete plans retain null authoritative output plus a precise last-authoritative boundary.
- Preflight distinguishes active, dormant, fallback, and blocking paths while still failing on every raw nonzero unsupported pip.
- Runtime-discovered dependencies cannot be hidden by successful preflight.
- Every projected metric names its actual rules, coverage, provenance, and blockers.
- Population feedback has `meanPath` provenance and `expectationGuarantee: false` on all dependent metrics.
- `--faction` never changes Welfare or other nation effects except through explicitly planned Advisors and audited CP-owner modifiers.
- Existing key names and package-only runtime tests remain compatible.

## Validation commands

- py -3 -m unittest tests.test_nation_projection_cli tests.test_nation_projection
- py -3 -m unittest tests.test_package_only_runtime
- py -3 -m unittest discover -s tests -p 'test_*.py'

## Manual smoke tests

- Run a complete supported plan with `--details --diagnostics` and inspect metric rule IDs, effective coverage, source hash, conditional resolver result, and Advisor provenance.
- Trigger a runtime fallback into an unsupported priority and verify the failed transaction is absent from `lastAuthoritativeState` while its attempted dependency trace remains visible.
- Run the same nation plan with two `--faction` values and confirm nation state is unchanged while only contribution/Advisor perspective changes.
- Compare default CAL preflight output with an all-CP-replacement plan to confirm active and dormant priorities are visible independently from blockers.

## Rollback risks

- New diagnostics fields may encourage external dependencies; preserve names and types once released.
- Mixing attempted and committed rule executions would falsely lower or raise metric coverage. Keep runtime-stop traces explicitly separate.
- A partial rollback could restore authoritative output on an incomplete path; guard the invariant in CLI and core tests.

## Progress

- Completed: real-save extraction, preflight separation, rule executions, metric coverage, runtime-stop output, dependency traces, and authoritative-state contracts are integrated through the existing CLI.

## Decision log

- Metric coverage is computed from committed execution dependencies, not a static list of mechanics supported somewhere in the engine.
- `factionContribution.*` remains the selected faction's contribution from the target nation; observed whole-faction totals are context-only at the start.
- Unsupported paths are errors in authority, not zero-valued effects.

## Outcomes / Retrospective

- Existing output keys remain available while incomplete plans expose `runtimeStop`, `lastAuthoritativeState`, `missingMechanicRules`, `missingDependencies`, `dependencyTrace`, and `affectedMetrics`.
- Population-derived metrics distinguish compatibility coverage `expected` from `meanPath` provenance and explicitly emit `expectationGuarantee: false`; Advisor-driven results retain `hypotheticalPolicy`.
