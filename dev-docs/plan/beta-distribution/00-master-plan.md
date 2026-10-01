# Small beta distribution

## Issue Target And Scope Summary
Implement the user-approved TI_Parser beta plan: ZIP execution in Codex and Python-capable ChatGPT, trustworthy selection/input, explicit compatibility consent, saved-fact inspection and basic analysis, MIT code license, reproducible distribution and CI.

## Strategy
Preserve package-only mechanics and existing result fields; add typed failures, strict selectors, a separate raw inspection path, stable saveIdentity, explicit compatibility metadata and consent, and a thin application/session boundary reusing domain functions. analyze is bounded LLM bootstrap context, not a comprehensive campaign report. capabilities inventories specialized analyses for future machine callers. Do not refactor the projection engine or regenerate catalogs.

## Phase Order
1. Input and entity hardening (01-input.md).
2. Inspection and compatibility (02-compatibility.md).
3. Analysis report and assistant workflow (03-analysis.md).
4. Reproducible beta distribution (04-distribution.md).
5. CI and acceptance (05-verification.md).

## Phase Dependencies
Runtime phases 1 -> 2 -> 3. Distribution/docs and CI scaffolding may proceed independently; integration follows stable runtime interfaces. Root owns integration, plans and phase commits. Workers have non-overlapping file ownership.

## Source Of Truth Decisions
User-approved plan is authoritative. This directory tracks implementation and evidence. Compatibility registry starts empty until a tested version/scenario/catalog combination has actual evidence; no game version is inferred. --allow-unverified is per invocation and never bypasses catalog or mechanics dependencies. Existing successful fields remain; error contracts intentionally change.

## Global Validation Expectations
Targeted pytest per phase, full pytest after runtime integration, committed fresh-export gate, deterministic ZIP tests and extracted ZIP smoke from outside checkout. Windows/Linux Python 3.11-3.14 CI. No private saves in git/artifacts. Real ChatGPT and platform matrix claims require execution evidence.

## Known Risks And Assumptions
Current host is Windows Python 3.14. External ChatGPT execution and other Python/OS versions may be unavailable; record pending acceptance honestly. Game-derived data redistribution permission is not established by MIT code licensing; external distribution remains gated. No external publishing is authorized. No arithmetic/catalog payload changes are intended.

## Product direction clarification
TI_Parser is a standalone LLM analysis/simulation engine. An external provider may eventually supply UI/history context, but this beta adds no companion dependency/integration, history, save diff, alerts, UI, browser/Pyodide, FastAPI, or MCP server. CLI calls a reusable Python session; existing calculate_* functions remain authoritative. saveIdentity is versioned and content-based, independent of path/mtime, and includes game date, canonical scenario, version, campaign-start evidence and resolved player identity. Unknown identity remains explicit.
