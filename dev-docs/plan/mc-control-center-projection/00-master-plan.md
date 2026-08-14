# Include queued control centers in projected mission control

## Issue Target And Scope Summary

- Issue target: MC control-center omission
- Title: Include queued control centers in projected mission control
- Source plan: None
- Scope: Count a completed prior Operations Center while its Command Center
  upgrade is underway, preserve current-state MC semantics for new construction,
  and add a current-queue projection for habitat planning constraints.

## Strategy

- Keep `calculate_topbar()`'s current `capacity`, `usage`, and `available` fields
  tied to operating modules, including completed prior modules that remain in
  service during an upgrade.
- Calculate queued hab-module capacity and usage deltas against each module's
  prior template so new construction and upgrades share one rule.
- Expose the queue projection in the MissionControl topbar row and use its
  projected availability in `hab-plan` candidate and fill calculations.
- Add unit coverage for active, queued, consuming, and non-functional modules,
  then compare the result with the latest local save.

## Phase Order

1. [Reproduce and bound the mission-control omission](01-discovery.md)
2. [Add current-queue mission-control projection](02-implementation.md)
3. [Regression and live-save verification](03-verification.md)

## Phase Dependencies

- Phase 1 has no phase dependency beyond resolved issue context.
- Phase 2 depends on completion and validation of phase 1.
- Phase 3 depends on completion and validation of phase 2.

## Source Of Truth Decisions

- `00-master-plan.md` is the phased implementation plan source of truth.
- Phase files in this directory define phase-local scope and validation.
- Current save values remain authoritative for the existing topbar fields;
  construction-queue values are explicitly nested under
  `projectedAfterCurrentQueue`.
- Hab module template `missionControl` is a signed headroom value: positive
  values add capacity and negative values add usage.
- `TIHabModuleState.priorModuleCompleted` identifies a prior module that remains
  the current MC source while its replacement is under construction.

## Global Validation Expectations

- python -m unittest discover -s tests -v

## Known Risks And Assumptions

- A queued module is projected only when it is not complete, destroyed, or
  decommissioning.
- The save's current `missionControlUsage` is assumed not to include unfinished
  modules; the latest local save confirms this for queued Operations Centers and
  Research Campuses.
- A projected module may still fail to operate after completion because of
  future power or ownership changes. The projection intentionally models the
  current queue and current module templates, not future events.
