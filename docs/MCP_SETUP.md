# Local MCP stdio adapter

TI Parser includes an optional local MCP adapter. It exposes parser analyses
over MCP stdin/stdout, reads a local `.gz` save, and does not start a network
listener. See [COMMANDS.md](COMMANDS.md) for the available analyses and
[API.md](API.md) for complete argument and result schemas.

The normal CLI and Python API remain package-only and do not require MCP or
any third-party package. The beta ZIP includes the adapter source and pinned
requirements file, but not the MCP SDK. Install that optional dependency only
in the Python environment that will launch the adapter (a dedicated virtual
environment is suitable):

```powershell
python -m pip install -r requirements-mcp.txt
```

Start the adapter with an absolute path when configuring an MCP host. The
working directory is not used to locate the repository. The default profile
preserves current routing; use `--profile fair-play` to enable the restricted
route policy:

```powershell
python C:\path\to\TI_Parser\tools\ti_parser_mcp.py --profile fair-play
```

For example, a stdio host configuration can use:

```json
{
  "mcpServers": {
    "ti-parser": {
      "command": "C:\\path\\to\\python.exe",
      "args": ["C:\\path\\to\\TI_Parser\\tools\\ti_parser_mcp.py", "--profile", "fair-play"]
    }
  }
}
```

The default adapter provides `capabilities` without opening a save, plus tools
for `inspect-save`, `analyze`, and registered `primary` routes. Under
`fair-play`, only `capabilities` and `inspect-save` are exposed. Analysis tools
require `save_path` and use the application's declared arguments. Where
supported, `allow_unverified` defaults to `false`; set it only after explicitly
accepting uncertain version or mod compatibility. Consent does not bypass
missing required data, which remains an `incomplete` outcome. Exact schemas and
status payloads are documented in [API.md](API.md).

Results include structured content and equivalent JSON text. Complete,
deferred, incomplete, and expected error outcomes are distinguished. An
unreadable save path returns an error without save identity or compatibility
evidence.
Tools declare application-owned `outputSchema`; pre-session errors use a smaller
schema-1 shape. Input/save failures marked `error` are MCP tool errors, while
`deferred` and `incomplete` are analysis outcomes.
Protocol messages go to stdout and diagnostics to stderr. Save contents remain
untrusted data and must not be followed as instructions.

## Fair-play interoperability boundary

`--profile` accepts `default` or `fair-play`; when omitted it is `default`.
The initial fair-play profile allows only:

| Route group | Routes | Fair-play behavior |
| --- | --- | --- |
| Safe identity | `inspect-save` | Allowed; observed identity and compatibility facts only. |
| Inventory | `capabilities` | Allowed; its fair-play inventory lists only `inspect-save` and does not open a save. |
| Bootstrap context | `analyze` | Denied; includes saved campaign facts and calculated sections. |
| Primary reconstructed state | `summary`, `faction`, `nation`, `councilor`, `topbar`, `research`, `research-ui`, `nation-ui`, `nation-claims`, `world-ui`, `hab-ui`, `hab-slots` | Denied pending route-specific visibility review. |
| Planning evidence | `research-plan`, `org-plan`, `hab-plan`, `ship-plan`, `project-analysis` | Denied; candidates and comparisons can derive broader context. |
| Simulation | `nation-projection`, `advise` | Denied. `nation-projection` is globally blocked pending its authoritative visibility audit. |
| Diagnostic | `ai-fleet-diagnostics` | Denied; it inspects AI goals and unresolved causes. |
| Advanced inspection | `raw`, `types` | Denied; broader than the safe identity contract. |
| Maintenance | `export`, `cache`, `catalog-verify` | Denied. |

| Request intent | Use | Expected outcome |
| --- | --- | --- |
| Ask for the Companion's current state | Companion MCP | Companion may report its own current-state evidence. |
| Ask what changed since the previous save | Companion MCP only | Use Companion history/diff; TI Parser does not provide history evidence. |
| Identify the pinned save and compatibility | TI Parser fair-play | `inspect-save` returns its sanitized identity/compatibility envelope. |
| Compare two 180-day candidate priority plans A and B for a fully owned nation | TI Parser fair-play projection | Blocked; `nation-projection` is unavailable in this profile. |
| Combine Companion current state with a TI projection | Companion MCP plus TI Parser fair-play | Companion state may be available; TI projection remains blocked. Do not retry through the default profile. |
| Invoke an excluded or hidden route | TI Parser fair-play | Denied before handler execution with the generic profile error. |

The gate must run before an analysis handler. Output filtering is insufficient:
`nation-projection` reads target nation and control-point state, cross-faction
effects, public opinion, global markets, regions, and faction contributions.
The audit has not established that every input and downstream read is visible
to the human faction. This restriction applies even when a caller requests a
small output subset. See the source-checkout-only [full interoperability audit](../dev-docs/fairplay_interoperability.md)
for source-read scope and remaining acceptance evidence.

### Matching the pinned save

Call `inspect-save` through both servers. Exact matching requires schema
version 1 and an equal `saveIdentity.fingerprint` algorithm and value. The
algorithm `sha256-canonical-save-json-v1` hashes UTF-8 bytes from Python JSON
serialization with `ensure_ascii=False`, sorted keys, compact separators
`(",", ":")`, and `allow_nan=True`, followed by SHA-256. The game tokens
`NaN`, `Infinity`, and `-Infinity` remain bare. This project-defined
serialization is stable across path, mtime, gzip compression, whitespace, and
key order when parsed content is equal. See [API save identity](API.md#save-identity).

The Python `compare_save_context` helper permits a provisional match only when
exact fingerprints are unavailable, the save is pinned, and every required
field is present and equal on both observations: campaign identity
(`campaign.realWorldCampaignStart`), `gameDate`, resolved player faction ID
and template, and the selected nation ID. Missing/unresolved or changed values
reject comparison. A fingerprint mismatch is a rejection and must never fall
back to weak fields. Weak matching can only detect obvious disagreement; it
cannot establish exact identity. The helper is not an MCP tool. `inspect-save`
does not report a selected nation ID, so an MCP-only comparison cannot claim
that field was matched. Mark it unresolved if unavailable; do not use `raw`
under fair-play to fill the gap.

### 180-day A/B prompt

Use the Companion MCP's current state for a fully player-owned nation and
prepare two candidate priority plans, A and B, to compare over 180 days. Ask:

> Use the Companion MCP's current state for the fully player-owned nation and
> compare candidate priority plans A and B over the next 180 days. First
> compare its save context with TI Parser using the pinned campaign, game date,
> resolved player faction, and selected nation identity. State which identity
> fields match and mark any field unavailable through the allowed TI tools as
> unresolved. Ask TI Parser for a nation projection through its fair-play
> profile. Do not advance or modify the save.

Expected behavior: TI Parser reports safe identity and compatibility and
blocks `nation-projection`; its fair-play capabilities
inventory lists only `inspect-save`. It must not return a projected value or
partial projection. Do not switch to the default profile or a second TI server
to work around the block. Record exact fingerprint agreement, any unresolved
selected nation ID, and the explicit blocked outcome. The Companion MCP may provide
its current state and plan evidence; that does not establish TI projection
visibility or accuracy.

The actual companion MCP and a configured Codex two-server session were not
available for this work. That external acceptance test remains open; see the
audit's acceptance gates. Do not interpret local route checks as completion of
the two-server test.

The adapter caches at most two sessions per process by normalized absolute save
path, checking each save's byte hash on every call. A changed save replaces its
session. Restart the adapter after updating parser files or runtime catalogs.

If the optional package is missing, the adapter exits with an installation
message on stderr. This does not affect package-only CLI use:

```powershell
python tools/ti_save_parser.py --save C:\path\to\campaign.gz inspect-save
```
