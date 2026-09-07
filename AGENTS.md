# AGENTS.md

These instructions apply to the entire `TI_Parser` repository unless a deeper
`AGENTS.md` overrides them.

## Project purpose

`TI_Parser` reconstructs Terra Invicta save-state, UI, planning, and selected
mechanics from `.gz` saves while keeping normal runtime operation package-only.
The parser favors auditable, evidence-backed calculations over convenient
fallbacks.

Start with `README.md` for command behavior and module ownership. Important
implementation areas include:

- `tools/ti_parser_core.py`: save loading, indexing, and reference helpers.
- `tools/ti_parser_snapshot.py`: compact snapshots and cache handling.
- `tools/ti_parser_income.py`: councilor and nation income calculations.
- `tools/ti_parser_hab.py`: hab modules, support, mining, and power.
- `tools/ti_parser_org.py`: org planning and assignment search.
- `tools/ti_parser_mechanics.py`: stable mechanics rule IDs and provenance.
- `tools/ti_parser_nation_validity.py`: tri-state priority validity.
- `tools/ti_parser_nation_projection.py`: cloned projection state, plans,
  transactions, and fail-closed simulation.
- `tools/ti_parser_projection_coverage.py`: execution-derived metric coverage.
- `tools/ti_parser_catalogs.py`: packaged runtime catalog validation.
- `tools/ti_parser_cli.py`: CLI parsing and dispatch.
- `tools/ti_save_parser.py`: public entrypoint and compatibility wrappers.
- `tests/`: behavioral, provenance, runtime-boundary, and regression coverage.

## Evidence and source-of-truth rules

- Do not infer Terra Invicta mechanics solely from current parser behavior when
  authoritative game evidence is available. For mechanics reconstruction,
  distinguish game DLL/template evidence, save evidence, parser implementation,
  and scenario assumptions.
- Normal parser commands must remain package-only. They must not silently read
  an installed Terra Invicta template tree or `Assembly-CSharp.dll` at runtime.
  Raw templates and DLL evidence are generation, audit, or `catalog-verify`
  inputs only.
- Packaged runtime catalogs under `data/` are the runtime source of truth for
  the domains they cover. Missing or incompatible required catalog data is an
  error or an explicit incomplete result, not permission to invent a default.
- Preserve the project's fail-closed behavior. Unsupported mechanics, missing
  blocking dependencies, ambiguous player identity, or unresolved required
  references must remain explicit rather than being converted to plausible
  zeroes, false values, or guessed constants.
- Keep provenance separate from calculated values. When a result is approximate,
  expected, suspected, unsupported, or unknown, preserve that distinction in
  output and diagnostics.
- For `nation-projection`, preserve the authoritative-prefix model: completed
  verified transactions remain authoritative, while an unsupported next action
  stops the affected path before that unsupported mutation executes.
- Coverage must follow the path actually executed. Do not mark downstream
  metrics exact or complete merely because a rule exists somewhere in code.
- When simulation output is surprising, diagnose these layers separately before
  changing code: save extraction, catalog/input resolution, parser mechanics,
  scenario assumptions, and the game's authoritative behavior.

See `docs/nation_projection_mechanics_audit.md` when changing projection
semantics, stochastic treatment, coverage, or provenance boundaries.

## Change discipline

- Read the narrowest relevant code and tests before editing. Search for callers,
  diagnostics, and existing regression tests before introducing a new path.
- Prefer the smallest coherent change that fixes the identified semantic issue.
  Avoid unrelated refactors during mechanics corrections.
- Preserve public JSON shapes and CLI compatibility unless the task explicitly
  requires a breaking change.
- Do not weaken strict dependency checks merely to make a test or example pass.
- Do not hand-edit generated catalogs or generated documentation when a generator
  owns them. Change the generator/source logic and regenerate the owned outputs.
- Do not edit caches or incidental generated artifacts such as `.ti_cache`,
  `.pytest_cache`, `.ruff_cache`, `__pycache__`, or `graphify-out` unless the task
  explicitly concerns them.
- The worktree may already contain user changes. Never revert, overwrite, stage,
  or clean unrelated changes. Scope inspection and edits to the task.

## Testing and verification

Use targeted verification first, then broaden only when the change warrants it.

- Default test runner: `pytest`.
- Run the most relevant test module(s) while iterating.
- Run the full suite for cross-cutting parser, catalog, projection, or public CLI
  changes when feasible.
- For runtime-catalog changes, run the relevant generator/verification path and
  tests that exercise package-only behavior and catalog fingerprints.
- For release-sensitive changes to generated runtime data, use
  `tools/verify_fresh_export.py` when appropriate; it validates committed bytes
  in a clean export rather than trusting checkout line endings.
- Add regression tests for semantic bugs when a focused test can protect the
  invariant. Do not add redundant tests that only mirror implementation details.
- Report commands actually run and any verification that could not be completed.

## Multi-agent operating model

Use the root agent primarily as a coordinator for decomposition, cross-source
reasoning, conflict resolution, and final verification. Delegate bounded work
when doing so reduces expensive reasoning, parallelizes independent evidence
collection, or materially improves quality.

### Current preferred routing

When the runtime supports explicit child model and reasoning-effort selection:

- **GPT-6 Astra, low**: preferred root coordinator. Use for task decomposition,
  deciding what evidence is needed, integrating worker results, and final checks.
- **GPT-5.6 Luna, low**: repository search, symbol/usages lookup, extraction,
  inventory work, repetitive read-heavy inspection, and simple log/test-output
  classification.
- **GPT-5.6 Luna, medium**: bounded analysis that needs modest reasoning but has
  a clear question and narrow evidence set.
- **GPT-5.6 Terra, medium**: ordinary implementation, refactoring, tests, and
  debugging where a worker needs reliable software-engineering judgment.
- **GPT-6 Astra, medium**: escalation for conflicting worker evidence, invalidated
  plans, parser/game-semantics disagreements, repeated worker failures, or
  architecture/simulation-semantics decisions.
- **GPT-6 Astra, high**: exceptional escalation only for unresolved, high-impact,
  structurally difficult problems where medium effort has not been sufficient.

Model names are routing preferences, not repository invariants. If a requested
model or effort is unavailable, preserve the role separation and use the
cheapest available worker that can reliably perform the bounded task.

### Delegation rules

- Prefer a fresh, bounded subagent with only the context required for its task
  over cloning the root's entire conversation into a cheaper worker.
- When the runtime permits overrides, explicitly request both the worker model
  and reasoning effort rather than assuming the desired budget will be inherited.
- Do not spawn a copy of the root model for deterministic work that Luna or Terra
  can reliably perform.
- Do not delegate tiny tasks when spawn/context overhead is likely to exceed the
  work itself.
- Parallelize independent searches or checks when it can save time, but avoid
  redundant agents investigating the same question without a reason.
- Give each worker a concrete question, bounded files/scope when known, and a
  requested output format. Workers should return evidence, not a broad strategic
  conclusion unless asked for one.
- Useful worker returns include file paths/lines or symbols inspected, observed
  values, commands/tests run, assumptions, uncertainties, and a concise finding.
- The coordinator owns synthesis. Verify important worker claims against source
  evidence before changing mechanics or presenting a final conclusion.
- If two workers disagree, do not vote. Identify the differing assumptions or
  evidence and resolve the conflict at the coordinator level; escalate reasoning
  effort if needed.

### Coordinator escalation triggers

Raise the root from Astra low to medium when one or more of these occurs:

1. Independent worker results materially conflict.
2. A core assumption in the original plan is disproved during execution.
3. Game-source evidence, save state, packaged catalogs, and parser behavior do
   not agree on the same mechanic.
4. The same implementation or test failure survives two competent attempts.
5. A change would alter projection semantics, provenance, fail-closed behavior,
   catalog boundaries, or public result contracts.
6. The task requires a new architecture or state-transition model rather than a
   localized implementation decision.

Return to low effort for routine follow-up work after the difficult decision is
resolved. Do not keep high reasoning enabled merely because the task is long.

## Efficiency goal

Optimize for successful work per unit of reasoning and context, not for the
fewest agent calls in isolation. Keep expensive coordinator context focused on
requirements, evidence summaries, decisions, and unresolved conflicts; push
large deterministic scans and repetitive extraction to cheaper bounded workers.
Avoid re-reading or re-sending large save, catalog, or repository context when a
small evidence summary is sufficient.
