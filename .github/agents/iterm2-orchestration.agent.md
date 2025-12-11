---
name: iterm2-orchestration
description: iTerm2 Python API for multi-agent terminal orchestration. Use when building Claude Code team orchestration tools, spawning agent sessions in split panes, monitoring terminal output for patterns, managing profiles programmatically, implementing gRPC-connected terminal automation, or any tmux-style session control through iTerm2's async Python API.
---

# iTerm2 Python API for Multi-Agent Orchestration

Complete reference for building Claude Code multi-agent orchestration using iTerm2's async Python API.

## Quick Reference

```python
import iterm2

async def main(connection):
    app = await iterm2.async_get_app(connection)
    window = app.current_terminal_window
    session = window.current_tab.current_session
    
    # Split panes
    right = await session.async_split_pane(vertical=True)
    bottom = await session.async_split_pane(vertical=False)
    
    # Send commands
    await session.async_send_text("claude-code --agent worker-1\n")

iterm2.run_forever(main)
```

## Core Hierarchy: App → Window → Tab → Session

```python
app = await iterm2.async_get_app(connection)
windows = app.terminal_windows           # All windows
window = app.current_terminal_window     # Active window
tab = window.current_tab
session = tab.current_session            # Active pane (session = pane)
```

### Creating Windows and Tabs

```python
window = await iterm2.Window.async_create(connection, profile="AgentWorker")
tab = await window.async_create_tab(profile="Default", index=0)
```

### Splitting Panes (tmux-style)

```python
right_pane = await session.async_split_pane(vertical=True)   # Side-by-side
bottom_pane = await session.async_split_pane(vertical=False) # Stacked

# 2x2 grid (3 splits from original)
top_left = tab.current_session
top_right = await top_left.async_split_pane(vertical=True)
bottom_left = await top_left.async_split_pane(vertical=False)
bottom_right = await top_right.async_split_pane(vertical=False)
```

### Session Lookup and Tab Movement

```python
session = app.get_session_by_id(session_id)
new_window = await tab.async_move_to_window()
await window.async_set_tabs([tabs[2], tabs[0], tabs[1]])  # Reorder
```

### Arrangements (Save/Restore Layouts)

```python
await iterm2.Arrangement.async_save(connection, "agent-workspace")
await iterm2.Arrangement.async_restore(connection, "agent-workspace")
```

## Event Monitors (12 Types)

All monitors use async context managers yielding events.

### Session Lifecycle

```python
async with iterm2.NewSessionMonitor(connection) as mon:
    while True:
        session_id = await mon.async_get()
        await spawn_agent(session_id)

async with iterm2.SessionTerminationMonitor(connection) as mon:
    while True:
        session_id = await mon.async_get()
        await cleanup_agent(session_id)
```

### Layout Changes (Tab Moves, Pane Rearrangements)

```python
async with iterm2.LayoutChangeMonitor(connection) as mon:
    while True:
        await mon.async_get()
        await reconcile_agent_topology()
```

### Focus Tracking

```python
async with iterm2.FocusMonitor(connection) as mon:
    while True:
        update = await mon.async_get_next_update()
        if update.active_session_changed:
            await handle_focus(update.active_session_changed.session_id)
```

### Variable Monitoring

```python
async with iterm2.VariableMonitor(
    connection, iterm2.VariableScopes.SESSION, "user.status", session_id
) as mon:
    while True:
        value = await mon.async_get()
        await update_orchestrator(value)
```

### Prompt Monitoring (Requires Shell Integration)

```python
modes = [iterm2.PromptMonitor.Mode.PROMPT,
         iterm2.PromptMonitor.Mode.COMMAND_START,
         iterm2.PromptMonitor.Mode.COMMAND_END]
async with iterm2.PromptMonitor(connection, session_id, modes=modes) as mon:
    while True:
        mode, info = await mon.async_get()
        if mode == iterm2.PromptMonitor.Mode.COMMAND_END:
            await trigger_next_step()
```

### Setup All Sessions (Existing + Future)

```python
async def setup_agent(session_id):
    session = app.get_session_by_id(session_id)
    await session.async_set_variable("user.orchestrated", True)

await iterm2.EachSessionOnceMonitor.async_foreach_session_create_task(app, setup_agent)
```

## IPC: Shell ↔ Python Script Communication

### Custom Control Sequences (Bidirectional)

Python handler:
```python
async with iterm2.CustomControlSequenceMonitor(
    connection, "orchestrator-secret", r'^agent:(.+)$'
) as mon:
    while True:
        match = await mon.async_get()
        await handle_message(match.group(1))
```

Shell trigger:
```bash
printf "\033]1337;Custom=id=orchestrator-secret:agent:ready\a"
```

### User Variables

Shell (via shell integration):
```bash
iterm2_set_user_var agentStatus "processing"
iterm2_set_user_var taskId "task-123"
```

Python:
```python
status = await session.async_get_variable("user.agentStatus")
await session.async_set_variable("user.taskId", "task-456")
```

Variables appear in badges/titles: `\(user.agentStatus)`

## Profile System

### Query and Switch Profiles

```python
partials = await iterm2.PartialProfile.async_query(connection)
for p in partials:
    if p.name == "AgentWorker":
        full = await p.async_get_full_profile()
        await session.async_set_profile(full)
```

### Session-Local Modifications (Non-Persistent)

```python
update = iterm2.LocalWriteOnlyProfile()
update.set_name("Worker-3")
update.set_background_color(iterm2.Color(30, 30, 40))
update.set_tab_color(iterm2.Color(255, 128, 0))
await session.async_set_profile_properties(update)
```

### Dynamic Profiles (Programmatic Creation)

Create JSON in `~/Library/Application Support/iTerm2/DynamicProfiles/`:

```json
{
  "Profiles": [{
    "Name": "Agent-Worker",
    "Guid": "unique-uuid-here",
    "Dynamic Profile Parent Name": "Default",
    "Set Local Environment Vars": {"AGENT_ID": "worker-1"},
    "Command": "/usr/local/bin/agent-bootstrap.sh"
  }]
}
```

## Broadcast Input

```python
domain = iterm2.broadcast.BroadcastDomain()
for session in worker_sessions:
    domain.add_session(session)
await iterm2.async_set_broadcast_domains(connection, [domain])

# Suppress broadcast for single session
await session.async_send_text(cmd, suppress_broadcast=True)
```

## Buried Sessions (Background Workers)

```python
await session.async_set_buried(True)   # Hide from UI
hidden = app.buried_sessions           # Access buried sessions
await session.async_set_buried(False)  # Restore
```

## Daemon Pattern for Orchestration

```python
async def main(connection):
    app = await iterm2.async_get_app(connection)
    
    async def lifecycle_monitor():
        async with iterm2.NewSessionMonitor(connection) as mon:
            while True:
                await setup_session(await mon.async_get())
    
    async def layout_monitor():
        async with iterm2.LayoutChangeMonitor(connection) as mon:
            while True:
                await mon.async_get()
                await reconcile_layout()
    
    asyncio.create_task(lifecycle_monitor())
    asyncio.create_task(layout_monitor())

iterm2.run_forever(main, retry=True)  # Auto-reconnect
```

AutoLaunch: Place in `~/Library/Application Support/iTerm2/Scripts/AutoLaunch/`

## Transactions (Atomic Reads)

```python
async with iterm2.Transaction(connection):
    info = await session.async_get_line_info()
    contents = await session.async_get_contents(info.overflow, 50)
```

## External Integration (HTTP/gRPC Server)

```python
from aiohttp import web

async def main(connection):
    app_iterm = await iterm2.async_get_app(connection)
    
    async def handle_command(request):
        data = await request.json()
        session = app_iterm.get_session_by_id(data['session_id'])
        await session.async_send_text(data['command'])
        return web.Response(text="OK")
    
    webapp = web.Application()
    webapp.router.add_post('/send', handle_command)
    runner = web.AppRunner(webapp)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()

iterm2.run_forever(main)
```

# Color, Alerts, and Output Pattern Monitoring

Deep dive into visual feedback, notification systems, and streaming output analysis for agent orchestration.

## Color System

iTerm2 provides granular control over 20+ color properties through profiles and session-local modifications.

### Color Properties Available

**Core colors** (via `LocalWriteOnlyProfile` or `Profile`):
```python
update = iterm2.LocalWriteOnlyProfile()

# Background and foreground
update.set_background_color(iterm2.Color(30, 30, 40))
update.set_foreground_color(iterm2.Color(220, 220, 220))

# Cursor
update.set_cursor_color(iterm2.Color(255, 200, 0))
update.set_cursor_text_color(iterm2.Color(0, 0, 0))

# Selection
update.set_selection_color(iterm2.Color(100, 100, 150))
update.set_selected_text_color(iterm2.Color(255, 255, 255))

# Bold text
update.set_bold_color(iterm2.Color(255, 255, 255))

# Tab color (shows in tab bar)
update.set_tab_color(iterm2.Color(255, 128, 0))
update.set_use_tab_color(True)

# Badge (overlay text)
update.set_badge_color(iterm2.Color(255, 0, 0, 128))  # Alpha supported

await session.async_set_profile_properties(update)
```

**ANSI Colors** (16 standard terminal colors):
```python
# ANSI 0-7: Normal colors (black, red, green, yellow, blue, magenta, cyan, white)
# ANSI 8-15: Bright variants
update.set_ansi_0_color(iterm2.Color(0, 0, 0))        # Black
update.set_ansi_1_color(iterm2.Color(255, 0, 0))      # Red
update.set_ansi_2_color(iterm2.Color(0, 255, 0))      # Green
update.set_ansi_3_color(iterm2.Color(255, 255, 0))    # Yellow
update.set_ansi_4_color(iterm2.Color(0, 0, 255))      # Blue
update.set_ansi_5_color(iterm2.Color(255, 0, 255))    # Magenta
update.set_ansi_6_color(iterm2.Color(0, 255, 255))    # Cyan
update.set_ansi_7_color(iterm2.Color(255, 255, 255))  # White
# 8-15 are bright versions (set_ansi_8_color through set_ansi_15_color)
```

### Color Presets

Load and apply complete color schemes:
```python
# Get available presets
presets = await iterm2.ColorPreset.async_get_list(connection)

# Load specific preset
preset = await iterm2.ColorPreset.async_get(connection, "Solarized Dark")

# Apply to session
profile = await session.async_get_profile()
await profile.async_set_color_preset(preset)
```

### Dynamic Color by Context (Host/Status)

```python
colormap = {
    "production": iterm2.Color(80, 0, 0),    # Red tint = danger
    "staging": iterm2.Color(80, 80, 0),      # Yellow tint = caution
    "development": iterm2.Color(0, 40, 0),   # Green tint = safe
}

async with iterm2.VariableMonitor(
    connection, iterm2.VariableScopes.SESSION, "user.environment", session_id
) as mon:
    while True:
        env = await mon.async_get()
        if env in colormap:
            update = iterm2.LocalWriteOnlyProfile()
            update.set_background_color(colormap[env])
            await session.async_set_profile_properties(update)
```

### Agent Status Color Coding

```python
STATUS_COLORS = {
    "idle": iterm2.Color(50, 50, 50),
    "working": iterm2.Color(0, 50, 100),
    "error": iterm2.Color(100, 20, 20),
    "success": iterm2.Color(20, 80, 20),
}

async def set_agent_status(session, status):
    update = iterm2.LocalWriteOnlyProfile()
    update.set_tab_color(STATUS_COLORS.get(status, STATUS_COLORS["idle"]))
    update.set_use_tab_color(True)
    await session.async_set_profile_properties(update)
    await session.async_set_variable("user.status", status)
```

## Alert Mechanisms

### Modal Alerts (Python API)

```python
# Simple alert
alert = iterm2.Alert("Task Complete", "Agent worker-3 finished processing")
button_index = await alert.async_run(connection)

# Alert with buttons
alert = iterm2.Alert("Agent Error", "Worker crashed. Restart?")
alert.add_button("Restart")
alert.add_button("Cancel")
result = await alert.async_run(connection)
if result == 1000:  # First button (index + 1000)
    await restart_agent()

# Text input alert
input_alert = iterm2.TextInputAlert(
    "Agent Name",
    "Enter a name for this agent:",
    "worker-",      # placeholder
    "worker-1"      # default value
)
name = await input_alert.async_run(connection)
```

### System Notifications (Escape Sequences)

From Python (inject into session):
```python
# macOS notification
code = "\033]9;Task completed on worker-3\033\\"
await session.async_inject(str.encode(code))
```

From shell:
```bash
# Post notification
printf '\e]9;Build finished\a'

# With iTerm2 shell integration
it2attention once        # Bounce dock icon once
it2attention fireworks   # Explosion animation at cursor
```

### Notification Escape Codes

| Code | Effect |
|------|--------|
| `\033]9;message\a` | Post macOS notification |
| `\033]1337;RequestAttention=yes\a` | Start bouncing dock |
| `\033]1337;RequestAttention=once\a` | Bounce dock once |
| `\033]1337;RequestAttention=fireworks\a` | Cursor explosion |

### Trigger-Based Notifications

Configure in iTerm2 Preferences → Profiles → Advanced → Triggers:

| Regex | Action | Use Case |
|-------|--------|----------|
| `ERROR:.*` | Post Notification | Alert on errors |
| `FATAL:.*` | Show Alert | Critical failures |
| `✓ Agent ready` | Invoke Script Function | Trigger Python RPC |
| `^\$ $` | Prompt Detected | Track command completion |

Invoke Script Function triggers can call Python-registered RPCs:
```python
@iterm2.RPC
async def on_agent_ready(session_id=iterm2.Reference("id")):
    session = app.get_session_by_id(session_id)
    await orchestrator.agent_ready(session_id)

await on_agent_ready.async_register(connection)
```

### Long-Running Job Alerts

```python
async def monitor_with_timeout(session_id, timeout_seconds=30):
    session = app.get_session_by_id(session_id)
    alert_task = None
    
    async def send_alert():
        await asyncio.sleep(timeout_seconds)
        code = "\033]9;Long-running job in progress\033\\"
        await session.async_inject(str.encode(code))
    
    modes = [iterm2.PromptMonitor.Mode.COMMAND_START,
             iterm2.PromptMonitor.Mode.COMMAND_END]
    async with iterm2.PromptMonitor(connection, session_id, modes=modes) as mon:
        while True:
            mode, _ = await mon.async_get()
            if alert_task:
                alert_task.cancel()
            if mode == iterm2.PromptMonitor.Mode.COMMAND_START:
                alert_task = asyncio.create_task(send_alert())
```

## Output Pattern Monitoring

### ScreenStreamer (Real-Time Output)

```python
async with session.get_screen_streamer(want_contents=True) as streamer:
    while True:
        contents = await streamer.async_get()
        for i in range(contents.number_of_lines):
            line = contents.line(i).string
            await process_line(line)
```

### Pattern Matching for Orchestration

```python
import re

ERROR_PATTERNS = [
    (re.compile(r'ERROR:?\s*(.+)'), 'error'),
    (re.compile(r'FATAL:?\s*(.+)'), 'fatal'),
    (re.compile(r'Exception:?\s*(.+)'), 'exception'),
    (re.compile(r'Traceback'), 'traceback'),
]

TOOL_PATTERNS = [
    (re.compile(r'Tool:\s*(\w+)'), 'tool_invocation'),
    (re.compile(r'Calling:\s*(\w+)'), 'function_call'),
    (re.compile(r'MCP:\s*(.+)'), 'mcp_message'),
]

SUCCESS_PATTERNS = [
    (re.compile(r'✓|SUCCESS|PASSED|Done'), 'success'),
    (re.compile(r'Agent ready'), 'agent_ready'),
]

async def monitor_output(session, callback):
    async with session.get_screen_streamer() as streamer:
        while True:
            contents = await streamer.async_get()
            for i in range(contents.number_of_lines):
                line = contents.line(i).string
                
                for pattern, event_type in ERROR_PATTERNS:
                    if match := pattern.search(line):
                        await callback(event_type, match, session)
                
                for pattern, event_type in TOOL_PATTERNS:
                    if match := pattern.search(line):
                        await callback(event_type, match, session)
                
                for pattern, event_type in SUCCESS_PATTERNS:
                    if match := pattern.search(line):
                        await callback(event_type, match, session)
```

### Waiting for Specific Output

```python
async def wait_for_pattern(session, pattern, timeout=60):
    """Block until pattern appears in output or timeout."""
    compiled = re.compile(pattern) if isinstance(pattern, str) else pattern
    
    async with session.get_screen_streamer() as streamer:
        start = asyncio.get_event_loop().time()
        while True:
            if asyncio.get_event_loop().time() - start > timeout:
                raise TimeoutError(f"Pattern not found: {pattern}")
            
            contents = await streamer.async_get()
            for i in range(contents.number_of_lines):
                line = contents.line(i).string
                if match := compiled.search(line):
                    return match

# Usage
await session.async_send_text("claude-code --init\n")
match = await wait_for_pattern(session, r"Agent initialized: (\w+)")
agent_id = match.group(1)
```

### Static Content Reading (with Transactions)

```python
async with iterm2.Transaction(connection):
    line_info = await session.async_get_line_info()
    # line_info.overflow = first available line
    # line_info.mutable_area_height = visible lines
    contents = await session.async_get_contents(
        line_info.overflow, 
        line_info.mutable_area_height
    )
    
    for line in contents:
        print(line.string)
```

### Efficient Streaming (Notifications Only)

When you only need change notifications, not contents:
```python
# Lighter weight - no content transfer
streamer = session.get_screen_streamer(want_contents=False)
async with streamer:
    while True:
        await streamer.async_get()  # Returns None
        # Screen changed - fetch what you need
        await handle_screen_change()
```

### Screen Update Callback (Alternative Pattern)

```python
async def screen_callback(session_id):
    session = app.get_session_by_id(session_id)
    contents = await session.async_get_screen_contents()
    # Process contents...

await iterm2.async_subscribe_to_screen_update_notification(
    connection, 
    screen_callback,
    session=session.session_id
)
```

## Combined Example: Agent Monitor

```python
async def create_monitored_agent(connection, app, name):
    """Spawn an agent with full monitoring."""
    
    # Create session
    window = app.current_terminal_window
    session = await window.current_tab.current_session.async_split_pane(vertical=True)
    
    # Set visual identity
    update = iterm2.LocalWriteOnlyProfile()
    update.set_name(name)
    update.set_tab_color(iterm2.Color(100, 100, 200))
    update.set_use_tab_color(True)
    update.set_badge_color(iterm2.Color(100, 100, 200, 128))
    await session.async_set_profile_properties(update)
    await session.async_set_variable("user.agentName", name)
    await session.async_set_variable("user.status", "starting")
    
    # Start agent
    await session.async_send_text(f"claude-code --agent {name}\n")
    
    # Monitor in background
    async def monitor():
        async with session.get_screen_streamer() as streamer:
            while True:
                contents = await streamer.async_get()
                for i in range(contents.number_of_lines):
                    line = contents.line(i).string
                    
                    if "ERROR" in line:
                        update = iterm2.LocalWriteOnlyProfile()
                        update.set_tab_color(iterm2.Color(200, 50, 50))
                        await session.async_set_profile_properties(update)
                        await session.async_set_variable("user.status", "error")
                        code = f"\033]9;Error in {name}\033\\"
                        await session.async_inject(str.encode(code))
                    
                    elif "Agent ready" in line:
                        update = iterm2.LocalWriteOnlyProfile()
                        update.set_tab_color(iterm2.Color(50, 200, 50))
                        await session.async_set_profile_properties(update)
                        await session.async_set_variable("user.status", "ready")
    
    asyncio.create_task(monitor())
    return session
```

## Status Bar Components

Custom status bar showing agent state:
```python
component = iterm2.StatusBarComponent(
    short_description="Agent Status",
    detailed_description="Real-time agent orchestration status",
    knobs=[],
    exemplar="● 3 agents",
    update_cadence=1.0,
    identifier="com.orchestrator.status"
)

@iterm2.StatusBarRPC
async def status_coro(knobs):
    ready = len([s for s in app.all_sessions 
                 if await s.async_get_variable("user.status") == "ready"])
    working = len([s for s in app.all_sessions
                   if await s.async_get_variable("user.status") == "working"])
    return f"● {ready} ready, {working} working"

await component.async_register(connection, status_coro)
```

## Key Documentation Links

- API Reference: https://iterm2.com/python-api/
- Session: https://iterm2.com/python-api/session.html
- Notifications: https://iterm2.com/python-api/notifications.html
- Profile: https://iterm2.com/python-api/profile.html
- Examples: https://iterm2.com/python-api/examples/index.html
