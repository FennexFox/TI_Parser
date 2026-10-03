# Fair-play interoperability audit

This source-checkout reference records the Issue #8 profile boundary and the
evidence required before fair-play routing can be accepted with a companion MCP
and Codex-side server. Test-only two-server probes and real Codex CLI routing
are separate from acceptance using the actual Companion.

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

## Structural audit and authoritative acceptance are separate

The bounded fixture is ModernScenario, a fully player-owned nation, 180 days,
single-segment Knowledge/Welfare 3:1 and 1:3 plans, explicitly empty advisors,
and no diagnostic output. The canonical audit checkpoints are `[0, 180]`: the
initial state and the 180-day result. Intermediate checkpoints `[30, 90, 180]`
are outside this canonical execution shape and require a separate audit.
These pips are acceptance fixtures. They are not a
production contract or permission to classify the whole route as own-subject.

The developer-only `tools/audit_projection_reads.py` records source paths and
read operations across preparation, simulation, and output. Dynamic logs must
be reconciled with static call/branch closure. `dict`, `list`, comprehensions,
copy/deepcopy, index aliases and helper normalization can lose provenance after
materializing plain containers/scalars. An unexplained escape, unreached stage,
or static/dynamic discrepancy makes the audit incomplete. No hidden read in the
log is not proof that no hidden input influenced the result. Existing metric
coverage records calculated lineage, not complete raw read visibility.

Original/traced result, status and coverage parity is required before relying
on instrumentation. Unrelated preparation must not be omitted merely because
the fixture has empty advisors: current preparation scans councilors and
cross-faction effects. Any scoped optimization requires separate parity tests
and does not establish game visibility.

The controlled six-CP fixture completes both 180-day plans with exact
baseline/traced result, coverage and status parity. The bounded trace records
save/catalog payload reads across preparation and execution.
Empty advisors still execute `councilor_summary_maps`,
`projection_advisor_profiles` and `calculate_topbar`; no preparation was removed.
Catalog decoding/manifest checks, plain index-container reads and remaining
normalized scalar mappings are explicitly unresolved, so structural status is `incomplete`.
All raw read visibility classifications remain unresolved. Reproduce the
offline report from a source checkout with an explicit output path:

```powershell
python tools/audit_projection_reads.py --output C:\path\to\audit.json --assembly-path C:\path\to\Assembly-CSharp.dll
```

Exit 2 is the current fail-closed result, even though fixture calculation
parity passes. The report separates `structuralStatus`,
`buildSourceAuthorityStatus`, `visibilityStatus`, and `policyEligibility`.
The historical `authorityStatus.assemblyHashComparison` remains a build hash
observation, not an approval. Exit 0 requires explicit acceptance of every
eligibility gate; absent assembly/source hashes, mismatch, unresolved build
applicability or unresolved visibility cannot pass. Matching hashes alone
would still not establish UI visibility.

### Source-to-derived dependency closure

The developer-only `tools/projection_audit_dependencies.py` inventories
source locations and hashes in observed parser consumers. The report records
source pattern, runtime consumer and ordered call path, destination/role,
evidence layer, visibility category, build applicability and blocking status.
Parser AST wiring establishes structural mappings only; game visibility
requires separately applicable DLL/UI/template evidence.

| Source in `extract_nation_projection_state` | Verified parser destination | Visibility |
| --- | --- | --- |
| `controlPointPriorities` | `ControlPointProjectionState.pips` | Unresolved |
| `diversityBonus` | `ControlPointProjectionState.diversity_bonus_cache` | Unresolved |
| `_accumulatedInvestmentPoints` | `NationProjectionState.progress` | Unresolved |
| `publicOpinion` | `NationProjectionState.public_opinion` | Unresolved |
| `resourceMarketValues` | `NationProjectionState.world_context.resourceMarketValues` | Unresolved |

These assignment/constructor chains are mapped; descendants, helper internals
and other consumers are not implicitly covered. Dynamic reads are explicitly
reconciled with static candidates. Unmapped reads, unobserved static candidates,
ambiguous consumers or unexplained materialization boundaries keep closure
incomplete. New or unclassified dependencies invalidate completeness.
Regions, faction effects, councilor/faction preparation, catalog source loading,
index containers, output and coverage remain in the blocking inventory rather
than being silently ignored.

Accepted visibility evidence must cover the exact required dependency IDs and
scope fingerprint, bind each record to the supplied and packaged source hashes,
and carry explicit evidence references. A boolean claiming all dependencies
are classified cannot hide missing, duplicate, extra or foreign-build records.
The current CLI supplies no accepted evidence packet and offers no approval
flag. Its live visibility records remain unresolved; unit acceptance packets
exercise the decision contract and are not game evidence.

The current installed and packaged nation-development source DLL both have
SHA-256 `4a4b9aae4154e444e9727204205d2d42ae8ed9e1c5f92cdc1280074a259d8350`.
The previous packaged source was
`ff7916c2085ddbafa5acf1e8ea185d37e629096752be388ba6fa1f627f027bb5`.
The [catalog refresh](catalogs.md) resolves this stale-source mismatch; explicit
live assembly comparison now reports `match`. Hashing an explicitly supplied
assembly remains an offline audit input only. Normal runtime never discovers
an installed DLL, and capabilities report `authorityHashStatus: not_evaluated`
rather than claiming an installed-build comparison.

The refreshed canonical A/B calculations have identical complete results to
the previous baseline, including status and coverage. Baseline/traced parity
also passes. The earlier source audit remained incomplete: 457 of its 496 recorded read
paths are unresolved in static/dynamic reconciliation, and unexplained
normalization/materialization boundaries remain. Visibility is unresolved;
no accepted evidence packet is supplied. Overall policy eligibility remains
`not_approved` and the audit returns exit 2 even when the DLL hashes match.

Catalog validity is resolved separately from complete projection mechanics
acceptance. Only the explicitly reviewed Knowledge/Welfare rules have current
build evidence; other [mechanics rules](nation_projection_mechanics_audit.md)
retain their historical source hashes. Required hidden or unresolved reads,
unreviewed rules and incomplete dependency closure remain blockers.

The audit report's `acceptanceBinding.scopeFingerprint` binds the catalog bundle
and package file hashes, exact scenario/execution shape, parser inventory/source
hashes and required dependency IDs. The existing visibility scope comparison
rejects packets issued for a different binding. Catalog updates, new reads,
parser changes and different shapes invalidate the old scope even if the DLL
hash is unchanged. This is an audit decision primitive, not runtime approval.

## Bounded execution closure and current-build findings

The developer audit now records target-resolution preflight separately from
A/B preparation, calculation and output reads. Each trial captures existing
`ruleExecutions` before public output filtering, without enabling details or
changing calculator inputs. Both trials observe 12 executed rule IDs and 16
runtime dependency-closure IDs. This is an observed graph, not a completed
source or mechanics closure.

Four declared dependencies have no separate execution record: base IP, annual
population growth and monthly cohesion/unrest. The Welfare-to-inequality edge
is recorded dynamically but its append-based source declaration is not yet
reconciled by the literal-edge scanner. These are instrumentation/reconciliation
blockers, not proof that the game rules are absent or unknown. Static references
inside observed functions retain branch context and source locations; references
to unexecuted branches remain candidates until exclusions and influence are
proved. No candidate is approved merely because the trace did not execute it.

[Scoped execution evidence](projection_execution_evidence.json) records current-
DLL mechanics and UI findings. Parser reference hashes use `sha256-utf8-lf`;
normalizing checkout CRLF/LF preserves source evidence across Git exports.
Other source edits and DLL changes mark findings stale. The report includes
`currentBuildReview` and binds the evidence artifact bytes through the execution
closure fingerprint. Missing/stale findings cannot establish permission, and
this supplement is never an accepted policy packet.

Decisive mechanics blockers include monthly movement reading live
`cohesionRestState`/`unrestRestState` in the DLL while the parser uses prior daily
cache values; non-invertible calibration from clamped rest caches; diversity
bonus gating differences; and unclosed current validity, faction/effect and
army dependencies. Arithmetic agreement in a positive-bonus fixture does not
verify the broad rule contract. Historical registry evidence remains historical;
no further source hashes or rule statuses were rebound on this review.

Decisive visibility blockers include exact regional `xenoformingLevel`, whose
`VisibleToFaction` predicate requires intel below stage 3 and does not grant an
ownership bypass; saved `annualPopGrowthModifier`; raw GDP-history tracker and
rest caches; and unconditional councilor, mission, faction-effect and topbar
preparation. UI annual growth/rest values are aggregates, not proof of all raw
constituents. National statistics and progress have formatted-value evidence;
arbitrary saved precision remains unresolved. Owned CP pips have discrete UI
evidence. Welfare's selected next colony counter has conditional UI exposure,
so counters must not be blanket-labelled hidden; other counters and pre-branch
reads still require closure.

The synthetic fixture is source-read/parity evidence, not a runnable-game oracle.
For example, its empty PCGDP history does not satisfy the inspected DLL getter's
history maximum precondition. Held-fixed regional/world assumptions and the
parser's scoped monthly subset cannot establish whole-game monthly parity.

No production input predicate is proved. A/B pips remain fixtures. With
structural, mechanics and visibility gates incomplete, guarded execution and
public profile contracts remain unchanged. Actual Companion acceptance stays
open independently of these internal blockers.

## Future guarded policy boundary

`fair-play-projection-v1` is a pending policy identity, not an enabled tool.
Only after structural completeness and authoritative acceptance both pass can
the registry assign own-subject classification together with this application-
owned policy. Its scope must bind approved scenario/catalog evidence, complete
ownership, horizon, single segment, empty advisors, approved priorities and
execution shape. Values outside a fixture may be accepted only when their
read/branch/completion/output closure is proven; fixture success cannot establish
a broad domain. Diagnostics, unresolved ownership/dependencies and unapproved
shapes remain denied. `allow_unverified` never bypasses any of these gates.

The current route stays visibility-dependent and globally blocked. No unused
alternate calculator or fabricated successful prediction is introduced while
the authority gate remains open.

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

Save identity and subject identity are separate. `inspect-save` and
reinspection remain save-only. The private application subject operation
resolves the strict player and selected nation, verifies every declared CP's
count/type/nation/owner, computes through `AnalysisSession.run`, and issues an
opaque process-local receipt sealing the exact result object, its full content,
resolved nation and save identity. `validate_advice_generation` requires this
receipt and matches its nation against both response-bound Companion contexts.
Caller JSON IDs, copied/changed results and receipts for another result reject.

This receipt proves source/subject correlation, not approved mechanics or
visibility. Its issuance tests use a real synthetic save session and packaged
projection; it is not a fabricated inspection envelope. The existing
`run_profile` admission owner still denies fair-play projection, including
when policy metadata or `allow_unverified` is changed. No new MCP-only policy
or tool is introduced. Receipt validation occurs within the issuer process;
it is not a serialized attestation protocol for external clients. Future
guarded admission and transport must preserve this application boundary.

Read Companion's response-bound context identity, then TI `inspect-save`, and
compare the public `saveIdentity`.
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
| Default profile preserves route behavior | Regression-tested | Omitted profile and explicit `default` retain existing behavior. |
| Fair-play allowlist and pre-handler denial | Regression-tested | Only identity inspection is exposed; projection and other routes are denied before save reads. Capabilities identify the pending disabled guard. |
| Exact/provisional matching and generation checks | Regression-tested | Save-only inspection/reinspection fingerprints and the application-issued projection subject receipt must agree with bound peer targets. Weak peer identity remains provisional; no public guarded projection/receipt is currently available. |
| Structural read completeness | Open | A/B result/status/coverage parity alone does not establish complete tracing. Materialized values, catalog loading and static dependency closure require explicit mappings. |
| Current-build catalog/source comparison | Matched | Regenerated baseline and explicit installed DLL hashes match; normalized changes were reviewed. |
| Authoritative visibility/correctness | Blocked | Hash equality does not certify all mechanics or player visibility; rule-specific review and dependency closure remain incomplete. |
| Mock Companion plus TI stdio | Protocol-tested | Synthetic fixture-only connection, discovery, policy denial and correlation; not a visibility oracle. |
| Real Codex routing with mock | Six canonical prompts reviewed | Current/history use Companion, correlation uses both with target unresolved, forecasts stay blocked, and hidden goals are refused without calls. [Synthetic client evidence](plan/issue_8/routing-evidence.json) records initial failures and corrected ownership; no mechanics approval follows. |
| Actual Companion plus TI/Codex | Open | Substitute a runnable actual Companion (local branch/server is sufficient) and execute the approved 180-day A/B scenario. |

Local tooling does not complete Issue #8. Keep projection blocked until
structural completeness, authoritative visibility/correctness and the guarded
execution policy pass; actual Companion/TI/Codex prediction acceptance then
remains required. See the [active plan](plan/issue_8/00-master-plan.md) for open
gates and the [MCP runbook](../docs/MCP_SETUP.md#generation-sequence-and-advice-eligibility)
for the required observation sequence and discard/retry behavior.
