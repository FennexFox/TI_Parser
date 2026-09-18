# Complete domain ownership behind public facade

## Issue Target And Scope Summary

- Issue target: Complete remaining facade extraction
- Title: Complete domain ownership behind public facade
- Source plan: None
- Scope: Finish the partially completed domain extraction. Keep public names, signatures, CLI and successful/error JSON behavior; move all remaining domain implementations out of ti_save_parser.py.

## Strategy

- Extract shared configuration/adapters and coherent hab, research, project, ship, income, world, nation and projection-input modules. Keep explicit facade reexports and CLI entry functions. Preserve function bodies, use explicit dependency imports, and break genuine cross-domain import cycles with local imports.

## Phase Order

1. [Boundaries and compatibility baseline](01-boundaries.md)
2. [Move domain implementations](02-extraction.md)
3. [Compatibility and acceptance](03-acceptance.md)

## Phase Dependencies

- Phase 1 has no phase dependency beyond resolved issue context.
- Phase 2 depends on completion and validation of phase 1.
- Phase 3 depends on completion and validation of phase 2.

## Source Of Truth Decisions

- `00-master-plan.md` is the phased implementation plan source of truth.
- Phase files in this directory define phase-local scope and validation.
- Earlier monolithic plans are input material only unless explicitly retained.

## Global Validation Expectations

- python -B -m pytest -q -p no:cacheprovider

## Known Risks And Assumptions

- Existing tests patch facade globals; retarget mocks to implementation owners without changing assertions. No game mechanics, generated catalogs, caches or raw runtime inputs change. Verify AST body parity and import order independently of behavior tests.
