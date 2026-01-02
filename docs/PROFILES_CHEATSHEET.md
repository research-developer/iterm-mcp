# Profile API Cheat Sheet

Minimal reference for common profile operations in iterm-mcp.

---

## Import and Setup

```python
import iterm2
import asyncio

async def main():
    async with iterm2.Application() as app:
        # Use app in async context
        pass

# Or for server/MCP context:
# app is typically passed to your function
```

---

## Getting Profiles

```python
# Get by GUID (recommended for agents)
profile = await iterm2.Profile.async_get(app, "guid-string")

# Get default profile
default = await iterm2.Profile.async_get_default(app)

# Handle not found
if profile is None:
    print("Profile not found")
```

---

## Tab Colors (Primary Use Case)

```python
# Create a color (HSL: Hue, Saturation, Lightness)
color = iterm2.color.Color(hue=120, saturation=100, lightness=40)

# Apply color
await profile.async_set_tab_color(color)

# Enable tab color display
await profile.async_set_use_tab_color(True)

# Read current
current_color = profile.tab_color
is_enabled = profile.use_tab_color

# Reset to no color
await profile.async_set_use_tab_color(False)
```

---

## Common Colors

```python
# Team colors (evenly distributed hues)
RED = iterm2.color.Color(0, 100, 40)           # team 0
GREEN = iterm2.color.Color(120, 100, 40)       # team 1
BLUE = iterm2.color.Color(220, 100, 40)        # team 2
YELLOW = iterm2.color.Color(60, 100, 40)       # team 3
PURPLE = iterm2.color.Color(270, 100, 40)      # team 4
GRAY = iterm2.color.Color(0, 0, 50)            # neutral

# Status colors
RUNNING = YELLOW
IDLE = GRAY
ERROR = RED
SUCCESS = GREEN
BLOCKED = iterm2.color.Color(30, 100, 40)
```

---

## Badge Text

```python
# Set badge (shows over tab)
await profile.async_set_badge_text("Team: DevOps")

# Clear badge
await profile.async_set_badge_text("")

# Keep short (<30 chars)
badge = f"{team}: {status}"[:30]
await profile.async_set_badge_text(badge)

# Read current
text = profile.badge_text_
```

---

## Badge Appearance

```python
# Color
await profile.async_set_badge_color(color)

# Font
await profile.async_set_badge_font("Monaco")

# Size/Position
await profile.async_set_badge_max_width(100)
await profile.async_set_badge_max_height(50)
await profile.async_set_badge_top_margin(10)
await profile.async_set_badge_right_margin(10)

# Read current
font = profile.badge_font_
color = profile.badge_color_
```

---

## Profile Properties

```python
# Identity
name = profile.name_
guid = profile.guid

# Rename
await profile.async_set_name("new-name")

# Make default
await profile.async_set_name("my-profile")
await profile.async_make_default()
```

---

## Batch Updates (Multiple Profiles)

```python
import asyncio

async def update_all_profiles(app, profile_guids, color):
    """Update multiple profiles in parallel."""
    tasks = []
    for guid in profile_guids:
        profile = await iterm2.Profile.async_get(app, guid)
        if profile:
            tasks.append(profile.async_set_tab_color(color))

    await asyncio.gather(*tasks, return_exceptions=True)
```

---

## Apply Profile to Session

```python
# Apply profile colors to a session (temporary, not persistent)
props = iterm2.LocalWriteOnlyProfile()

if profile.tab_color:
    props.set_tab_color(profile.tab_color)
if profile.badge_text_:
    props.set_badge_text(profile.badge_text_)

await session.async_set_profile_properties(props)
```

---

## Error Handling

```python
async def safe_set_color(profile, color, logger):
    """Safe color update with error handling."""
    try:
        await profile.async_set_tab_color(color)
        return True
    except iterm2.RPCException as e:
        logger.error(f"RPC error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False
```

---

## Cursor Settings

```python
# Cursor type: 1=underline, 2=vertical, 3=box
await profile.async_set_cursor_type(2)

# Blink
await profile.async_set_blinking_cursor(True)

# Boost brightness
await profile.async_set_cursor_boost(True)

# Smart color (auto-contrast)
await profile.async_set_smart_cursor_color(True)

# Cursor guide (horizontal highlight)
await profile.async_set_use_cursor_guide(True)
await profile.async_set_cursor_guide_color(color)
```

---

## Generate Team Colors

```python
def team_color(index: int, total_teams: int) -> iterm2.color.Color:
    """Generate evenly-distributed team color.

    Args:
        index: 0-based team index
        total_teams: Total teams

    Returns:
        Color with evenly-distributed hue
    """
    hue = (index / total_teams) * 360
    return iterm2.color.Color(hue, 75, 40)

# Usage
colors = [team_color(i, 5) for i in range(5)]
```

---

## Store Profile in Agent Metadata

```python
# Register agent with profile GUID
agent_metadata = {
    "profile_guid": profile.guid,
    "profile_name": profile.name_,
    "team": "devops"
}

agent = registry.register_agent(
    name="claude-agent-1",
    session_id="session-123",
    teams=["devops"],
    metadata=agent_metadata
)
```

---

## Retrieve and Update Agent Profile

```python
# Later: retrieve agent and update profile
agent = registry.get_agent("claude-agent-1")
profile_guid = agent.metadata.get("profile_guid")

if profile_guid:
    profile = await iterm2.Profile.async_get(app, profile_guid)
    await profile.async_set_badge_text("Status: Running")
```

---

## Profile Caching Pattern

```python
class ProfileCache:
    """Simple profile cache to avoid repeated lookups."""

    def __init__(self):
        self._cache = {}

    async def get(self, app, guid):
        """Get profile with caching."""
        if guid in self._cache:
            return self._cache[guid]

        profile = await iterm2.Profile.async_get(app, guid)
        if profile:
            self._cache[guid] = profile
        return profile

    def clear(self):
        """Clear cache after updates."""
        self._cache.clear()
```

---

## Minimal Complete Example

```python
import iterm2

async def demo():
    """Complete working example."""
    async with iterm2.Application() as app:
        # Get profile
        default = await iterm2.Profile.async_get_default(app)

        # Create color
        color = iterm2.color.Color(120, 100, 40)  # Green

        # Set color and badge
        await default.async_set_tab_color(color)
        await default.async_set_use_tab_color(True)
        await default.async_set_badge_text("Team: Backend")

        print(f"Updated profile: {default.name_}")

# Run it
asyncio.run(demo())
```

---

## Properties Reference

| Property | Type | Read? | Write? |
|----------|------|-------|--------|
| `guid` | str | ✓ | ✗ |
| `name_` | str | ✓ | `async_set_name()` |
| `tab_color` | Color | ✓ | `async_set_tab_color()` |
| `use_tab_color` | bool | ✓ | `async_set_use_tab_color()` |
| `badge_text_` | str | ✓ | `async_set_badge_text()` |
| `badge_color_` | Color | ✓ | `async_set_badge_color()` |
| `badge_font_` | str | ✓ | `async_set_badge_font()` |
| `cursor_type` | int | ✓ | `async_set_cursor_type()` |
| `blinking_cursor` | bool | ✓ | `async_set_blinking_cursor()` |

---

## Common Mistakes

```python
# WRONG: Creating color with wrong range
color = iterm2.color.Color(1.0, 1.0, 1.0)  # ✗ Not normalized

# RIGHT: Use 0-360 for hue, 0-100 for saturation/lightness
color = iterm2.color.Color(120, 100, 50)  # ✓

# WRONG: Forgetting to enable tab color visibility
await profile.async_set_tab_color(color)  # Color set but not visible

# RIGHT: Enable display
await profile.async_set_use_tab_color(True)
await profile.async_set_tab_color(color)

# WRONG: Too-long badge text
await profile.async_set_badge_text("Very Long Status That Won't Fit")

# RIGHT: Keep it short
await profile.async_set_badge_text("Team: DevOps")

# WRONG: Synchronous call (will error)
profile.async_set_tab_color(color)  # ✗ Not awaited

# RIGHT: Await async operations
await profile.async_set_tab_color(color)  # ✓
```

---

## Full API Reference

See `/Users/preston/MCP/iterm-mcp/docs/PROFILES.md` for complete documentation.

See `/Users/preston/MCP/iterm-mcp/docs/PROFILES_INTEGRATION.md` for implementation examples.
