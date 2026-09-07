# Phase 07: Nation claims diagnostics

## Goal

- Add read-only claim hostility and eligibility diagnostics grounded in game code.

## Scope

- Add `nation-claims`, packaged claim threshold/provenance, static/conditional/peaceful classification.

## Non-goals

- Do not claim annexation, independence, or claim succession behavior that was not reconstructed.

## Affected files

- New claims module, claim catalog section, CLI wiring, synthetic tests, README.

## Implementation steps

- Resolve nation/region references from the save and report the source of each raw claim.
- Apply the verified democracy differential and expose values, threshold, formula, and changeability.
- Reconstruct federation/unification predicates only where all inputs and game-code rules are evidenced.

## Acceptance criteria

- Peaceful, static hostile, conditional hostile, and threshold-boundary tests pass with provenance.

## Validation commands

- python -m unittest discover -s tests -v

## Manual smoke tests

- Inspect claims for an installed save and compare with serialized `claims`/`hostileClaims` lists.

## Rollback risks

- `static` does not automatically mean permanent; output `permanent: null` unless permanence is proven.

## Progress

- Complete: `nation-claims` joins save claims, hostile claims, owners, democracy values, and packaged rule provenance.

## Decision log

- Permanence and post-annexation/unification/independence succession remain unknown unless directly evidenced.

## Outcomes / Retrospective

- Peaceful, static hostile, conditional hostile, strict threshold boundary, filters, and unsupported succession are covered.
