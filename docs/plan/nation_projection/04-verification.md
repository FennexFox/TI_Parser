# Phase 04: Regression verification and documentation

## Goal

- Complete one-tick fixtures, integrity checks, observational validation support, and end-to-end regression verification.

## Scope

- Rule-linked expected-value tests.
- Transaction, advisor, contribution, coverage, catalog, CLI, and package-only tests.
- Documentation of strict versus observational validation and limitations.

## Non-goals

- No claim that uncontrolled save endpoints are strict validation.

## Affected files

- `tests/test_nation_projection.py`
- `tests/test_mechanics_registry.py`
- `tests/test_catalog_generators.py`
- `tests/test_runtime_catalogs.py`
- `tests/test_package_only_runtime.py`
- phase documentation

## Implementation steps

1. Add independent fixtures for every supported rule.
2. Add registry-to-test coverage assertions.
3. Verify package-only runtime and catalog parity.
4. Run full regression suite and CLI smoke tests.
5. Record controlled strict validation as a future local-game procedure; label existing saves observational only.

## Acceptance criteria

- Existing 179 tests remain green and new tests cover all supported mechanic IDs.
- No runtime access to raw templates/DLL is introduced.
- Diagnostics IDs/revisions/hashes are internally consistent.

## Validation commands

- py -3 -m unittest discover -s tests -p 'test_*.py'

## Manual smoke tests

- Run the user examples on a real local save; inspect complete and incomplete output paths.

## Rollback risks

- Tests and docs are additive; any game-version mismatch is exposed by provenance rather than hidden.

## Progress

- Completed.

## Decision log

- Registered a stable completion rule ID for every unsupported priority so an
  incomplete result can identify the exact missing mechanics rather than only
  naming a priority.
- Segment conditions are recorded after a transaction but the new CP and
  Advisor policy is applied immediately before the next investment tick.
- The installed real save is suitable for CLI and incomplete-path smoke tests,
  not strict A to B validation. No uncontrolled endpoint comparison is claimed
  as strict evidence.
- Full `catalog-verify` currently also reports unrelated source-hash drift in
  the pre-existing research catalog's installed DLC inputs. The new nation
  development catalog's payload and exact source-hash parity checks pass.

## Outcomes / Retrospective

- `py -3 -m unittest discover -s tests -p 'test_*.py'`: 199 tests passed, one
  skipped. This preserves the original 179-test baseline and adds registry,
  catalog, projection, transaction, Advisor, contribution, fail-closed, CLI,
  and package-only coverage.
- A real `KOR` one-day CLI run completed normally and correctly returned an
  incomplete non-authoritative plan because the save's current CP pips include
  unsupported priorities. Diagnostics included the audited DLL hash and rule
  metadata.
- Rebuilding and comparing `nation_development_catalog.json` against the
  installed templates and DLL passed both selected-payload and exact source-hash
  parity.
- Controlled strict save pairs were not available in the repository. Their
  creation remains a local-game validation procedure; existing campaign saves
  are explicitly observational only.
