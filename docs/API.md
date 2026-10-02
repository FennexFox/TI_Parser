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
programming exceptions propagate. Every session method that accepts calculation
consent requires `allow_unverified` to be a real boolean. Compatibility opt-in
does not suppress missing dependencies or
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

## Fair-play profile boundary

The MCP adapter accepts `--profile default|fair-play`; omitting the option
preserves the default route set. `run_profile(session, analysis, *,
profile="default", **kwargs)` applies the same policy to session calls. In
fair-play, only `inspect-save` is an analysis route. `capabilities` remains an
inventory tool and lists only `inspect-save`; every other registry route is
denied before its handler runs. `nation-projection` is globally blocked
pending the authoritative visibility audit described in the
[interoperability audit](../dev-docs/fairplay_interoperability.md).

Fair-play keeps the envelope fields `schemaVersion`, `parserVersion`,
`analysis`, `saveIdentity`, `compatibility`, and `status`. Its save identity
allowlist contains the supported fingerprint, observed game date/scenario and
version facts, campaign start, and resolved player faction identity; unresolved
player identity is rejected. Compatibility contains only status, reason codes,
and a valid catalog fingerprint, without observations, context, or mod
internals. Errors are reduced to
`schemaVersion`, `status`, and a generic error code/message, preventing
profile-denied details from leaking through diagnostics. Compatibility checks
remain in force; `allow_unverified` does not grant access to denied routes.

The Python `compare_save_context(parser_identity, companion_identity,
parser_nation_id, companion_nation_id, *, pinned,
previous_parser_fingerprint=None)` helper compares save context; it is not an
MCP tool. Exact matching requires schema version 1 on both identities, equal
supported canonical-save SHA-256 fingerprints, and equal campaign start, game
date, resolved player faction ID and template, and selected nation ID. A
provisional match is allowed only when an exact fingerprint is unavailable,
the save is pinned, and every context value is present and equal. A present
supported algorithm with an invalid digest, a previous-fingerprint change, a
mismatch, or a missing/changed context field rejects comparison; fingerprint
mismatch never falls back to weak fields.
`inspect-save` does not expose a selected nation ID, so an MCP-only workflow
must leave that comparison unresolved unless the ID is provided by another
authoritative approved source. See the [MCP runbook](MCP_SETUP.md#matching-the-pinned-save)
for operator steps.

`validate_advice_generation(context_envelope, ti_inspection_envelope,
projection_envelope, ti_reinspect_envelope,
companion_reobserved_context_envelope, *, pinned, subject_binding=None)` checks a complete advice
observation batch. It is a Python correlation helper, not a policy approval or
MCP tool. Peer envelopes require `status="complete"`, `saveIdentity`,
`selectedNationId`, and `result.nation.id` equal to that selected ID. Identities
must describe the snapshot that produced each result, not a later lookup.

TI envelopes use schema version 1, the expected analysis, and their response
`saveIdentity`. Inspection and reinspection remain save-only and retain their
matching `result.saveIdentity`; they need no selected nation field. All three
TI fingerprints must be supported and identical.

The helper additionally requires `subject_binding=receipt`, an opaque,
process-local receipt issued by the trusted application operation. The
operation resolves the strict player and selected nation, verifies every CP's
type, nation, count and player ownership, executes the existing session
projection, and seals that exact result object, its complete content and its
save identity. A JSON `selectedNationId`, guessed ID, copied or altered result,
or receipt from another result cannot supply attestation. The receipt's nation
must match both Companion observations. This is subject/correlation evidence;
it grants no visibility, mechanics or fair-play approval.

Issuance is currently a private application contract tested with real sessions
and packaged calculations. It is not a serialized MCP token or a new public
tool. Fair-play admission remains owned by `run_profile`, which still denies
projection before any subject or save preparation. Current public MCP tools
cannot finish the successful advice sequence. A future approved adapter must
issue and validate the receipt within the application boundary; callers must
not add guessed IDs to inspection responses.

A future approved adapter's complete projection needs usable plans and
comparison data. An incomplete result must retain its authoritative prefix;
the helper returns `outcomeStatus="incomplete"` rather than converting it to a
complete prediction. Deferred/error results reject the batch. Pinned weak peer
identity can return only `provisional`, even after reobservation. Any conflict
or missing observation requires discarding the batch and observing again.

Fair-play capabilities include `fairPlayPolicy` with the pending, disabled
`fair-play-projection-v1` identity. Registry target classification and an
approved execution policy are separate; no projection domain is approved yet.
Companion MCP and mechanics behavior still require external acceptance. Local
profile support and mock-client routing do not establish those results.
