# Telemetry and Dashboards

The FastMCP server now exposes lightweight telemetry so operators can supervise pane health, agent coordination, and recent message traffic without tailing multiple log files.

## Enabling telemetry

Session logging is enabled by default when the FastMCP server starts. Telemetry derives from the same session log streams in `~/.iterm_mcp_logs`, so no additional configuration is required. If you disabled logging previously, re-enable it by starting the server without `--no-logging` flags and ensure `~/.iterm_mcp_logs` is writable.

## Telemetry resource

Use the `telemetry://dashboard` MCP resource to retrieve the aggregated JSON payload:

```bash
# From an MCP client, request telemetry
telemetry://dashboard
```

The payload includes:

- `agents_online`: number of registered agents tied to panes
- `pane_count`: total panes discovered in iTerm
- `panes`: per-pane stats (command count, output line count, queue depth, recent errors, last activity timestamps)
- `recent_messages`: recent message hashes and recipients recorded for deduplication
- `teams`: team hierarchy with parents and member lists
- `active_session`: the session ID currently marked active in the registry

## Dashboard tool

Run the `show_dashboard` tool from Claude/your MCP client to visualize telemetry:

```bash
# Text-mode summary (default)
show_dashboard

# Start a temporary web endpoint on port 7002 for 3 minutes
show_dashboard mode="web" port=7002 duration_seconds=180
```

- **TUI mode** renders a textual summary showing team hierarchy, pane health, and recent errors.
- **Web mode** starts an ephemeral HTTP server that serves the same JSON at `http://localhost:<port>` for the requested duration. The MCP resource remains available for polling.

## Interpreting the dashboard

- **Queue depth** indicates whether a pane is currently processing input (1) or idle (0).
- **Recent errors** surface the last logged error per pane from the session log stream.
- **Command/output counters** accumulate from the session lifecycle to highlight busy or noisy panes.
- **Message hashes** help coordinate broadcast/cascaded messages across teams by showing which payloads have been seen recently.
- **Team hierarchy** shows parent/child relationships so you can confirm cascaded messaging paths.
