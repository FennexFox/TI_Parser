# Phase 02: Catalog and domain consistency

## Goal

- Reduce repeated work and consolidate domain boundaries without changing public results.

## Scope

- Packaged module/location integrity and duplicate rejection; command-local catalog reuse; cohesive implementation extraction; evidence-backed adviser selection.

## Non-goals

- Wholesale rewrite, guessed game mechanics, new CLI output shapes.

## Affected files

- Catalog loaders/generators, a new domain module, public facade wrappers, relevant tests and README.

## Implementation steps

- Inspect evidence and choose narrow boundaries; update generators and regenerate owned data; preserve wrappers; reuse validated catalog objects; verify parity and package-only behavior.

## Acceptance criteria

- All runtime catalog domains receive integrity protection; repeated loads are bounded per command; extracted domain preserves signatures/results; adviser policy follows authoritative evidence.

## Validation commands

- python -B -m pytest -q -p no:cacheprovider

## Manual smoke tests

- Compare public wrappers and extracted module results; verify altered catalog bytes are rejected.

## Rollback risks

- Public compatibility must remain; revert the phase commit rather than weakening checks.

## Progress

- Complete.

## Decision log

- Extracted 23 pure ship helpers with AST parity and public reexports; retained orchestration in the facade.
- Runtime bundles are reused only within one CLI invocation; new commands revalidate bytes.
- Module/location generators attach canonical payload fingerprints, excluding provenance timestamps; loaders reject tampering and duplicate module IDs.
- Decompiled game evidence confirmed active advisers exclude detained councilors. Real saves omit computed activity booleans, so snapshot schema 7 reconstructs them from status and detainingFaction. Missing evidence stays unknown.

## Outcomes / Retrospective

- Full pytest: 325 passed, 13 skipped, 45 subtests passed.
- Both catalog generators ran against installed templates: 156 modules; 495 bodies, 117 navigables, 919 orbits. Numeric game payloads unchanged; module localization regenerated.
- Actual latest-save topbar smoke succeeded with complete output and 13 resources.
- Added regressions for integrity, malformed JSON/UTF-8, command scope, activity reconstruction, rank filtering, and projection roster selection.
