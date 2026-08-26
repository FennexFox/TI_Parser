# Phase 08: Independent fixtures, real-save validation, and Graphify refresh

## Goal

- Prove the hardened mechanics with independent one-tick fixtures, opt-in local-save smoke coverage, full regressions, package-only verification, and an updated Graphify knowledge graph.

## Scope

- Add expected-value fixtures that do not reuse production constants or formula helpers.
- Verify rule assertion metadata, coverage resolvers, transaction rollback, event order, priority branches, maintenance propagation, and metric provenance.
- Add opt-in real-save smoke tests selected only through `TI_PARSER_REAL_SAVE`.
- Exercise CAL using full CP replacement for supported plans while separately reporting the default raw-pip blockers.
- Preserve existing nation UI, catalog parity, package-only, `IndexedState` immutability, plan isolation, faction contribution, and Advisor provenance regressions.
- Refresh and validate Graphify only after code, tests, and documentation stabilize.

## Non-goals

- Do not commit a full save, extracted current values, object IDs, or the user's absolute save path.
- Do not call an uncontrolled existing campaign A-to-B comparison strict validation.
- Do not tune fixed real-save tolerances before verifying numeric types, serialization precision, cadence, and controlled-pair behavior.
- Do not expand into an optimizer or unsupported priority implementation.

## Affected files

- `tests/test_nation_projection.py`
- `tests/test_nation_projection_cli.py`
- `tests/test_nation_projection_real_save.py`
- `tests/test_mechanics_registry.py`
- `tests/test_catalog_generators.py`
- `tests/test_runtime_catalogs.py`
- `tests/test_package_only_runtime.py`
- projection/audit user documentation
- `graphify-out/`

## Implementation steps

1. Add literal, independent fixtures for CP allocation, float/double boundaries, Government's three paths, persistent invalid-only Economy fallback, runtime rollback, Population annual/monthly/floor behavior, daily/monthly/quarterly order, Welfare child dependencies, MC candidate cases and mutation order, deterministic BuildArmy selection/next-tick maintenance, exact Knowledge/Government deltas, and metric dependency propagation.
2. Assert that every supported registry rule is covered by a test declaring the same rule ID in assertion metadata, and that every conditional resolver returns only registered closed outcomes.
3. Test `meanPath` propagation through Population, GDP, PCGDP, research, cohesion-rest, and contribution results. Assert that no nonlinear dependent metric claims mathematical expectation equivalence.
4. Add opt-in `TI_PARSER_REAL_SAVE` discovery with a skip when unset; never derive an installation or save path in production code.
5. Against CAL, inspect current active/dormant/default blockers, then run all-CP replacement scenarios for Knowledge-only; Government/Knowledge/mixed checkpoints; relative-democracy Government-to-Knowledge switching; Knowledge/Welfare; Government-to-Knowledge/Welfare; MC/Knowledge; Army/Knowledge; and a one-year Population/monthly/quarterly/condition path.
6. Derive CAL's current MC and Army candidates from extracted state and the audited selection order, then assert the execution selects that result and applies the scenario's packaged home-maintenance value on the next daily investment. Do not freeze a region name, CP position, or maintenance number from one mutable save snapshot.
7. Run the entire suite plus package-only and scenario-parity checks; document any external installed-source drift separately from repository failures.
8. Read the Graphify update procedure, update the graph from the finished working tree, verify graph status, and query the new runtime dependencies and output contract.
9. Update progress, decision logs, and outcomes with exact automated and manual validation results.

## Acceptance criteria

- All new expected values are independent of production calculation helpers and constants.
- Registry CI validates actual assertion metadata, not only test-name presence.
- Transaction rollback and MC intermediate mutation order have exact regression coverage.
- BuildArmy deterministic selection and next-tick maintenance are exact fixtures.
- Opt-in real-save tests skip cleanly without an environment variable and pass with the local Broken Earth CAL save.
- Existing regressions remain green and runtime never reads installed game files.
- Strict controlled-pair validation and observational campaign comparison remain explicitly distinct.
- `graphify-out` is regenerated after implementation and queries expose the new mechanics, dependencies, and diagnostics.

## Validation commands

- py -3 -m unittest tests.test_nation_projection tests.test_nation_projection_cli tests.test_mechanics_registry
- py -3 -m unittest tests.test_catalog_generators tests.test_runtime_catalogs tests.test_package_only_runtime
- py -3 -m unittest tests.test_nation_projection_real_save
- $env:TI_PARSER_REAL_SAVE = 'C:\Users\techn\OneDrive\문서\My Games\TerraInvicta\Saves\ExitSave.gz'; py -3 -m unittest tests.test_nation_projection_real_save; Remove-Item Env:TI_PARSER_REAL_SAVE
- py -3 -m unittest discover -s tests -p 'test_*.py'
- graphify update
- graphify diagnose multigraph --graph graphify-out/graph.json --json
- graphify query "nation projection population government welfare mission control build army runtime stop metric coverage"

## Manual smoke tests

- Run the documented `nation-projection CAL` examples with supported all-CP replacement plans and inspect checkpoints, segment changes, placements, mean-path provenance, and authoritative final state.
- Run the same command with CAL's current raw pips and confirm unsupported Economy/Unity-dependent paths remain explicit and non-authoritative rather than silently ignored.
- If a controlled A-to-B save pair is available, compare one known update at a time; otherwise record the real-save runs as smoke/observational validation only.
- Inspect Graphify's query result and confirm it links the scheduler, rule registry, catalog, state extraction, completion handlers, diagnostics, and tests.

## Rollback risks

- Real-save assertions can become brittle across game builds; limit them to structural/runtime invariants and record source hashes rather than hardcoding current save values.
- Graph generation can touch many tracked artifacts; run it only after implementation and revert the graph as a unit if its validation fails.
- A broad tolerance can hide mechanics errors and a narrow tolerance can encode serialization noise; controlled one-tick fixtures remain the authoritative regression evidence.

## Progress

- Completed: independent fixtures, full regression, opt-in local-save smoke, phased-plan validation, and Graphify refresh all pass.

## Decision log

- Real `ExitSave.gz` coverage is opt-in smoke evidence, not a committed fixture or strict uncontrolled endpoint regression.
- A strict comparison requires a deliberately controlled A-to-B pair with no actions or exogenous events between endpoints.
- Graphify is refreshed once after implementation, because the existing graph was current at commit `117d4b3` before this extension.

## Outcomes / Retrospective

- Current automated regression: `214 passed, 6 skipped, 10 subtests passed`.
- Opt-in local `ExitSave.gz` smoke: 5 tests passed, including full-CP Knowledge replacement, conditional Government/Welfare paths, MC/BuildArmy execution, and long-horizon monthly/quarterly Population handling. This is smoke/observational evidence, not a controlled strict A-to-B pair.
- No local save path, object ID, or current numeric state is encoded in production code or committed fixtures.
- Graphify was rebuilt from the completed tree: 2,021 nodes, 5,941 edges, 109 communities. The focused query reaches the scheduler, runtime stop, registry, completion handlers, metric coverage, extraction layer, and tests; multigraph diagnostics report no dangling, duplicate, collapsed, or self-loop edges.
