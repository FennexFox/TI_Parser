# Architecture

The parser loads a save, indexes references, and computes domain results using
packaged catalogs. Normal operation never discovers an installed game.

| Boundary | Owning modules under `tools/` |
| --- | --- |
| Save loading, indexing, references | `ti_parser_core` |
| Compact snapshot and atomic cache | `ti_parser_snapshot` |
| Catalog validation, manifest, scenario selection | `ti_parser_catalogs` |
| Shared settings and runtime adapters | `ti_parser_config`, `ti_parser_runtime` |
| Income and organizations | `ti_parser_income`, `ti_parser_org` |
| Hab mechanics, UI, construction, planning | `ti_parser_hab`, `ti_parser_hab_ui`, `ti_parser_hab_construction`, `ti_parser_hab_plan` |
| Research and project planning | `ti_parser_research`, `ti_parser_research_plan`, `ti_parser_project_analysis` |
| Ship helpers and saved-design simulation | `ti_parser_ship`, `ti_parser_ship_plan` |
| Resource aggregation and forecasts | `ti_parser_topbar` |
| World and nation UI | `ti_parser_world`, `ti_parser_nation_ui` |
| Projection extraction and transactions | `ti_parser_projection_adapter`, `ti_parser_nation_projection` |
| Mechanics provenance, validity, executed coverage | `ti_parser_mechanics`, `ti_parser_nation_validity`, `ti_parser_projection_coverage` |
| Analysis IDs, arguments, dispatch | `ti_parser_registry`, `ti_parser_application` |
| Fair-play exposure, sanitized inspection, cross-tool save correlation | `ti_parser_registry`, `ti_parser_fairplay` |
| One-save session and result envelopes | `ti_parser_session`, `ti_parser_schema` |
| Bootstrap and capability inventory | `ti_parser_analysis`, `ti_parser_capabilities` |
| CLI parsing and rendering | `ti_parser_cli`, `ti_parser_commands` |
| Public entry point and compatibility exports | `ti_save_parser` |
| Compatibility, expected errors, version | `ti_parser_compatibility`, `ti_parser_errors`, `ti_parser_version` |
| Optional stdio transport | `ti_parser_mcp` |

Domain dependencies are direct and acyclic; domain modules do not import the
public facade. Patch dependencies where they are used in tests, rather than
rebinding facade exports. Existing exported function names/signatures remain
compatibility boundaries.

Snapshot caching is keyed by save path, size, mtime, and packaged catalog bytes.
Cache hits validate current runtime data; malformed entries rebuild and completed
files replace prior entries atomically. This cache key is distinct from the
content-based public `saveIdentity` described in [the API](../docs/API.md).

Expected input/dependency errors stay structured. Unsupported mechanics and
unknown identity or validity cannot become guessed values. Projection works on
cloned state, retains verified transaction prefixes, and derives metric coverage
from actual reads/writes. See the [mechanics audit](nation_projection_mechanics_audit.md)
before changing simulation semantics or provenance.
