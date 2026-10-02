# Terra Invicta Save Parser

TI Parser is a beta, standalone tool for inspecting Terra Invicta `.gz` saves and reconstructing selected UI values, planning evidence, and mechanics. The normal runtime ZIP uses Python 3.11–3.14 and packaged data only; it does not require an installed game, third-party Python packages, or a companion service. Those Python versions are the CI target, not a claim that every platform and account combination has been manually validated.

## Get started

- [한국어 quickstart](docs/QUICKSTART_KO.md)
- [ChatGPT guide](docs/CHATGPT_START.md)
- [Optional local MCP setup](docs/MCP_SETUP.md)
- [Command guide](docs/COMMANDS.md)
- [Python and machine API](docs/API.md)
- [Documentation index](docs/README.md)

```powershell
python .\tools\ti_save_parser.py --version
python .\tools\ti_save_parser.py --save "C:\path\campaign.gz" inspect-save
python .\tools\ti_save_parser.py --save "C:\path\campaign.gz" analyze
```

`analyze` creates bounded bootstrap context: campaign and player identity, compatibility, core resource/research/control-point context, and available analysis routes. Use specialized commands for details. This beta does not provide dashboards, history, previous-save comparisons, alerts, or companion integration.

## Compatibility and data

The initial compatibility registry contains no verified version/mod/runtime tuples. Calculation commands require a verified tuple or the per-invocation `--allow-unverified` opt-in. That opt-in does not bypass missing dependencies, unsupported scenarios, or catalog integrity checks. Raw/type inspection and capabilities do not require calculation consent; incomplete calculations remain explicitly incomplete.

Normal execution is package-only: runtime calculations use catalogs under `data/` and never discover an installed template tree or `Assembly-CSharp.dll`. Raw game files are generation, audit, or source-checkout `catalog-verify` inputs only. See the [game-derived data notice](docs/BETA_DATA_NOTICE.md) for excluded assets and the unresolved redistribution review. MIT applies to project code; no external publication or ChatGPT acceptance is implied by a local test pass.

**Source checkout only:** [Developer documentation](dev-docs/README.md) is excluded from the runtime ZIP.
