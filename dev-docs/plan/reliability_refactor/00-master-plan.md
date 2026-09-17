# Parser reliability and bounded refactoring

## Issue Target And Scope Summary

- Issue target: Repository-wide review follow-up
- Title: Parser reliability and bounded refactoring
- Source plan: None
- Scope: Implement the confirmed repository-review defects, then bounded domain extraction, catalog reuse/integrity, and adviser consistency with authoritative evidence. Preserve public entrypoints and successful JSON contracts.

## Strategy

- Fix correctness before moving implementation. Phase 1 covers snapshot freshness/recovery, mission timing coverage, MC missing positions, default CLI arguments, verifier exit status, and structured errors. Phase 2 unifies packaged catalog integrity, reuses validated command inputs, extracts a cohesive domain from the public facade, and reconciles adviser selection after evidence review. Phase 3 runs complete checkout and committed-export acceptance.

## Phase Order

1. [Cache, coverage and CLI correctness](01-reliability.md)
2. [Catalog and domain consistency](02-structure.md)
3. [Cross-platform acceptance](03-verification.md)

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

- Generated data must be regenerated or restored byte-for-byte from Git, never hand-authored. Existing trait catalog has stale CRLF checkout bytes; restore committed LF bytes after proving equivalence. No semantic change based only on parser disagreement. Keep module moves separate from mechanics corrections; use focused compatibility tests. Runtime commands remain package-only. Commit each validated phase with scoped staging.

## Completed extraction follow-up

- The initially bounded ship-helper extraction was completed across the remaining domains in [domain_extraction](../domain_extraction/00-master-plan.md). The public facade now contains only explicit compatibility exports and CLI entry functions.
