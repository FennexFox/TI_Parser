# Phase 03: Verification and cleanup

## Goal

- Prove recurring timing numerically and remove the obsolete continuous-renewal limitation.

## Scope

- Focused/full tests, catalog verification, real-save smoke, plan validation, documentation, and Graphify refresh.

## Non-goals

- No unrelated projection mechanics.

## Affected files

- Tests, docs, plan, generated artifacts, and Graphify outputs touched by this extension.

## Implementation steps

1. Cover cadence transitions, mean resolution offsets, repeated downtime, segment changes, and cost totals.
2. Run focused and full suites plus package verification.
3. Run a local-save smoke and refresh Graphify.

## Acceptance criteria

- Tests pass and catalog hashes match installed inputs.
- Output no longer says travel/failure are ignored.
- No fictional 14-day travel constant or user-supplied success probability remains.

## Validation commands

- All commands in the master plan plus strict plan validation and Graphify diagnostics.

## Manual smoke tests

- Compare no-advisor, current-advisor, and newly-selected-advisor plans across two phases.

## Rollback risks

- Generated artifacts must roll back with generator and runtime code.

## Progress

- Completed.

## Decision log

- A live save opened during mission assignment is valid smoke input: current active Advise missions reveal the queued policy while `advisingCouncilors` is intentionally empty after phase bookkeeping.
- Whole-catalog verification currently reports unrelated research-template source-hash drift; the new nation-development catalog payload and every source hash, including mission/time templates and DLL, match the installed inputs.
- The mutable CAL observational matrix is not a strict regression gate. Its current unrelated Government/mean-path expectations drifted with the save, while the targeted live WES Advise lifecycle smoke passed.

## Outcomes / Retrospective

- Focused validation passed 70 tests; the complete suite passed 247 tests with 9 environment-dependent skips.
- The current live WES assignment resolved from an empty post-bookkeeping advisor state at `2125-04-02T09:51:00`; its already-paid order cost 0 future Influence, and the next saved-cadence renewal cost 10 Influence.
- `nation_development` package parity passed against the installed Broken Earth templates and current DLL. The broader verifier's sole failure was pre-existing research overlay source-hash drift outside this change.
- Plan validation passed for all three phases. Graphify refreshed to 2,308 nodes, 5,996 edges, and 139 communities; multigraph diagnostics found no malformed, missing-endpoint, dangling, self-loop, or duplicate edges.
- Search verification found no runtime 14-day travel constant, adjustable Advise success probability, or obsolete continuous-renewal user documentation.
