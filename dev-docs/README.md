# Developer documentation

User workflows and public integration contracts live in [docs/](../docs/README.md).
This directory contains maintained engineering references, audit evidence, and
active work. It is excluded from the runtime ZIP.

| Reference | Purpose |
| --- | --- |
| [Architecture](architecture.md) | Module ownership and dependency boundaries |
| [Catalogs and verification](catalogs.md) | Generation, package-only rules, and release checks |
| [Nation projection audit](nation_projection_mechanics_audit.md) | DLL evidence, rule index, coverage, and validation limits |
| [Advisor activity audit](advisor_activity_audit.md) | Activity/detention evidence and stacking semantics |
| [Development notes](development-notes.md) | Condensed completed work and unresolved acceptance items |
| [Module catalog](reference/module_catalog.md) | Generated hab-module table |
| [Research catalog](reference/research_catalog.md) | Generated research dependency table |

Keep one authoritative document per subject. Put user instructions in `docs/`,
current engineering contracts here, and new active implementation plans in
`dev-docs/plan/<topic>/`. On completion, remove phase logs after moving lasting
decisions into the appropriate reference; add a short development note only when
the historical context remains useful. Git preserves detailed work history.
Generated tables are rebuilt by their generators, never edited by hand.
