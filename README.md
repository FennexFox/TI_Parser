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
python .\tools\ti_save_parser.py research --details
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

The `nation-ui` command reconstructs the nation panel values used for UI
validation, including federation-pooled funding/boost income, faction research
share, control-point priority weights, accumulated investment points, public
opinion, army/navy limits, nukes, and diplomacy lists.

The `hab-ui` command reconstructs a hab panel from raw sector/module state and
module templates, including crew, power, monthly net resources, research
category bonuses, Earth LEO priority bonuses, and construction modifiers.
