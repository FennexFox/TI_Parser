# Authoritative build and visibility evidence

## Goal

Establish matching source evidence before granting any visibility acceptance.

## Scope

Compare explicitly supplied assembly fingerprint with catalog provenance; classify evidence separately from save/parser facts.

## Non-goals

Treat regenerated hashes as mechanics or visibility approval. Current-build catalog refresh is a required predecessor, using existing generators.

## Affected files

dev-docs/fairplay_interoperability.md; existing projection mechanics audit.

## Implementation steps

Fingerprint explicit installed DLL/templates/DLC/localization inputs before and after generation. Verify generator compiled defaults against current DLL. Generate all families twice in temporary outputs, review normalized payload and overlay differences, then regenerate committed artifacts. Re-audit source mechanics and visibility independently; leave missing evidence unresolved.

## Acceptance criteria

Structural audit can finish independently. Authority acceptance remains open while build or visibility evidence is unresolved.

## Validation commands

- `git diff --check`

## Manual smoke tests

Hash the explicitly named installed assembly and compare with catalog source metadata.

## Rollback risks

No runtime installed-game discovery or inference from the current parser.

## Progress

The current-build predecessor is implemented. Two independent generations
match byte-for-byte; before/after explicit game input inventories match.
Compiled defaults and selected mechanics were reviewed against the current
DLL; semantic catalog changes are limited to four 2003Scenario research fields.
See [catalogs](../../catalogs.md) for fingerprints and reviewed differences.

The live audit now reports assembly `match`, resolving the historical
stale-provenance mismatch. Structural, build/source authority, visibility and
overall eligibility remain separate. Full authority and visibility acceptance
are unresolved; no accepted packet is supplied and overall exit remains 2.
Acceptance scope now binds catalog bytes, parser source/dependencies and exact
execution shape; a changed baseline invalidates previous scope evidence.

## Decision log

The historical build mismatch is resolved by regeneration, not by relabeling
old evidence. Current hash equality cannot replace source mechanics review,
structural closure or visibility evidence; phase 3 remains blocked.

## Outcomes / Retrospective

Acceptance is pending the evidence and checks above; implementation completion is not release acceptance.
