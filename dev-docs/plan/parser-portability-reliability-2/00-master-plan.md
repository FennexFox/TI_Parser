# Package-only reliability and diagnostics

## Issue Target And Scope Summary

- Issue target: TI_Parser package-only reliability follow-up
- Title: Package-only reliability and diagnostics
- Source plan: None
- Scope: Remove silent calculation degradation and normal-runtime raw-template reads; package the effect, trait,
  org, research, ship, and claim data required by calculations; add structured provenance, claims diagnostics,
  AI/fleet diagnostics, package-only regression coverage, verification tooling, and current documentation.

## Strategy

- Introduce one scenario-aware runtime catalog bundle with deterministic manifests and strict row resolution.
- Keep raw templates and the installed assembly exclusively in catalog generation and explicit verification tools.
- Raise structured dependency errors at calculator boundaries and retain existing successful JSON fields.
- Migrate existing domains before adding claims and AI diagnostics, then enforce the boundary with automated guards.

## Phase Order

1. [Runtime dependency and silent-fallback audit](01-audit.md)
2. [Strict dependency and catalog foundation](02-foundation.md)
3. [Effects traits and org catalogs](03-core-catalogs.md)
4. [Research runtime migration](04-research.md)
5. [Ship runtime migration](05-ship.md)
6. [Package-only and raw-reference verification](06-verification.md)
7. [Nation claims diagnostics](07-claims.md)
8. [AI and fleet diagnostics](08-ai-fleet.md)
9. [Final regression documentation and audit](09-final.md)

## Phase Dependencies

- Phase 1 has no phase dependency beyond resolved issue context.
- Phase 2 depends on completion and validation of phase 1.
- Phase 3 depends on completion and validation of phase 2.
- Phase 4 depends on completion and validation of phase 3.
- Phase 5 depends on completion and validation of phase 4.
- Phase 6 depends on completion and validation of phase 5.
- Phase 7 depends on completion and validation of phase 6.
- Phase 8 depends on completion and validation of phase 7.
- Phase 9 depends on completion and validation of phase 8.

## Source Of Truth Decisions

- `00-master-plan.md` is the phased implementation plan source of truth.
- Phase files in this directory define phase-local scope and validation.
- Earlier monolithic plans are input material only unless explicitly retained.

## Global Validation Expectations

- python -m unittest discover -s tests -v

## Known Risks And Assumptions

- The baseline is commit `253b86f`; 139 tests pass and one optional local fixture test is skipped.
- Base, Dark Skies DLC templates, `Assembly-CSharp.dll`, and local saves are available for verification.
- Unknown or unsupported scenarios must be incomplete; they must never inherit Standard data silently.
- Game mechanics are implemented only when demonstrated by saves, templates, decompiled code, or existing verified behavior.
