# Phase 06: Package-only and raw-reference verification

## Goal

- Prove standalone execution and provide an explicit installed-data verification path.

## Scope

- Add `catalog-verify`, package-only CLI tests, deterministic generation tests, and common diagnostics output.

## Non-goals

- Verification must never become an implicit runtime fallback.

## Affected files

- CLI, verification helper, tests, README draft.

## Implementation steps

- Trap every raw loader while exercising topbar/research/org/hab/forecast/ship/CP/MC.
- Compare Mercury solar, CP, MC, research, org eligibility, and ship design using fixed tolerances.
- Report schema/fingerprint/scenario/override metadata for each comparison.

## Acceptance criteria

- Package-only commands pass and verification differences are zero or within documented tolerance.

## Validation commands

- python -m unittest discover -s tests -v

## Manual smoke tests

- Run `catalog-verify` for available Standard-family and Broken Earth saves; use synthetic 2003 identity if no save exists.

## Rollback risks

- Installed data may advance independently of checked-in catalogs; report hash mismatch distinctly from formula mismatch.

## Progress

- Complete: package-only raw-loader traps and explicit `catalog-verify` raw/package parity are implemented.

## Decision log

- Save-backed checks use the requested scenario only and report unavailable instead of inventing evidence when inputs are absent.

## Outcomes / Retrospective

- Broken Earth verification passes all 12 checks, including Mercury solar, CP, MC, research, org eligibility, and saved-design simulation.
