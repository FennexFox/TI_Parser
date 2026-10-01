# Phase 05: Automate matrix and distribution acceptance and document remaining gates.

## Goal

- Automate matrix and distribution acceptance and document remaining gates.

## Scope

- CI workflow, ZIP verifier, acceptance record and final regression.

## Non-goals

- No game formula changes, catalog regeneration, projection restructuring or external publication.

## Affected files

- CI workflow, ZIP verifier, acceptance record and final regression.

## Implementation steps

- Run full pytest/fresh export; isolated extracted ZIP synthetic workflow; configure Windows/Linux3.11-3.14; record actual Codex/ChatGPT evidence.

## Acceptance criteria

- All available checks pass; unavailable platform/ChatGPT/data rights checks remain explicitly pending.

## Validation commands

- python -m pytest -q
- python tools/verify_fresh_export.py

## Manual smoke tests

- Codex extracted ZIP scenario; ChatGPT if accessible, otherwise pending.

## Rollback risks

- Local success is not remote CI or ChatGPT evidence.

## Progress

- Implemented Windows/Linux x Python 3.11-3.14 CI, pinned pytest development dependency, committed-export pytest collection and isolated ZIP verifier. Local integrated regression passed 392 tests (13 skipped, 75 subtests) before final review fixes; committed-export gate will record the final count.
- ZIP validation checks independent distribution membership, hashes, six catalog scenarios, version/help/inventory, inspection, compatibility blocking, deferred bootstrap and opt-in bootstrap/topbar. Processes run outside the repository under -I -S with network/game-input audit guards and Korean/space paths.
- Final committed-source validation at 884cb11f73b67f4a64885616a8c64b022e6b100b: `python tools/verify_fresh_export.py` passed 395 tests, 13 skipped, 75 subtests; package-only suite passed 6 tests and all 6 scenario catalog loads. Plan helper strict validation passed all 5 phases.
- `python tools/build_beta_distribution.py --ref HEAD` and `python tools/verify_beta_distribution.py dist/TI_Parser-0.1.0b1.zip` succeeded on the same commit. Artifact has 55 files, SHA-256 `b6d84f61bff4d9f9573df3e2ad988b23b3f5a05b790ac990fdfb02e778d680ca`. All 9 isolated checks passed. Artifact stays ignored/local; this subsequent evidence-only documentation commit does not change its runtime bytes.

## Decision log

- Use user-approved beta contract; root integrates independent worker changes.

## Outcomes / Retrospective

- Local Codex execution is available; real Python-capable ChatGPT acceptance is not available in this session and remains pending. The remote eight-environment CI matrix has been configured but not executed here. Game-derived data redistribution conditions remain unconfirmed. No external publication or upload occurred.


## Machine contract checks
Verify saveIdentity stability across copies and changes when save contents change, unknown player/version handling, and capabilities inventory consistency.
