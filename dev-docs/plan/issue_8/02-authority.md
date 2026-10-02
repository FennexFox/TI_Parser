# Authoritative build and visibility evidence

## Goal

Establish matching source evidence before granting any visibility acceptance.

## Scope

Compare explicitly supplied assembly fingerprint with catalog provenance; classify evidence separately from save/parser facts.

## Non-goals

Regenerate runtime catalogs or migrate mechanics to the installed build.

## Affected files

dev-docs/fairplay_interoperability.md; existing projection mechanics audit.

## Implementation steps

Record full hashes; obtain matching-build or validated cross-build visibility/correctness evidence; leave missing evidence unresolved.

## Acceptance criteria

Structural audit can finish independently. Authority acceptance remains open while build or visibility evidence is unresolved.

## Validation commands

- `git diff --check`

## Manual smoke tests

Hash the explicitly named installed assembly and compare with catalog source metadata.

## Rollback risks

No runtime installed-game discovery or inference from the current parser.

## Progress

Blocked on matching/cross-build evidence. Structural completeness, build/source
authority, visibility and overall policy eligibility are separate report gates.
Exit 0 requires explicit acceptance of every gate; missing evidence, mismatch
and hash equality alone cannot approve. Regression tests exercise those cases
and require visibility evidence to cover the exact dependency IDs and scope.

The explicit offline assembly comparison confirmed the known mismatch. Full
hashes are maintained in the interoperability audit; normal runtime performed
no installed-game discovery and committed catalogs were not regenerated.

## Decision log

The known build mismatch is a mandatory predecessor gate for phase 3.

## Outcomes / Retrospective

Acceptance is pending the evidence and checks above; implementation completion is not release acceptance.
