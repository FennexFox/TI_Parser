# Terra Invicta Save Parser

Small local parser for Terra Invicta `.gz` saves. It reads the full save once,
builds a compact indexed snapshot, and reuses a cache keyed by save path, size,
and modification time.

Examples:

```powershell
python .\tools\ti_save_parser.py summary
python .\tools\ti_save_parser.py faction ResistCouncil
python .\tools\ti_save_parser.py nation KOR
python .\tools\ti_save_parser.py councilor Hanna
python .\tools\ti_save_parser.py councilor Hanna --target-nation USA --details
python .\tools\ti_save_parser.py councilor Hanna --current-location-context
python .\tools\ti_save_parser.py org-plan --focus balanced
python .\tools\ti_save_parser.py org-plan --focus science --market-only --top 3
python .\tools\ti_save_parser.py nation-ui "유럽 연합"
python .\tools\ti_save_parser.py hab-ui "제303기초연구단"
python .\tools\ti_save_parser.py hab-slots --faction ResistCouncil
python .\tools\ti_save_parser.py hab-plan --upgrading-to-tier 3 --focus research
python .\tools\ti_save_parser.py research --details
python .\tools\ti_save_parser.py research-ui
python .\tools\ti_save_parser.py research-plan --top 5
python .\tools\ti_save_parser.py topbar --details
python .\tools\build_module_catalog.py
python .\tools\ti_save_parser.py world-ui
python .\tools\ti_save_parser.py advise "Lati Wirya" "중화민국"
python .\tools\ti_save_parser.py types --limit 30
python .\tools\ti_save_parser.py raw --type TIFactionState --template ResistCouncil --keys displayName,resources,baseIncomes_year,missionControlUsage
```

Use global options such as `--save <path>` and `--refresh-cache` before the
subcommand.

Councilor attributes are calculated from save base values plus unconditional
trait and active-org modifiers, then clamped to the game's normal 25 cap.
Conditional trait modifiers are not mixed into `finalAttributes`; use
`--target-nation <name/code>` or `--current-location-context` to get
`contextualAttributes` for a specific situation.

The `org-plan` command evaluates the faction's currently acquirable
`availableOrgs` against every councilor. It reports per-councilor views for
balanced stats and each individual stat, applies the Administration capacity
limit, checks acquisition costs and owner eligibility, and recommends a
committee-wide assignment sequence. Already-owned unassigned orgs are included
by default so useful inventory is assigned before spending resources; pass
`--market-only` to evaluate acquisitions only. The committee plan uses a
bounded beam search with practical defaults; increase `--max-actions` or
`--beam-width` when a slower, broader search is useful.

The `research` command recalculates the UI's daily research tooltip from raw
save values, including councilor trait/org income, CP research effects,
knowledge-sector bonuses, hab efficiency modules, excess MC research, and
research-distribution bonuses. The `advise` command applies one hypothetical
Advise assignment to a nation and reports both the direct source increase and
the final increase after research-distribution bonuses.

The `research-ui` command reconstructs the Research screen's active slots. It
reads the three global techs from `TIGlobalResearchState.techProgress`, active
faction projects from `TIFactionState.currentProjectProgress` slots 3-5, slot
weights from `researchWeights`, category/project-facility modifiers, current
progress, daily slot output, faction contribution bars, and ETA dates. Project
records in slots 6+ are reported separately as paused/stored progress, not as
currently active project research slots.

The `research-plan` command builds an LLM-ready report for the question "what
global tech or faction project should I research next?" It automates objective
candidate collection and evidence shaping: currently active slots, paused
projects, available global techs, available projects, research costs, ETA
estimates at current slot weights, category synergy, downstream unlock counts,
critical template flags, resource-deficiency coverage, and existing progress.
It intentionally does not collapse those signals into a final strategic utility
ranking; the output includes goal-specific score views and source notes so an
LLM can make the value judgment explicitly.

The `topbar` command reconstructs the top resource bar from the save, including
current stockpiles, monthly/yearly net resource income, research distribution,
mission-control usage/capacity, and control-point maintenance usage/cap.

The module catalog generator reads hab module templates from the local Terra
Invicta install and writes `data/module_catalog.json` plus
`docs/module_catalog.md`. Use the JSON for optimizer inputs; the Markdown is a
human-readable reference for module income, upkeep, crew, power, MC, CP cap,
build cost, requirements, and derived tags.

The `world-ui` command reconstructs the Intel screen's world tab values:
population, GDP, global public opinion, resource market prices, environmental
damage, active wars, and faction atrocity counts.

The `nation-ui` command reconstructs the nation panel values used for UI
validation, including federation-pooled funding/boost income, faction research
share, control-point priority weights, accumulated investment points, public
opinion, army/navy limits, nukes, and diplomacy lists.

The `hab-ui` command reconstructs a hab panel from raw sector/module state and
module templates, including crew, power, monthly net resources, research
category bonuses, Earth LEO priority bonuses, construction modifiers, and
`modules.slots` slot accounting. Raw saves can include locked future sector
placeholders with empty module slots; these should not be treated as currently
available build slots.

The `hab-slots` command lists faction habs with currently usable empty slots.
It defaults to the player faction, excludes habs with zero usable empty slots
unless `--all` is passed, and reports raw, usable, occupied, empty, locked, and
locked-empty slot counts for each hab.

The `hab-plan` command is a save-derived planning view for current and future
hab slots. It can scan the player's habs, filter to cores currently upgrading
to a target tier, and rank buildable module candidates for `balanced`,
`research`, `projects`, `category-bonus`, or `resources` focus. `research`
means monthly `Research` output only; `Projects` output and tech category
bonuses are separate score axes and are not silently converted into research.
Its `suggestedFill` output aggregates a transparent heuristic fill plan by
module count and includes projected final power, MC availability, and monthly
resource/research deltas. Locked placeholder slots are only included in
`plannedEmpty` when the current core module is actively upgrading to a higher
tier that will unlock those sectors.

`hab-plan` is intentionally not a full optimizer yet. It uses template build
material weights rather than exact location-adjusted costs, filters out combat
and objective-only modules for the economic planning view, and should be treated
as a shortlist generator before committing construction in-game.
