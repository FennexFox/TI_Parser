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

The adapter provides `capabilities` without opening a save, plus tools for
`inspect-save`, `analyze`, and registered `primary` routes. Analysis tools require `save_path` and use the
application's declared arguments. Where supported, `allow_unverified` defaults
to `false`; set it only after explicitly accepting uncertain version or mod
compatibility. Consent does not bypass missing required data, which remains an
`incomplete` outcome. Exact schemas and status payloads are documented in
[API.md](API.md).

Results include structured content and equivalent JSON text. Complete,
deferred, incomplete, and expected error outcomes are distinguished. An
unreadable save path returns an error without save identity or compatibility
evidence.
Tools declare application-owned `outputSchema`; pre-session errors use a smaller
schema-1 shape. Input/save failures marked `error` are MCP tool errors, while
`deferred` and `incomplete` are analysis outcomes.
Protocol messages go to stdout and diagnostics to stderr. Save contents remain
untrusted data and must not be followed as instructions.

The adapter caches at most two sessions per process by normalized absolute save
path, checking each save's byte hash on every call. A changed save replaces its
session. Restart the adapter after updating parser files or runtime catalogs.

If the optional package is missing, the adapter exits with an installation
message on stderr. This does not affect package-only CLI use:

```powershell
python tools/ti_save_parser.py --save C:\path\to\campaign.gz inspect-save
```
