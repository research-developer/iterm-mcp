# split_session Visual Guide

## Direction Visualization

```
Starting with a single session labeled "Main":

┌────────────────┐
│     Main       │
│                │
└────────────────┘


1. Split "below" (direction: "below")
   Result: New pane appears BELOW the target

┌────────────────┐
│     Main       │
├────────────────┤
│     Below      │  ← New pane
└────────────────┘


2. Split "above" (direction: "above")
   Result: New pane appears ABOVE the target

┌────────────────┐
│     Above      │  ← New pane
├────────────────┤
│     Main       │
└────────────────┘


3. Split "right" (direction: "right")
   Result: New pane appears to the RIGHT of target

┌────────┬────────┐
│  Main  │ Right  │  ← New pane
│        │        │
└────────┴────────┘


4. Split "left" (direction: "left")
   Result: New pane appears to the LEFT of target

┌────────┬────────┐
│  Left  │  Main  │
│        │        │  ← New pane on left
└────────┴────────┘
```

## Progressive Layout Building

You can build complex layouts by making multiple splits:

```
Step 1: Start with Main
┌────────────────┐
│     Main       │
└────────────────┘

Step 2: Split Main → right → Editor
┌─────────┬──────┐
│  Main   │Editor│
└─────────┴──────┘

Step 3: Split Main → below → Terminal
┌─────────┬──────┐
│  Main   │Editor│
├─────────┼──────┤
│Terminal │      │
└─────────┴──────┘

Step 4: Split Editor → below → Tests
┌─────────┬──────┐
│  Main   │Editor│
├─────────┼──────┤
│Terminal │Tests │
└─────────┴──────┘

Final Layout:
┌─────────┬──────┐
│  Main   │Editor│
│         ├──────┤
├─────────┤Tests │
│Terminal │      │
└─────────┴──────┘
```

## Orchestrator Pattern

Create a central orchestrator with worker panes:

```
Initial state:
┌──────────────┐
│ Orchestrator │
└──────────────┘

After splitting right 3 times:
┌──────────────┬────────┬────────┬────────┐
│ Orchestrator │Worker1 │Worker2 │Worker3 │
└──────────────┴────────┴────────┴────────┘

Each worker can be:
- Registered as an agent
- Assigned to a team
- Given a specific command
- Monitored for completion
```

## Team Organization

Use teams to visually group related sessions with colors:

```
Frontend Team (blue tabs):
┌────────────┬────────────┬────────────┐
│ Frontend-1 │ Frontend-2 │ Frontend-3 │
│  [BLUE]    │  [BLUE]    │  [BLUE]    │
└────────────┴────────────┴────────────┘

Backend Team (green tabs):
┌────────────┬────────────┬────────────┐
│ Backend-1  │ Backend-2  │ Backend-3  │
│  [GREEN]   │  [GREEN]   │  [GREEN]   │
└────────────┴────────────┴────────────┘
```

## Debugging Layout

Create a debugging environment with specialized panes:

```
┌──────────────────┬──────────────┐
│   Main Code      │   Logs       │
│                  │              │
├──────────────────┴──────────────┤
│         Python Debugger         │
│         (pdb/ipdb)              │
└─────────────────────────────────┘

Split sequence:
1. Main Code → right → Logs
2. Main Code → below → Debugger
```

## IDE-style Layout

Build a development environment:

```
┌──────────────┬──────────────┐
│   Editor     │   Tests      │
│   (vim/code) │   (watch)    │
├──────────────┼──────────────┤
│   Terminal   │   Server     │
│   (bash)     │   (npm run)  │
└──────────────┴──────────────┘

Split sequence:
1. Editor → right → Tests
2. Editor → below → Terminal
3. Tests → below → Server
```

## Direction Reference Quick Guide

```
           ┌─────────────┐
           │    above    │
           │  (before)   │
           ├─────────────┤
┌──────────┤   TARGET    ├──────────┐
│  left    │   SESSION   │  right   │
│ (before) │             │ (after)  │
└──────────┴─────────────┴──────────┘
           │    below    │
           │   (after)   │
           └─────────────┘

Mapping to iTerm2 API:
- above: vertical=False, before=True   (horizontal split, new on top)
- below: vertical=False, before=False  (horizontal split, new on bottom)
- left:  vertical=True,  before=True   (vertical split, new on left)
- right: vertical=True,  before=False  (vertical split, new on right)
```

## Usage Flow

```
1. Identify Target Session
   ├─ By session_id: "w0t0p0:s123456"
   ├─ By agent name: "orchestrator"
   └─ By session name: "MainSession"

2. Choose Direction
   ├─ above (horizontal, before)
   ├─ below (horizontal, after)
   ├─ left (vertical, before)
   └─ right (vertical, after)

3. Configure New Session (optional)
   ├─ Name the new session
   ├─ Set iTerm2 profile
   ├─ Register as agent
   ├─ Assign to team
   ├─ Run initial command
   ├─ Launch AI agent CLI
   └─ Enable monitoring

4. Execute Split
   └─ Returns new session details

5. Use New Session
   ├─ Send commands (write_to_sessions)
   ├─ Read output (read_sessions)
   └─ Manage as agent (register_agent, manage_teams)
```

## Common Patterns

### Pattern 1: Spawn on Demand
```
[Orchestrator detects need for worker]
      ↓
split_session(orchestrator, "right", worker_config)
      ↓
[New worker ready]
```

### Pattern 2: Debug Session
```
[Development session running]
      ↓
split_session(dev, "below", debugger_config)
      ↓
[Debugger attached]
```

### Pattern 3: Progressive Layout
```
[Single session]
      ↓
split_session(main, "right", editor)
      ↓
split_session(main, "below", terminal)
      ↓
split_session(editor, "below", tests)
      ↓
[Complete IDE layout]
```

### Pattern 4: Team Formation
```
[Orchestrator exists]
      ↓
for each worker in workers:
    split_session(orchestrator, "right", worker, team="workers")
      ↓
[Team assembled with color coding]
```

## API Example

```json
{
  "target": {
    "agent": "orchestrator"
  },
  "direction": "right",
  "name": "Worker1",
  "profile": "MCP Agent",
  "command": "python worker.py --task=build",
  "agent": "worker-1",
  "team": "workers",
  "monitor": true,
  "role": "builder"
}
```

## Response Example

```json
{
  "session_id": "w0t0p0:s789012",
  "name": "Worker1",
  "agent": "worker-1",
  "persistent_id": "persistent-abc123",
  "source_session_id": "w0t0p0:s123456"
}
```

Now you can:
- Send commands to session_id
- Query agent "worker-1"
- Reference by name "Worker1"
- Reconnect via persistent_id
