# Development notes

This replaces completed phase-by-phase plans. It summarizes lasting outcomes,
not a release changelog or new verification run. Detailed decisions, commands,
test counts, and old plans remain available in Git history.

## Completed work

| Area | Lasting outcome |
| --- | --- |
| Reliability and domain extraction | Direct acyclic dependencies, preserved facade exports/CLI behavior, explicit advisor activity and fail-closed identity/reference handling |
| Package-only portability | Raw runtime template dependencies replaced by scenario-aware packaged catalogs; source hashes, integrity checks, dependency diagnostics, canonical output bytes and fresh-export verification |
| Hab and organization planning | Current versus queued MC separated; location-aware power/costs; lower-tier duplicate filtering; org capacity, ideology, acquisition and recommendation eligibility enforced |
| Nation projection | Audited transaction scheduler, shared tri-state validity, authoritative prefixes, execution-derived metric coverage, Economy/Unity branches and identity-preserving BuildNavy conversion |
| Advisor projection | Repeat-order lifecycle, inactive renewal gaps and Influence costs; future affordability, detention, competing orders and target changes held fixed |
| Beta analysis boundary / issue #5 | Save inspection, compatibility consent, stable identity, bounded bootstrap, analysis registry, structured application results and deterministic runtime ZIP |
| Python/MCP boundary / issue #6 | Reusable one-save sessions, optional stdio adapter, canonical registry input schemas and SDK-independent application output schemas |

BuildNavy was merged with PR #2 in `beced6b`, which is part of the current
checkout's history. Its old phase log's pending push/merge wording was stale.

Current contracts live in [architecture](architecture.md), [catalog verification](catalogs.md),
the [projection audit](nation_projection_mechanics_audit.md), and the
[public API](../docs/API.md). Deliberate unsupported simulation paths are documented
there rather than retained as unfinished implementation phases.

## Outstanding acceptance and follow-ups

The removed plans did not establish completion of the following items. Check
current external evidence before closing them; this documentation cleanup does
not perform publication, CI dispatch, or PR changes.

- Beta release acceptance: actual execution in a Python-capable ChatGPT environment,
  remote Windows/Linux × Python 3.11–3.14 matrix results, and game-derived catalog
  redistribution review. The compatibility registry remains unverified until
  supporting evidence is recorded.
- L2 solar/eclipse provenance: evaluate replacing reliance on saved `templateName`
  with packaged `lagrangeValue` where appropriate; older notes identified this as
  a possible improvement, not an implemented or proven bug.
