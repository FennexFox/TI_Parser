# Fair-play interoperability audit

This source-checkout reference records the Issue #8 profile boundary and the
evidence required before fair-play routing can be accepted with a companion MCP
and Codex-side server. It does not claim that the external two-server test has
run.

## Policy decision

`--profile default|fair-play` is the profile choice. `default` remains the
default and retains the existing route behavior. The initial `fair-play`
allowlist is intentionally small:

| Route | `default` | Initial `fair-play` | Reason |
| --- | --- | --- | --- |
| `inspect-save` | Existing behavior | Allowed | Reports observed save identity and compatibility evidence without calculating UI values. |
| `capabilities` | Existing behavior | Allowed | Fair-play inventory lists only `inspect-save`. |
| `nation-projection` | Existing behavior, subject to current compatibility/dependency gates | Blocked for every caller | Its visibility dependencies have not been proven authoritative and complete. |
| Every other route | Existing behavior | Excluded | No route has yet passed the profile's source-read and information-flow audit. |

This is a route gate, not output filtering. A result scrubber cannot undo
information already read or derived. In particular, `nation-projection`
extracts the target nation, control points and owners, advisor profiles,
owner/faction bonuses, relevant regions, and global development inputs; its
simulator can apply effects to public opinion, global market values, region
state, and faction contributions. The current audit does not establish that
all inputs and downstream reads are limited to information visible to the
human faction, nor that visibility remains bounded for every priority and
random/expected branch. Therefore the whole route stays unavailable under
`fair-play`, including when a caller requests only a subset of output metrics.

| Input/read evidence | Parser behavior | Visibility status |
| --- | --- | --- |
| Caller-selected target and faction (`handle_nation_projection`) | Resolves requested nation/faction, then delegates projection; it does not establish game visibility. | Ownership/visibility is not validated as authoritative. |
| Target CP owners and bonuses (`calculate_nation_projection`, `extract_nation_projection_state`) | Builds owner-specific profiles and bonuses for multiple owners. | Cross-faction visibility is unresolved. |
| Nation public opinion and region state | Extracts public opinion, population, and regions and applies priority/periodic transitions. | Availability to the player is not proven by save presence. |
| Global resource markets and faction effects | Extracts market values and calculates effects/contributions across owners. | Global and faction-level visibility is unresolved. |
| Projection snapshots and diagnostics (`_state_snapshot`, `projection_output`) | Returns state snapshots, metrics, coverage, execution diagnostics, and missing inputs. | Output allowlisting cannot repair prior unapproved reads. |

Relevant implementation entry points are `handle_nation_projection` in
`tools/ti_parser_application.py`, `calculate_nation_projection` and
`extract_nation_projection_state` in `tools/ti_parser_projection_adapter.py`,
and `_state_snapshot` plus `projection_output` in
`tools/ti_parser_nation_projection.py`. Save/parser evidence establishes what
is read and emitted; DLL/template evidence and an authoritative visibility
model are still needed to classify what the player may know. Scenario
assumptions must remain separate from that evidence.

| Evidence layer | Current evidence | What it establishes |
| --- | --- | --- |
| Save/parser | `handle_nation_projection` (`ti_parser_application.py:464`), `extract_nation_projection_state` (`ti_parser_projection_adapter.py:565`), `calculate_nation_projection` (`:953`), `_state_snapshot` (`ti_parser_nation_projection.py:2187`), `projection_output` (`:3839`) | Which save fields, factions, CP owners, public-opinion/market values, regions, and output diagnostics the implementation can read or produce. |
| DLL/templates | No issue-specific visibility trace for these source reads | Authoritative player visibility remains unknown. Parser state presence does not establish what the player can see. |
| Scenario assumptions | A fully player-owned nation, candidate plans A/B, 180-day horizon | Defines the requested smoke scenario; it does not establish mechanics parity or information visibility. |

## Registry inventory audit

The analysis registry in `tools/ti_parser_registry.py` is the source of truth
for route IDs and routing classes. Current entries group as follows:

| Registry category | Route IDs | Initial `fair-play` decision |
| --- | --- | --- |
| Bootstrap | `inspect-save`, `analyze` | Allow only `inspect-save`; `analyze` includes campaign context and is excluded. |
| Primary reconstructed state | `summary`, `faction`, `nation`, `councilor`, `topbar`, `research`, `research-ui`, `nation-ui`, `nation-claims`, `world-ui`, `hab-ui`, `hab-slots` | Exclude pending route-by-route visibility review. |
| Primary planning evidence | `research-plan`, `org-plan`, `hab-plan`, `ship-plan`, `project-analysis` | Exclude; candidate inventories and simulations can expose derived or cross-entity context. |
| Primary simulations | `nation-projection`, `advise` | Exclude; `nation-projection` is explicitly globally blocked pending its visibility audit. |
| Diagnostic | `ai-fleet-diagnostics` | Exclude; it intentionally inspects AI goals and unresolved causes. |
| Advanced observed state | `raw`, `types` | Exclude; raw selected fields and type counts are broader than the safe identity contract. |
| Maintenance | `export`, `cache`, `catalog-verify` | Exclude; they are not fair-play interaction routes. |
| Inventory | `capabilities` | Allow; fair-play inventory lists only `inspect-save`. |

The fair-play inventory lists only `inspect-save`. The runtime profile must
reject an excluded route before calling its analysis handler; checking response
fields after execution is insufficient.

| Request intent | Routing decision | Expected result |
| --- | --- | --- |
| Companion current-state request | Companion MCP | Companion may report its own current-state evidence. |
| Pinned-save identity/compatibility request | TI Parser fair-play `inspect-save` | Sanitized identity and compatibility envelope. |
| Plans A/B for a fully player-owned nation over 180 days | TI Parser fair-play `nation-projection` | Blocked before projection extraction. |
| Companion state plus TI projection request | Companion MCP for state; TI Parser fair-play for projection | Companion evidence may be returned; TI prediction remains blocked. No default-profile retry. |
| Excluded route or hidden alias | TI Parser fair-play | Generic denial before handler execution; no analysis payload. |

## Save identity and peer matching

Use `inspect-save` from each server and compare the public `saveIdentity`.
For exact matching, require schema version 1 on both sides and the same
supported fingerprint algorithm/value. The exact fingerprint is
`sha256-canonical-save-json-v1`:
serialize the parsed save with Python JSON options `ensure_ascii=False`,
`sort_keys=True`, `separators=(",", ":")`, and `allow_nan=True`; encode as
UTF-8 and SHA-256 those bytes. Bare `NaN`, `Infinity`, and `-Infinity` tokens
remain bare during hashing. The serialization is project-defined, not RFC
canonical JSON. It is independent of file path, modification time, gzip
compression, whitespace, and object-key order when parsed content is equal.
See [API save identity](../docs/API.md#save-identity) for the public fields.

For provisional comparison, allow a weak match only if an exact fingerprint
is unavailable because its algorithm is unknown (a present supported algorithm
with an invalid digest is rejected), the save is pinned, and every component
below is present and equal on both sides:

- The pinned save's campaign identity (`campaign.realWorldCampaignStart`).
- `gameDate`.
- A resolved player faction ID and template (`playerFaction.id` and
  `playerFaction.template`). Display name is not an identity key.
- The selected nation ID.

Reject matching if any component is missing, unresolved, or changes between
observations. Reject a mismatch; do not fall back from an exact fingerprint
mismatch to the weak fields. Weak fields can collide across different saves,
so this provisional comparison is for detecting obvious disagreement only and
must not be represented as exact save identity. Weak comparison is never a
fallback after a fingerprint mismatch. The Python helper is not exposed as an
MCP tool, and the approved `inspect-save` route does not expose a selected
nation ID. An MCP-only comparison must mark that field unresolved unless
another authoritative approved source provides it; never use `raw` under
fair-play to bridge the gap.

## Reproducible 180-day A/B prompt

Use the Companion MCP's current state for a fully player-owned nation and
prepare two candidate priority plans, A and B, for a 180-day comparison. Ask:

> Use the Companion MCP's current state for the fully player-owned nation and
> compare candidate priority plans A and B over the next 180 days. First
> compare its save context with TI Parser using the pinned campaign, game date,
> resolved player faction, and selected nation identity. State which identity
> fields match and mark any field unavailable through the allowed TI tools as
> unresolved. Ask TI Parser for a nation projection through its fair-play
> profile. Do not advance or modify the save.

Expected result: TI Parser reports safe identity and compatibility and blocks
`nation-projection`. Its fair-play capabilities inventory lists only
`inspect-save`. It must not return projected values or a partial projection.
Do not switch to the default profile or a second TI server to work around the
block. Record any unresolved selected nation ID and the explicit blocked
outcome. Companion state does not establish TI projection visibility or
accuracy.

The companion server configuration remains product-specific; no companion
launch command is invented here.

## Acceptance gates and current status

| Gate | Status | Evidence still required |
| --- | --- | --- |
| Default profile preserves route behavior | Verified by coordinator; 60 focused tests passed | Omitted profile and explicit `default` retain existing behavior. |
| Fair-play allowlist and pre-handler denial | Verified by coordinator; 60 focused tests passed | Fair-play analysis route is only `inspect-save`; capabilities lists only that route. Projection and all other routes are denied. |
| Exact and provisional save matching | Verified by coordinator; 60 focused tests passed | Exact schema-1 supported fingerprints and context must match. Missing/invalid/change rejects; unavailable fingerprint allows only pinned and complete equal context. |
| Projection visibility audit | Open; projection remains blocked | Parser source traces are recorded above. Authoritative DLL/template visibility classification across branches and cross-scope reads is not established. |
| Companion MCP plus Codex-side server | Not run; external acceptance pending | Requires the actual Companion MCP and Codex-side integration. Run the 180-day A/B prompt with the same pinned save; retain tool/result evidence without sensitive save data. |

The local profile implementation and regression checks pass, but this does not
complete the actual Companion MCP/Codex two-server acceptance. Keep that gate
open and keep projection blocked until authoritative visibility evidence is
complete. This repository task had no access to the actual Companion MCP or a
configured Codex two-server session.
