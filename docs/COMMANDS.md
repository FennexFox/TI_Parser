# Command guide

The CLI reads one local Terra Invicta `.gz` save. Put global options before the
subcommand; `--allow-unverified` is also accepted by calculation commands.

```powershell
python .\tools\ti_save_parser.py --save "C:\path\campaign.gz" inspect-save
python .\tools\ti_save_parser.py --save "C:\path\campaign.gz" analyze
python .\tools\ti_save_parser.py --save "C:\path\campaign.gz" --allow-unverified topbar --details
```

Use a positional name or `--entity-id` for a primary subject, never both.
Projection plans use `--plan-file` and comma-separated `--checkpoints` on the
CLI. For Python arguments and result envelopes, see [API.md](API.md).

## Command comparison

| Command | What it reports | Heuristics and limits |
| --- | --- | --- |
| `inspect-save` | Saved date, scenario, version, campaign, player evidence, and compatibility. | Observed facts only; it does not calculate UI values. |
| `analyze` | Bounded bootstrap context and available analysis routes. | Context aid, not a dashboard, history, save diff, or final strategic recommendation. May return a usable incomplete/deferred report. |
| `capabilities` | Machine-readable analysis IDs, argument defaults, and routing classes. | Does not require a save. |
| `summary`, `faction`, `nation`, `councilor` | Compact save summaries and entity views. | Councilor base plus unconditional trait/active-org modifiers are capped at 25; conditional effects require a target nation or current-location context. |
| `topbar` | Resource stockpiles/income, research distribution, MC, and CP maintenance; optionally queue and resource forecasts. | Current operating values stay distinct from queued MC. A forecast with negative hab power is incomplete. |
| `research`, `advise` | Research income breakdown; or one hypothetical councilor Advise contribution. | `advise` reports the direct source increase and the final increase after research-distribution bonuses. |
| `research-ui` | Active global/project slots, weights, progress, contributions, and ETA. | Slots 6+ are paused/stored progress, not active project slots. |
| `research-plan` | Candidate global techs/projects with costs, ETA, synergy, unlocks, deficiencies, and progress. | Goal-specific score views preserve evidence; the command does not choose a final strategic utility ranking. |
| `org-plan` | Councilor goal views and a committee assignment/acquisition sequence. | Includes owned unassigned orgs unless `--market-only`; uses bounded beam search, so larger `--max-actions`/`--beam-width` broaden a slower search. Candidate inventory is not itself a recommendation list. |
| `hab-ui`, `hab-slots` | Hab display values and currently usable empty slots. | Locked future-sector placeholders are not currently buildable slots. `hab-slots` defaults to player habs and omits empty-less habs unless `--all`. |
| `hab-plan` | Buildable module and core-upgrade candidates with costs, timing, deltas, and focus scores. | A shortlist heuristic, not a full optimizer. `research` means monthly Research; Projects and category bonuses are separate. Focus scores charge slot opportunity cost; combat/objective-only modules are excluded. |
| `ship-plan` | Unlocked components, role-focused shortlists, and saved-design non-combat simulation. | Simulates mass, acceleration, delta-v, power/heat, resources, shipyard time, MC, and upkeep; excludes combat performance. Rankings are comparison proxies, not combat or transfer simulations. `--design` inspects one design; obsolete parts require `--include-obsolete`. |
| `project-analysis` | Available/stored project evidence, resource tradeoffs, and unlocked-module samples. | Samples assume project completion and try 1/2/4 modules in the best current hab. They do not schedule a global construction queue, reserve support power, or enforce MC across hypothetical builds. |
| `world-ui`, `nation-ui` | World population/environment/markets/wars, or nation panel values and CP priorities. | Priority validity is tri-state; missing inputs remain unknown rather than becoming false. |
| `nation-claims` | Peaceful, statically hostile, and democracy-conditional hostile claims. | Reports the strict democracy threshold with evidence. Claim permanence and succession after annexation/unification/independence remain unknown unless evidenced. |
| `nation-projection` | Conditional CP priorities and Advisor policies over a requested period. | See [Projection semantics](#projection-semantics); unsupported next actions stop before mutation. |
| `ai-fleet-diagnostics` | Supported AI goals, fleets, ships, habs, shipyards, queues, and resource/MC evidence. | Separates observed, derived, suspected, and unknown facts. An empty queue is not evidence of a resource shortage; stale suspicion is only added when `--stale-days` is supplied. |
| `raw`, `types` | Selected raw save fields or gamestate type counts. | Inspection tools; they do not require calculation consent. |
| `export`, `cache` | Export or build/validate a compact calculated snapshot cache. | Calculations require compatibility consent; cache identity includes save metadata and packaged catalog bytes. |
| `catalog-verify` | Audit packaged catalog data against explicit game templates and optional save checks. | Source-checkout command only; requires `--templates-dir`. Templates are never a runtime fallback. |

Faction-scoped commands identify the human faction from `TIPlayerState.isAI == false`
and cross-check `TIMetadataState.playerFactionName`. Missing, ambiguous, or
conflicting evidence stops default resolution; an explicit faction argument or
`--faction` is an override.

For `org-plan`, `candidateSources` is diagnostic inventory;
`recommendationEligibility` is derived from each org's `eligibleCouncilors`, while
actionable views are in `councilors.goalViews` and `committeePlan`. For
`hab-plan`, planned locked slots count only when an active core upgrade will
unlock them. Location-adjusted cost/time includes gravity, solar-mirror
distance, irradiated-location metals, the two-thirds module-upgrade discount,
eligible water-for-fissiles substitution, construction speed, and any wait for
the current core upgrade. Farm-style modules can show negative support when
they reduce existing crew upkeep.

## Compatibility and failure behavior

The initial compatibility registry has no verified tuples. Calculation commands,
including legacy summaries, export, and cache, require verified compatibility or
per-invocation `--allow-unverified`. Raw/type inspection and capabilities do not.
Opt-in does not waive unsupported mechanics, missing required references,
missing dependencies, or catalog integrity failures.

Normal calculation commands use packaged catalogs under `data/`; they do not
read an installed game template tree or `Assembly-CSharp.dll`. An unresolved
required effect, trait, applying org, active hab module/body location, weighted
research row, saved ship component, or packaged shipyard is reported as
incomplete with structured missing-dependency evidence. Valid absence—such as
an empty optional ship slot—remains valid and does not require a catalog row.

Expected input or incomplete-calculation outcomes use JSON and exit code 2;
unexpected internal errors use exit code 1. `analyze` can return useful JSON
with code 2 when work is deferred or incomplete. `catalog-verify` returns 0
only when all requested checks pass; failed or unavailable checks preserve a
detailed partial/failed report with code 2.

## Planning guidance

Treat scores and candidate lists as auditable decision evidence. `hab-plan`,
`research-plan`, `project-analysis`, and `ship-plan` expose their inputs and
shortlist axes; they do not make a final campaign decision. The parser preserves
source facts, calculated values, assumptions, expected values, and unknowns as
separate evidence. Missing or unsupported information is not converted into a
plausible zero or guessed constant.

## Projection semantics

`nation-projection` does not mutate the loaded save. Completed, verified
transactions remain authoritative; if the next action or a newly activated
dependency is unsupported, that mutation is not executed and the affected path
becomes incomplete. An independent missing Economy, BuildArmy, or BuildNavy
market value can leave nation/faction scopes complete while marking only the
world-market scope incomplete. Coverage follows the inputs and outputs actually
executed, so a rule existing in code does not make downstream metrics exact.

Segment conditions are evaluated after a complete investment or verified
periodic transaction, and a satisfied segment applies immediately before the
next investment tick. `nation.*` metrics describe the target nation;
`factionContribution.*` metrics describe only the selected faction's share.
Advisor placement is a desired repeat-order policy: the projection clears
active advisors at each mission phase and reapplies them at the audited expected
order-0 resolution time. Advise succeeds automatically and `MoveToTarget` moves
on assignment, so modeled travel time is zero. Future resource availability,
target invalidation, detention, and competing orders are held fixed.

Monthly cohesion uses a live resting target after supported democracy changes;
unrest recomputes its live target after cohesion changes. Serialized clamped
rest caches are not inverted to guess source inputs. Missing required source
state, low-cohesion stochastic democracy and nonzero surveillance-abduction
branches stop before the unsupported mutation. Priority validity uses the
current DLL's cached gates and capabilities; unavailable inputs remain unknown.

Unity requires the explicit plan opt-in
`stochasticPolicy.unityPublicOpinion: "meanPath"`. Population uses deterministic
mean inputs; Unity uses sequential conditional expected transitions. Both can
report `coverage: expected` and `expectationGuarantee: false`: neither claims to
equal the mathematical expectation of the full nonlinear stochastic path.
Unsupported priorities are excluded from comparison/ranking, but the already
completed prefix and its CP cache repairs remain authoritative. Diagnostics
identify the stop point, attempted action, affected metrics, and last
authoritative state. See the source-checkout projection audit for mechanics
provenance and detailed validation boundaries.
