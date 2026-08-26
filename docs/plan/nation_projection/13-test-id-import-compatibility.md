# Phase 13: Cross-runner mechanics test-ID resolution

## Goal

- Make stable mechanics registry test IDs resolve identically under unittest discovery and pytest.

## Scope

- Preserve the existing canonical `tests.<module>.<class>.<method>` registry IDs.
- Make the repository `tests` directory an explicit importable package.
- Reproduce and regress the pytest failure while retaining unittest behavior.

## Non-goals

- Do not change mechanic rule IDs, evidence metadata, or supported coverage.
- Do not add runner-specific fallback imports to production mechanics code.
- Do not modify nation simulation behavior.

## Affected files

- `tests/__init__.py`
- `docs/plan/nation_projection/00-master-plan.md`
- `docs/plan/nation_projection/13-test-id-import-compatibility.md`

## Implementation steps

1. Reproduce the `ModuleNotFoundError: No module named 'tests'` failure with `pytest -q`.
2. Add an explicit test-package marker documenting why canonical registry paths depend on it.
3. Run the focused mechanics registry test under pytest and unittest.
4. Run both complete test entrypoints and verify their expected runner-specific counts.

## Acceptance criteria

- Every registry `test_id` imports through its unchanged canonical dotted path under both runners.
- `validate_test_metadata()` still verifies the decorator metadata on the resolved callable.
- `pytest -q` and unittest discovery both pass.
- No production calculation or registry semantics change.

## Validation commands

- pytest -q tests/test_mechanics_registry.py
- py -3 -m unittest tests.test_mechanics_registry
- pytest -q
- py -3 -m unittest discover -s tests -p 'test_*.py'
- py -3 C:\Users\techn\.codex\skills\phased-issue-implementation\scripts\phase_plan_helper.py validate --strict --plan-dir docs\plan\nation_projection

## Manual smoke tests

- Import `tests.test_nation_projection` from the repository root and resolve one registry class/method path.

## Rollback risks

- Adding `tests/__init__.py` changes test collection module names to package-qualified names; both complete runners must be checked for collection count or duplication changes.

## Progress

- Completed: the test tree is an explicit package and both supported test
  entrypoints resolve unchanged registry IDs.

## Decision log

- Keep registry IDs stable and fix the repository import contract instead of rewriting IDs for whichever runner happens to execute them.

## Outcomes / Retrospective

- Root cause: the registry correctly stored canonical
  `tests.<module>.<class>.<method>` IDs, but the test directory was not an
  explicit package. Pytest imported collected modules without making the
  `tests` namespace reliably importable, so the registry's direct
  `importlib.import_module()` verification failed before checking metadata.
- Added `tests/__init__.py` as the repository-level import contract. No
  production module, mechanic rule, evidence metadata, or calculation changed.
- The representative canonical path imports directly and resolves its class and
  method. Focused registry validation passes under both runners.
- Final validation: pytest reports 233 passed, 9 skipped, and 23 subtests;
  unittest discovery reports 242 tests passed with 9 skipped.
- Graphify was incrementally refreshed after the package marker was committed:
  2,162 nodes, 6,208 edges, and 117 communities. Multigraph diagnostics report
  no malformed, missing-endpoint, dangling, self-loop, or duplicate edges.
