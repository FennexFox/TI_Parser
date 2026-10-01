# Local MCP stdio adapter

TI Parser includes an optional local MCP adapter. It exposes the same
application analysis session used by the Python API through the Model Context
Protocol over stdin/stdout. The adapter reads a local `.gz` save and never
starts a network listener.

The normal CLI and Python API remain package-only and do not require MCP or
any third-party package. The beta ZIP includes the adapter source and pinned
requirements file, but not the MCP SDK. Install that optional dependency only
in the Python environment that will launch the adapter (a dedicated virtual
environment is suitable):

```powershell
python -m pip install -r requirements-mcp.txt
```

Start the adapter with an absolute path when configuring an MCP host. The
working directory is not used to locate the repository:

```powershell
python C:\path\to\TI_Parser\tools\ti_parser_mcp.py
```

For example, a stdio host configuration can use:

```json
{
  "mcpServers": {
    "ti-parser": {
      "command": "C:\\path\\to\\python.exe",
      "args": ["C:\\path\\to\\TI_Parser\\tools\\ti_parser_mcp.py"]
    }
  }
}
```

The adapter exposes one MCP tool for each `inspect-save`, `analyze`, and
`primary` analysis route in the application registry, plus `capabilities`.
`capabilities` takes no arguments and does not open a save. Each analysis tool
requires `save_path` (a non-empty path string); its other argument names and
defaults follow the registered application handler. Unknown extra properties
are rejected. Routes that support explicit unverified-compatibility consent
also expose `allow_unverified`, defaulting to `false`. `nation-projection`
accepts `plan_payload` as a JSON object or `null`, and `checkpoints` as an
integer array or `null`.

Successful and expected in-session outcomes use schema version 1 and carry the
same `analysis`, `parserVersion`, `saveIdentity`, `compatibility`, and `status`
fields as `AnalysisSession.run()`. Status is `complete`, `deferred`,
`incomplete`, or `error`; applicable results include `result`,
`missingDependencies`, or `error`, and projection results retain their
execution evidence and authoritative prefix. Errors before a session can be
created (for example, an unreadable save path) return a structured schema-1
error payload and cannot contain save identity or compatibility evidence. The
MCP result includes the payload as structured content and JSON text. Input or
save failures marked `error` are MCP tool errors; `deferred` and `incomplete`
are returned as analysis outcomes. Protocol messages use stdout, diagnostic
messages use stderr, and save contents are treated only as data.

The adapter keeps at most two sessions per process, keyed by normalized
absolute save path and checked against the save's byte hash on every call. A
changed save replaces its cached session. Restart the adapter after replacing
parser files or packaged runtime catalogs.

If the optional package is missing, the adapter exits with an installation
message on stderr. This does not affect package-only CLI use:

```powershell
python tools/ti_save_parser.py --save C:\path\to\campaign.gz inspect-save
```
