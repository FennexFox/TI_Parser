# Python and machine API

The reusable Python API is in `tools/ti_parser_session.py`. Add the bundled
`tools/` directory to `sys.path`, then create one `AnalysisSession` per save.
Session construction loads and indexes the save; a failure at this stage is an
exception because no result envelope can yet be built.

```python
from pathlib import Path
from ti_parser_session import AnalysisSession

session = AnalysisSession(Path("campaign.gz"))
inspection = session.run("inspect-save")
research = session.run("research-plan", allow_unverified=True, top=8)
```

## Session methods

- `inspect()` returns save identity and observed facts with compatibility
  evidence; it does not run calculations.
- `analyze(allow_unverified=False)` builds bounded LLM bootstrap context.
- `calculate(analysis, allow_unverified=False, **kwargs)` returns the existing
  analysis payload and preserves expected failures as exceptions.
- `run(analysis_id, allow_unverified=False, **kwargs)` is the versioned machine
  boundary. It supports `inspect-save`, `analyze`, and registered
  application-callable analyses.
- `calculation_scope(allow_unverified=False)` yields the indexed save for
  existing domain `calculate_*` functions while sharing validated catalog
  bundles for the session lifetime.

The registry exposes `get_input_schema(analysis_id)` for a fresh JSON Schema
of each application-callable analysis. `capabilities` publishes the analysis
inventory, routing class, argument names, and defaults. `inspect-save` and
`analyze` take no analysis arguments. Other Python arguments use their declared
snake_case names and types; name selectors accept a string name or integer ID
where the schema says so. The CLI offers the same primary selector as a
positional name or `--entity-id`, and rejects both together. Projection takes
`plan_payload` as a parsed JSON object (or `None`) and `checkpoints` as an array
of integer days. CLI paths, comma-separated checkpoint text, output flags,
cache flags, and template overrides are not Python API arguments.

## `run()` envelope

Schema version 1 includes `schemaVersion`, `parserVersion`, `analysis`,
`saveIdentity`, `compatibility`, and `status`. A successful or partial handler
also provides `result`; expected failures provide `missingDependencies` or
`error` as applicable.

| Status | Meaning |
| --- | --- |
| `complete` | The handler completed without a reported incomplete scope. |
| `deferred` | Compatibility is unverified and calculation consent was not given. |
| `incomplete` | A dependency is missing, or the executed result is partial or unsupported. |
| `error` | The analysis, arguments, or input are invalid. |

An incomplete projection keeps its authoritative completed prefix, scope status,
and diagnostics. Expected errors are returned in the envelope, while unexpected
programming exceptions propagate. `run()` requires `allow_unverified` to be a
real boolean. Compatibility opt-in does not suppress missing dependencies or
catalog errors. The CLI keeps its own output shapes and exit codes.

## Save identity

`saveIdentity` schema 1 fingerprints parsed save content with
`sha256-canonical-save-json-v1`. The exact hashed bytes are UTF-8 from Python's
JSON serialization of the parsed save with `ensure_ascii=False`, sorted keys,
compact separators `(",", ":")`, and `allow_nan=True`, followed by SHA-256.
This is a project-defined stable serialization, not RFC canonical JSON.

Python's non-standard JSON tokens `NaN`, `Infinity`, and `-Infinity` are hashed
as those bare tokens. A string such as `"NaN"` remains a quoted JSON string and
has a different fingerprint. Whitespace, object-key order, save path, file
mtime, and gzip compression do not affect identity when parsed content is the
same. The fingerprint is a content identity, not a compatibility or catalog
fingerprint. Bootstrap output represents non-finite values explicitly.

The remaining identity fields report observed date, scenario, latest and
campaign-start versions, campaign start, and player-faction resolution. Missing
or ambiguous player evidence stays unresolved; the parser does not guess.

## Lifetime and compatibility

Treat a session as an immutable, single-threaded view of one save and one
runtime-data snapshot. Do not mutate the indexed save or returned domain state.
The session reuses its save index, lazy snapshot, and validated catalog bundles;
create a new session after the save or runtime data changes, and use separate
sessions for different saves or concurrent work.

Calculation requires a verified save/runtime tuple or explicit per-call
`allow_unverified=True`. The initial compatibility registry contains no
verified tuples. Consent is narrow: package catalogs remain mandatory, and
unsupported mechanics, unresolved required references, and missing blocking
dependencies stay explicit. See [Commands](COMMANDS.md) for the CLI contract
and [the beta data notice](BETA_DATA_NOTICE.md) for data boundaries.
