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

- Completed.

## Decision log

- `meanPath` is retained as shared provenance while `stochasticTreatment` identifies the distinct approximation.

## Outcomes / Retrospective

- Unity now executes in DLL order: Religion owner lookup, distinct CP owners in
  nation CP order, sequential propaganda, direct cohesion, direct education,
  and hostile-claim legitimize handling.
- Public opinion uses the DLL integer sample count, weak/strong movement
  thresholds, ideology sort/tie order, Undecided normalization, disabled-CP
  filtering for owned-count strength, permanent allies, and the independent
  Religion bonus. Positive Unity samples already at the target ideology remain
  in place, matching the audited DLL branch condition.
- Every propaganda source records its before/after vector and effective inputs.
  Metric evidence is `expected`, `meanPath`,
  `deterministicExpectedTransition`, and `expectationGuarantee: false`.
- Direct cohesion and education remain exact when their own inputs are exact;
  they do not inherit public-opinion stochasticity. Population mean-input
  provenance is still propagated independently when population scaling is an
  upstream input.
- The noon rest cache now computes public dispersion and public/elite divide
  from live vectors. This is the first downstream point at which Unity opinion
  evidence reaches cohesion-rest; later monthly movement inherits it normally.
- Registry rules for Unity and public-opinion cohesion are verified and backed
  by literal expected-value/state-transition fixtures. Registry fixture
  discovery now consumes pytest-collected objects instead of importing the
  unstable `tests` namespace.
- Validation: the focused projection/registry suite passed, then the complete
  suite passed with 248 tests, 9 skips, and 23 subtests. An observational
  10-day smoke on the local Broken Earth save used a currently extant
  four-control-point/five-region nation selected from the save: five Unity
  completions finished with no runtime stop, direct cohesion remained exact,
  public opinion and noon cohesion-rest were expected. The save's current
  `CAL` entry is no longer the earlier four-CP/five-region snapshot, so no CAL
  identity/count/value was promoted to a regression contract.
