# Developer documentation

User workflows and public integration contracts live in [docs/](../docs/README.md).
This directory contains maintained engineering references, audit evidence, and
active work. It is excluded from the runtime ZIP.

| Reference | Purpose |
| --- | --- |
| [Architecture](architecture.md) | Module ownership and dependency boundaries |
| [Catalogs and verification](catalogs.md) | Generation, package-only rules, and release checks |
| [Nation projection audit](nation_projection_mechanics_audit.md) | DLL evidence, rule index, coverage, and validation limits |
| [Fair-play interoperability audit](fairplay_interoperability.md) | Profile routing, save matching, projection visibility, and external acceptance gates |
| [Advisor activity audit](advisor_activity_audit.md) | Activity/detention evidence and stacking semantics |
| [Development notes](development-notes.md) | Condensed completed work and unresolved acceptance items |
| [Module catalog](reference/module_catalog.md) | Generated hab-module table |
| [Research catalog](reference/research_catalog.md) | Generated research dependency table |

The repository's [documentation maintenance rules](../AGENTS.md#documentation-maintenance)
define placement, ownership, plan cleanup, and change checks. Use this index to
find maintained references; Git preserves detailed work history.

Active implementation plan: [Issue #8](plan/issue_8/00-master-plan.md).
