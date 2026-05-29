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
python .\tools\ti_save_parser.py nation-ui "유럽 연합"
python .\tools\ti_save_parser.py hab-ui "제303기초연구단"
python .\tools\ti_save_parser.py hab-slots --faction ResistCouncil
python .\tools\ti_save_parser.py hab-plan --upgrading-to-tier 3 --focus research
python .\tools\ti_save_parser.py project-analysis --top 10 --sort research-sustainable
python .\tools\ti_save_parser.py research --details
python .\tools\ti_save_parser.py research-ui
python .\tools\ti_save_parser.py topbar --details
python .\tools\build_research_catalog.py
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

The `topbar` command reconstructs the top resource bar from the save, including
current stockpiles, monthly/yearly net resource income, research distribution,
mission-control usage/capacity, and control-point maintenance usage/cap.

The module catalog generator reads hab module templates from the local Terra
Invicta install and writes `data/module_catalog.json` plus
`docs/module_catalog.md`. Use the JSON for optimizer inputs; the Markdown is a
human-readable reference for module income, upkeep, crew, power, MC, CP cap,
build cost, requirements, and derived tags.

The research catalog generator reads global tech and faction project templates
from the local Terra Invicta install and writes `data/research_catalog.json`
plus `docs/research_catalog.md`. The JSON stores research prerequisites as
explicit `all`/`any` boolean trees, plus derived graph indexes such as `edges`
and `childrenByPrereq`. Save-specific completion, objectives, milestones,
faction gates, and nation gates should be evaluated against that static catalog
rather than baked into it.

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
resource/research deltas. Candidate rows and suggested fills include slot
opportunity costs: for each focus, the best affordable candidate's score is
treated as the per-slot alternative value, and selected modules are charged for
the focus score they give up. If every candidate is non-positive for that
focus, the alternative value is zero. Locked placeholder slots are only
included in `plannedEmpty` when the current core module is actively upgrading
to a higher tier that will unlock those sectors.

`hab-plan` is intentionally not a full optimizer yet. It uses template build
material weights rather than exact location-adjusted costs, filters out combat
and objective-only modules for the economic planning view, and should be treated
as a shortlist generator before committing construction in-game.
Candidate monthly deltas are calculated by comparing the whole hab before and
after a hypothetical completed module. For farm-style modules, negative support
means reduced existing crew upkeep rather than resource production.

The `project-analysis` command ranks available and stored faction projects on
multiple transparent heuristic axes instead of choosing a final answer. It
combines the current research slot model, active resource bottlenecks, direct
project effects/resource grants, and hab modules that a project would unlock.
Unlocked-module samples pretend the project is complete, scan current/planned
empty hab slots, and report 1/2/4-module effects using the best current hab
option. Treat those samples as LLM/human decision inputs: they do not solve the
global construction queue, reserve power-support modules, or enforce global MC
across every hypothetical build.
