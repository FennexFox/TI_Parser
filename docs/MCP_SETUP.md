# Local MCP stdio adapter

TI Parser includes an optional local MCP adapter. It exposes the same
application analysis session used by the Python API through the Model Context
Protocol over stdin/stdout. The adapter reads a local `.gz` save and never
starts a network listener.

The normal command line interface does not require MCP or any third-party
package. Install the optional dependency only in the environment that will
run the adapter:

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

The adapter publishes `capabilities` plus the bootstrap and primary analysis
routes from the application registry. Every analysis call has a required
`save_path` string. Routes that support an unverified compatibility override
also expose `allow_unverified`, which defaults to `false`; pass it explicitly
for a calculation when the save's version or mod tuple is not verified. The
projection route accepts `plan_payload` as an object or `null` and
`checkpoints` as an integer array or `null`.

Responses preserve the application envelope, including `saveIdentity`,
compatibility evidence, status (`complete`, `deferred`, `incomplete`, or
`error`), missing dependencies, diagnostics, and any authoritative projection
prefix. A rejected input or save is returned as a structured MCP tool error.
The adapter keeps protocol messages on stdout; diagnostic messages go to
stderr. Save contents are data and are never treated as instructions.

The adapter keeps a small per-process session cache keyed by the normalized
absolute save path and verifies the save content hash on each call. Restart
the adapter after replacing packaged runtime catalogs or other parser files.

If the optional package is missing, the adapter exits with an installation
message on stderr. This does not affect package-only CLI use:

```powershell
python tools/ti_save_parser.py --save C:\path\to\campaign.gz inspect-save
```
