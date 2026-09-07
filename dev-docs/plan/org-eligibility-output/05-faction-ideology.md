# Phase 05: Enforce faction ideology restrictions

## Goal

- Prevent org recommendations when the selected faction is listed in the template's `restricted` ideologies, and enforce faction-org affinity ownership.

## Scope

- Extend requirement and faction-eligibility output with template ideology rules.
- Apply the rules through `org_plan_owner_eligibility` so candidate diagnostics, individual goal views, and committee search share one decision.
- Preserve ordinary-org `affinities` as a non-blocking availability weight.

## Non-goals

- Recomputing market generation, required technology, detention, or Earth-system location.
- Treating ordinary-org affinity as a hard eligibility rule.

## Affected files

- `tools/ti_parser_org.py`
- `tests/test_org_plan.py`
- `dev-docs/plan/org-eligibility-output/*.md`

## Implementation steps

- Reconstruct the installed game rules from `TIOrgState.IsEligibleForFaction` and record the source-of-truth decision.
- Normalize template ideology values against `faction_ideology_key`.
- Add explicit reasons for a restricted ideology, an unresolved faction ideology, and a mismatched faction-org affinity.
- Add focused allow/block tests and prove committee search excludes a numerically superior restricted candidate.

## Acceptance criteria

- A faction listed in `restricted` has no eligible councilors and receives no individual or committee recommendation for the org.
- The same org remains eligible for a non-restricted faction when all other rules pass.
- A normal org's `affinities` does not block a non-affinity faction.
- A faction org requires its faction ideology in `affinities`.

## Validation commands

- `python -m unittest tests.test_org_plan -v`

## Manual smoke tests

- Run the latest-save org plan and confirm every recommended action's candidate is faction eligible.

## Rollback risks

- Scenario and mod templates may use unrecognized ideology values; these must produce an explicit diagnostic rather than a silent allow.

## Progress

- Complete.

## Decision log

- The installed game's `TIOrgState.MeetsIdeologyRequirement` rejects a faction when its ideology appears in `TIOrgTemplate.restricted`.
- `TIOrgState.AvailabilityModifier` uses ordinary-org affinity only as a weight, while `IsEligibleForFaction` requires affinity membership for `OrgType.Faction`.
- Ideology names are compared case-insensitively after resolving the selected faction through `faction_ideology_key`.

## Outcomes / Retrospective

- Requirement rows now expose `restrictedFactionIdeologies` and faction-org-only `requiredFactionAffinities`.
- `factionEligibility` reports the selected ideology, evaluated rule set, and explicit block reasons; owner eligibility propagates the same result to all planners.
- `python -m unittest tests.test_org_plan -v`: 27 tests passed.
- Latest-save smoke test inspected 28 source candidates and 73 emitted recommendation actions. Five candidates had ideology restrictions, one was blocked for the selected `Cooperate` faction, and zero emitted actions were faction-ineligible.
