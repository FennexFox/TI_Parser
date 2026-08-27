# Phase 17: Unity public opinion and direct effects

## Goal

- Implement Unity's exact direct branches and explicit-opt-in sequential conditional-expected public-opinion trajectory.

## Scope

- Religion owner, distinct CP-owner propaganda order, active ideology space, expected transfer kernel, cohesion/education, legitimize, and downstream resting-state evidence.

## Non-goals

- Do not replay the global RNG stream or claim full stochastic expectation.
- Do not add public-opinion goal/condition metrics.

## Affected files

- projection engine, policy validation, snapshots/output, and Unity fixtures

## Implementation steps

1. Reproduce DLL completion order: Religion owner, sequential distinct CP owners, cohesion, education, legitimize.
2. Construct active human ideologies plus Undecided in template sort order and handle disabled CP, allies, Religion, alien/proxy semantics.
3. For each source call, form the integer-sample transition kernel from current opinion, apply its conditional expected flow, normalize, and pass it to the next source call.
4. Emit `expected/meanPath/deterministicExpectedTransition/expectationGuarantee:false` for opinion and only its real descendants.
5. Keep direct cohesion/education/legitimize exact unless their own upstream scaling evidence is expected.

## Acceptance criteria

- Unity without whole-plan opt-in fails preflight; opted-in plans do not fail unexpectedly on later segments.
- Public opinion affects noon cohesion-rest and later monthly movement, not direct same-completion formulas.
- Diagnostics visibly distinguish Unity's transition approximation from Population's mean-input approximation.

## Validation commands

- `py -3 -m pytest -q tests/test_nation_projection.py tests/test_nation_projection_cli.py`
- registry evidence validation

## Manual smoke tests

- Run opted-in Unity-only and conditional Unity plans against the local CAL save and inspect sequential owner executions and coverage.

## Rollback risks

- Sequential expected transitions are nonlinear; do not merge source calls or label the result as exact/full expectation.

## Progress

- Pending.

## Decision log

- `meanPath` is retained as shared provenance while `stochasticTreatment` identifies the distinct approximation.

## Outcomes / Retrospective

- Pending.
