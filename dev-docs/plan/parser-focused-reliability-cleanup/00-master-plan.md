# TI Parser focused reliability cleanup

## Issue Target And Scope Summary

- Issue target: focused reliability cleanup
- Title: TI Parser focused reliability cleanup
- Source plan: user-approved six-phase reliability cleanup plan
- Scope: close portability, missing-definition, scenario-overlay, diagnostics, and package-only acceptance defects at baseline `6e6aaa3`; add no new game mechanics.

## Strategy

- Canonicalize generated catalog bytes before changing runtime semantics.
- Route required named references through one structured resolver while preserving optional absence.
- Add ship scenario deltas and merge claims diagnostics without changing normal result shapes.
- Lock the runtime with a command matrix and a clean LF fresh-export gate.
- Commit every phase independently after its focused validation passes.

## Phase Order

1. [Canonical LF catalog artifacts](01-catalog-portability.md) — complete
2. [Referenced definition fail-closed](02-fail-closed.md)
3. [Ship scenario delta generation](03-ship-overlays.md)
4. [Claims diagnostics merge](04-claims-diagnostics.md)
5. [Package-only command matrix](05-package-only.md)
6. [Fresh-export gate and documentation](06-fresh-export.md)

## Phase Dependencies

- Phase 1 has no phase dependency beyond resolved issue context.
- Phase 2 depends on completion and validation of phase 1.
- Phase 3 depends on completion and validation of phase 2.
- Phase 4 depends on completion and validation of phase 3.
- Phase 5 depends on completion and validation of phase 4.
- Phase 6 depends on completion and validation of phase 5.

## Source Of Truth Decisions

- `00-master-plan.md` is the phased implementation plan source of truth.
- Phase files in this directory define phase-local scope and validation.
- Earlier monolithic plans are input material only unless explicitly retained.

## Global Validation Expectations

- python -m unittest discover -s tests -v
- python -m unittest tests.test_package_only_runtime -v
- python tools/verify_fresh_export.py

## Known Risks And Assumptions

- The worktree is clean at `6e6aaa3`; generated catalogs are intentionally tracked.
- Local game templates and assembly are generation/verification inputs only.
- Module/location schemas stay unchanged; only their serialized line endings may change.
- Missing scenario overlay files mean base inheritance; malformed overlays and unsupported scenarios fail closed.
- The fresh-export gate is run only after the final implementation commit so `HEAD` contains every change.
