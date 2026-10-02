# Phase 02: Contract and routing guidance

## Goal

- Publish the profile and interoperability contract in user-facing runtime documentation and keep the source-checkout audit/index current.

## Scope

- Document profile options, the complete route matrix, save matching, and reproducible 180-day A/B prompt in `docs/MCP_SETUP.md`.
- Document API implications and link to the detailed audit.
- Maintain projection visibility rationale, acceptance gates, and active plan index in developer references.

## Non-goals

- Claim the Companion MCP/Codex two-server integration has passed without its actual run.

## Affected files

- `docs/MCP_SETUP.md`, `docs/API.md`, `dev-docs/fairplay_interoperability.md`, `dev-docs/README.md`, `dev-docs/plan/issue_8/*`.

## Implementation steps

- Verify documentation against existing save identity and registry source.
- Check local links and whitespace; validate the phase plan structure.

## Acceptance criteria

- User guide describes omitted/default behavior and `--profile fair-play` configuration without inventing companion commands.
- Runtime ZIP user guide contains the route matrix, matching rules, and A/B prompt.
- Developer audit labels external validation and projection visibility as unresolved.

## Validation commands

- python C:\\Users\\techn\\.codex\\skills\\phased-issue-implementation\\scripts\\phase_plan_helper.py validate --plan-dir dev-docs/plan/issue_8
- git diff --check

## Manual smoke tests

- No product integration smoke test: companion MCP and Codex-side server are unavailable in this repository task.

## Rollback risks

- Revert only the documentation phase files if their contract description becomes inaccurate; preserve implementation and unrelated work.

## Progress

- Complete. User guide, API note, developer audit, and index updated.

## Decision log

- Keep the full runbook essentials in `docs/MCP_SETUP.md`, which is included in the runtime ZIP; detailed source evidence stays source-checkout-only.
- Use `--profile fair-play` in the parser MCP launch example; no companion-specific command is documented.

## Outcomes / Retrospective

- Documentation describes the implemented TI profile contract; only actual Companion MCP/Codex interoperability remains external acceptance.
