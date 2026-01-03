# iTerm2 Profiles Reference for Multi-Agent Orchestration

This reference documents the iTerm2 Profile API for iterm-mcp's use cases: team-based visual distinction, agent session management, and state integration with AgentRegistry and NotificationManager.

**Table of Contents**
- [Quick Reference](#quick-reference)
- [Core Profile Concepts](#core-profile-concepts)
- [Visual Indicators](#visual-indicators)
- [Color Manipulation](#color-manipulation)
- [Async Patterns](#async-patterns)
- [Team-Based Profiles](#team-based-profiles)
- [Integration Points](#integration-points)
- [Examples](#examples)
- [Performance Notes](#performance-notes)

---

## Quick Reference

### Most Common Operations

```python
import iterm2

# Get a profile by GUID
profile = await iterm2.Profile.async_get(app, "profile-guid")

# Get default profile
default_profile = await iterm2.Profile.async_get_default(app)

# Read tab color
color = profile.tab_color  # Returns iterm2.color.Color object

# Set tab color (async)
await profile.async_set_tab_color(iterm2.color.Color(h, s, l))

# Read/write tab color visibility
is_visible = profile.use_tab_color
await profile.async_set_use_tab_color(True)

# Set badge text
await profile.async_set_badge_text("Team: DevOps")

# Get profile name
name = profile.name_
await profile.async_set_name("new-name")

# Rename and set as default
await profile.async_set_name("my-profile")
await profile.async_make_default()
```

---

## Core Profile Concepts

### Profile Identification

**Type**: Profile GUID, Name, or Direct Reference

Profiles are identified by:
- **GUID** (`profile.guid`): Immutable, globally unique identifier
- **Name** (`profile.name_`): Human-readable, mutable identifier

```python
# Get profile by GUID
profile = await iterm2.Profile.async_get(app, guid)

# Get default profile (commonly used as base)
default = await iterm2.Profile.async_get_default(app)

# Rename a profile
await profile.async_set_name("my-new-name")
```

**Best Practice**: Store GUIDs in AgentRegistry for persistent identification across sessions. Names can change, but GUIDs remain stable.

---

## Visual Indicators

### Tab Colors

**Type**: Boolean flag + `iterm2.color.Color` object

Tab colors provide the primary visual distinction for team identification.

```python
# Read current tab color
color = profile.tab_color  # Returns iterm2.color.Color or None

# Set tab color
await profile.async_set_tab_color(color)

# Toggle tab color visibility
is_enabled = profile.use_tab_color  # Read current state
await profile.async_set_use_tab_color(True)   # Enable tab color display
await profile.async_set_use_tab_color(False)  # Hide tab color
```

**Key Properties**:
- `use_tab_color` (bool): Whether tab color is displayed
- `tab_color` (iterm2.color.Color): The color itself

**Integration with Teams**: When registering an agent to a team, apply the team's color to the profile's tab.

### Badge Text and Appearance

**Type**: Text string with formatting options

Badges display over the terminal tab, useful for showing agent/team state.

```python
# Set badge text
await profile.async_set_badge_text("Team: DevOps")
await profile.async_set_badge_text("Status: Running")
await profile.async_set_badge_text("")  # Clear badge

# Configure badge appearance
await profile.async_set_badge_color(team_color)  # Match team color
await profile.async_set_badge_font("Monaco")
await profile.async_set_badge_max_width(100)
await profile.async_set_badge_max_height(50)
await profile.async_set_badge_top_margin(10)
await profile.async_set_badge_right_margin(10)

# Read badge properties
text = profile.badge_text_
font = profile.badge_font_
color = profile.badge_color_
max_width = profile.badge_max_width_
max_height = profile.badge_max_height_
top_margin = profile.badge_top_margin_
right_margin = profile.badge_right_margin_
```

**Best Practice**: Keep badge text short (<20 chars) and update it when agent status changes (pending, running, idle, blocked).

### Cursor and Visual Effects

**Type**: Cursor type, colors, effects

Useful for distinguishing sessions at a glance.

```python
# Cursor configuration
await profile.async_set_cursor_type(1)  # 1=underline, 2=vertical bar, 3=box
await profile.async_set_blinking_cursor(True)
await profile.async_set_cursor_boost(True)  # Brighter cursor
await profile.async_set_smart_cursor_color(True)  # Auto-contrast cursor
await profile.async_set_use_cursor_guide(True)  # Horizontal highlight
await profile.async_set_cursor_guide_color(guide_color)

# Read cursor properties
cursor_type = profile.cursor_type
is_blinking = profile.blinking_cursor
guide_enabled = profile.use_cursor_guide
guide_color = profile.cursor_guide_color
```

**Not typically used for team distinction**, but can indicate agent status:
- Blinking cursor = agent is busy
- Cursor guide = debugging session
- Box cursor = recording session

---

## Color Manipulation

### Color Representation

All profile colors use `iterm2.color.Color` with **HSL (Hue, Saturation, Lightness)** components:

```python
# Create a color
color = iterm2.color.Color(hue, saturation, lightness)

# Access components
h = color.hue          # 0-360 degrees
s = color.saturation   # 0-100 %
l = color.lightness    # 0-100 %

# For RGB conversion, use iterm2's built-in conversion
# (Not typically needed for visual distinction)
```

**HSL Advantages for Teams**:
- **Hue (0-360)**: Perfect for distributing unique colors across N teams
- **Saturation (0-100)**: Control color intensity (higher = more vivid)
- **Lightness (0-100)**: Control brightness (50 = pure color, 0 = black, 100 = white)

### Team Color Distribution

**Best Practice**: Assign evenly-distributed hues for team visual distinction.

```python
def get_team_color(team_index: int, total_teams: int,
                   saturation: int = 75, lightness: int = 40) -> iterm2.color.Color:
    """Get an HSL color for a team based on even hue distribution.

    Args:
        team_index: 0-based team index
        total_teams: Total number of teams
        saturation: 0-100, controls color intensity
        lightness: 0-100, controls brightness

    Returns:
        iterm2.color.Color with evenly-distributed hue
    """
    # Distribute hues evenly across the color wheel
    hue = (team_index / total_teams) * 360
    return iterm2.color.Color(hue, saturation, lightness)


# Example: 5 teams with unique colors
teams = ["backend", "frontend", "devops", "data", "ml"]
colors = {}
for idx, team in enumerate(teams):
    colors[team] = get_team_color(idx, len(teams))

# Apply to profiles
for team_name, color in colors.items():
    profile = get_or_create_profile(f"team-{team_name}")
    await profile.async_set_tab_color(color)
    await profile.async_set_use_tab_color(True)
```

### Common Color Presets

```python
# Red team (debugging)
RED = iterm2.color.Color(0, 100, 40)

# Green team (production)
GREEN = iterm2.color.Color(120, 100, 40)

# Blue team (development)
BLUE = iterm2.color.Color(220, 100, 40)

# Yellow team (testing)
YELLOW = iterm2.color.Color(60, 100, 40)

# Purple team (infrastructure)
PURPLE = iterm2.color.Color(270, 100, 40)

# Neutral (no team)
GRAY = iterm2.color.Color(0, 0, 50)
```

---

## Async Patterns

### Async/Await Pattern

All profile modifications use async/await. The Profile API never blocks.

```python
import asyncio
import iterm2

async def configure_profile_for_team(app: iterm2.Application,
                                     profile_guid: str,
                                     team_name: str,
                                     team_color: iterm2.color.Color):
    """Configure a profile for a team."""
    try:
        profile = await iterm2.Profile.async_get(app, profile_guid)

        # Set visual indicators
        await profile.async_set_tab_color(team_color)
        await profile.async_set_use_tab_color(True)
        await profile.async_set_badge_text(f"Team: {team_name}")
        await profile.async_set_badge_color(team_color)

    except Exception as e:
        logger.error(f"Failed to configure profile: {e}")


# Usage in iterm-mcp
async with iterm2.Application() as app:
    await configure_profile_for_team(app, guid, "devops", PURPLE)
```

### Batch Profile Updates

When updating multiple profiles, use `asyncio.gather()` for parallel execution:

```python
async def update_all_team_profiles(app: iterm2.Application,
                                   team_profiles: Dict[str, Tuple[str, iterm2.color.Color]]):
    """Update multiple profiles efficiently.

    Args:
        app: iTerm2 application instance
        team_profiles: {team_name: (profile_guid, color)}
    """
    tasks = []

    for team_name, (profile_guid, color) in team_profiles.items():
        task = configure_profile_for_team(app, profile_guid, team_name, color)
        tasks.append(task)

    # Execute all in parallel
    await asyncio.gather(*tasks, return_exceptions=True)
```

### Error Handling

```python
async def safe_set_tab_color(profile: iterm2.Profile,
                             color: iterm2.color.Color,
                             logger) -> bool:
    """Safely set tab color with error handling.

    Args:
        profile: Target profile
        color: Color to set
        logger: Logger instance

    Returns:
        True if successful, False if failed
    """
    try:
        await profile.async_set_tab_color(color)
        logger.debug(f"Set tab color for {profile.name_}")
        return True
    except iterm2.RPCException as e:
        logger.error(f"RPC error setting color: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False
```

---

## Team-Based Profiles

### Profile Lifecycle for Teams

When a team is created in AgentRegistry, create or configure a corresponding profile:

```python
from core.agents import Team
import iterm2

async def create_team_profile(app: iterm2.Application,
                              team: Team,
                              team_color: iterm2.color.Color,
                              base_profile: iterm2.Profile = None) -> iterm2.Profile:
    """Create or get a profile for a team.

    Args:
        app: iTerm2 application instance
        team: Team object from AgentRegistry
        team_color: HSL color for the team
        base_profile: Optional base profile to clone from

    Returns:
        Configured profile for the team
    """
    profile_name = f"team-{team.name}"

    # In production, you would look up existing profile by name
    # For now, assume we have a reference to the profile
    profile = base_profile or await iterm2.Profile.async_get_default(app)

    # Configure for team
    await profile.async_set_name(profile_name)
    await profile.async_set_tab_color(team_color)
    await profile.async_set_use_tab_color(True)
    await profile.async_set_badge_text(f"Team: {team.name}")
    await profile.async_set_badge_color(team_color)

    # Disable zsh autocorrect for agent-friendly shell behavior
    await disable_shell_automation(profile)

    return profile


async def disable_shell_automation(profile: iterm2.Profile):
    """Disable zsh autocorrect and other automation-hostile features.

    Agents benefit from predictable shell behavior without autocorrection
    that might alter command output.
    """
    # Note: These are example properties; actual iTerm2 API may vary
    # Consult full API documentation for shell-specific settings

    # Disable CORRECT_PROMT and other zsh automations
    # This typically requires setting environment variables or shell config
    pass
```

### Integration with AgentRegistry

Store profile GUIDs in agent metadata for session recovery:

```python
from core.agents import AgentRegistry
import iterm2

async def register_agent_with_profile(registry: AgentRegistry,
                                      agent_name: str,
                                      session_id: str,
                                      team_name: str,
                                      profile: iterm2.Profile):
    """Register an agent and link its profile.

    Args:
        registry: AgentRegistry instance
        agent_name: Unique agent name
        session_id: iTerm session ID
        team_name: Team name
        profile: Configured profile for the agent
    """
    metadata = {
        "profile_guid": profile.guid,
        "profile_name": profile.name_,
        "team": team_name,
        "color_hue": str(profile.tab_color.hue) if profile.tab_color else "0"
    }

    agent = registry.register_agent(
        name=agent_name,
        session_id=session_id,
        teams=[team_name],
        metadata=metadata
    )

    return agent
```

### Session-Profile Relationships

Profiles can be applied per-session without modifying the global profile:

```python
import iterm2

async def apply_profile_to_session(session: iterm2.Session,
                                   profile: iterm2.Profile):
    """Apply profile settings to a session (non-persistent).

    Uses async_set_profile_properties() to apply profile colors/badges
    to a session without modifying the underlying profile definition.

    Args:
        session: Target iTerm session
        profile: Profile to apply from
    """
    # Create a LocalWriteOnlyProfile with desired properties
    props = iterm2.LocalWriteOnlyProfile()

    # Set tab color
    if profile.tab_color:
        props.set_tab_color(profile.tab_color)
    if profile.use_tab_color:
        props.set_use_tab_color(True)

    # Set badge
    if profile.badge_text_:
        props.set_badge_text(profile.badge_text_)
    if profile.badge_color_:
        props.set_badge_color(profile.badge_color_)

    # Apply to session
    await session.async_set_profile_properties(props)
```

---

## Integration Points

### With AgentRegistry

**Use Case**: Track which profile each agent is using

```python
class EnhancedAgentRegistry(AgentRegistry):
    """Extended registry with profile management."""

    async def apply_team_colors(self, app: iterm2.Application):
        """Apply team colors to all agent profiles."""
        teams = self.list_teams()
        agents_by_team = {}

        # Group agents by team
        for team in teams:
            team_agents = self.list_agents(team=team.name)
            agents_by_team[team.name] = team_agents

        # Apply colors
        for team in teams:
            color = get_team_color_for_team(team)
            agents = agents_by_team.get(team.name, [])

            for agent in agents:
                profile_guid = agent.metadata.get("profile_guid")
                if profile_guid:
                    profile = await iterm2.Profile.async_get(app, profile_guid)
                    await profile.async_set_tab_color(color)
```

### With NotificationManager

**Use Case**: Update badges when agent status changes

```python
class NotificationManager:
    """Manages agent status notifications with profile updates."""

    def __init__(self, app: iterm2.Application, registry: AgentRegistry):
        self.app = app
        self.registry = registry

    async def update_agent_status(self, agent_name: str, status: str):
        """Update agent status in badge.

        Args:
            agent_name: Agent name
            status: New status (e.g., "running", "idle", "error")
        """
        agent = self.registry.get_agent(agent_name)
        if not agent:
            return

        profile_guid = agent.metadata.get("profile_guid")
        if not profile_guid:
            return

        profile = await iterm2.Profile.async_get(self.app, profile_guid)

        # Update badge text with status
        team = agent.teams[0] if agent.teams else "unassigned"
        await profile.async_set_badge_text(f"{team}: {status}")

        # Update tab color based on status
        if status == "error":
            await profile.async_set_tab_color(RED)
        elif status == "running":
            await profile.async_set_tab_color(YELLOW)
        elif status == "idle":
            team_color = get_team_color_for_agent(agent)
            await profile.async_set_tab_color(team_color)
```

### With Session Management

**Use Case**: Apply team colors when creating new sessions

```python
from core.session import ItermSession

async def create_team_session(terminal,
                              team_name: str,
                              agent_name: str,
                              profile: iterm2.Profile) -> ItermSession:
    """Create a new session with team profile applied.

    Args:
        terminal: ItermTerminal instance
        team_name: Team name
        agent_name: Agent name
        profile: Team profile

    Returns:
        New ItermSession with profile applied
    """
    # Create new session
    session = await terminal.create_tab(profile_guid=profile.guid)

    # Apply profile colors
    await apply_profile_to_session(session, profile)

    # Wrap in ItermSession
    wrapped = ItermSession(session, name=f"{team_name}/{agent_name}")

    return wrapped
```

---

## Examples

### Example 1: Team-Based Color System

```python
import asyncio
import iterm2
from core.agents import AgentRegistry

async def setup_teams_with_colors():
    """Complete example: Create teams and assign distinct colors."""
    async with iterm2.Application() as app:
        registry = AgentRegistry()

        # Define teams
        teams = [
            ("backend", "Backend team"),
            ("frontend", "Frontend team"),
            ("devops", "DevOps team"),
        ]

        # Get base profile
        default_profile = await iterm2.Profile.async_get_default(app)

        # Create teams and profiles
        for idx, (team_name, description) in enumerate(teams):
            # Create team in registry
            team = registry.create_team(team_name, description)

            # Calculate color (evenly distributed hue)
            color = get_team_color(idx, len(teams))

            # Configure profile for team
            # (In real usage, you'd create/lookup by name)
            profile = default_profile
            await profile.async_set_name(f"team-{team_name}")
            await profile.async_set_tab_color(color)
            await profile.async_set_use_tab_color(True)
            await profile.async_set_badge_text(f"Team: {team_name}")
            await profile.async_set_badge_color(color)

            # Store profile GUID in team metadata
            team.metadata = {"profile_guid": profile.guid}

            print(f"Created team {team_name} with color hue={color.hue}")
```

### Example 2: Agent Registration with Profile

```python
async def register_agent_with_team(app: iterm2.Application,
                                   registry: AgentRegistry,
                                   agent_name: str,
                                   session_id: str,
                                   team_name: str):
    """Register an agent and apply team profile."""

    # Get team and its profile
    team = registry.get_team(team_name)
    if not team:
        raise ValueError(f"Team {team_name} not found")

    profile_guid = team.metadata.get("profile_guid")
    if not profile_guid:
        raise ValueError(f"Team {team_name} has no profile configured")

    # Get profile
    profile = await iterm2.Profile.async_get(app, profile_guid)

    # Register agent
    agent = registry.register_agent(
        name=agent_name,
        session_id=session_id,
        teams=[team_name],
        metadata={
            "profile_guid": profile.guid,
            "profile_name": profile.name_,
        }
    )

    return agent
```

### Example 3: Status Badge Updates

```python
class AgentStatusMonitor:
    """Monitor agent status and update visual indicators."""

    def __init__(self, app: iterm2.Application, registry: AgentRegistry):
        self.app = app
        self.registry = registry

    async def update_status(self, agent_name: str, status: str,
                            info: str = ""):
        """Update agent status badge.

        Args:
            agent_name: Agent name
            status: Status key (e.g., "running", "idle", "error", "blocked")
            info: Optional status info (e.g., "compiling", "waiting for user")
        """
        agent = self.registry.get_agent(agent_name)
        if not agent:
            return

        profile_guid = agent.metadata.get("profile_guid")
        if not profile_guid:
            return

        profile = await iterm2.Profile.async_get(self.app, profile_guid)

        # Build badge text
        team = agent.teams[0] if agent.teams else "?"
        badge_parts = [team, status.upper()]
        if info:
            badge_parts.append(info)
        badge_text = " | ".join(badge_parts)

        # Update badge (keep short for tab display)
        if len(badge_text) > 30:
            badge_text = badge_text[:27] + "..."

        await profile.async_set_badge_text(badge_text)

        # Update tab color based on status
        status_colors = {
            "running": YELLOW,
            "idle": GRAY,
            "error": RED,
            "blocked": ORANGE,
            "success": GREEN,
        }

        color = status_colors.get(status)
        if color:
            await profile.async_set_tab_color(color)
```

### Example 4: Profile Session Shortcuts

```python
class ProfileManager:
    """Centralized profile management for agents."""

    def __init__(self, app: iterm2.Application, registry: AgentRegistry):
        self.app = app
        self.registry = registry
        self._profile_cache = {}

    async def get_agent_profile(self, agent_name: str) -> iterm2.Profile:
        """Get cached profile for an agent."""
        if agent_name in self._profile_cache:
            return self._profile_cache[agent_name]

        agent = self.registry.get_agent(agent_name)
        if not agent:
            raise ValueError(f"Agent {agent_name} not found")

        profile_guid = agent.metadata.get("profile_guid")
        if not profile_guid:
            raise ValueError(f"Agent {agent_name} has no profile")

        profile = await iterm2.Profile.async_get(self.app, profile_guid)
        self._profile_cache[agent_name] = profile

        return profile

    async def set_agent_status(self, agent_name: str, status: str):
        """Quick status update for an agent."""
        profile = await self.get_agent_profile(agent_name)
        agent = self.registry.get_agent(agent_name)

        team = agent.teams[0] if agent.teams else "?"
        await profile.async_set_badge_text(f"{team}: {status}")

    async def clear_profile_cache(self):
        """Clear cached profiles (call after team updates)."""
        self._profile_cache.clear()
```

---

## Performance Notes

### Profile Lookup Performance

- **By GUID**: O(1) lookup via iTerm2 API
- **By Name**: Requires iteration; cache results
- **First Access**: Initial profile retrieval is slower; cache frequently-accessed profiles

### Color Updates

- **Async**: Profile color updates are non-blocking
- **Batch Updates**: Use `asyncio.gather()` for multiple profiles
- **No Redraws**: Tab color changes don't require session refresh

### Memory Considerations

- **Profile Objects**: Keep a cache of frequently-accessed profiles
- **Color Objects**: iterm2.color.Color is lightweight; safe to create as needed
- **Metadata**: Store profile GUIDs in AgentRegistry metadata, not full profile objects

### Best Practices

1. **Cache Profile GUIDs**: Store in AgentRegistry.metadata, not profile objects
2. **Lazy Load Profiles**: Fetch from iTerm2 only when needed
3. **Batch Operations**: Use asyncio.gather() for multiple profiles
4. **Error Recovery**: Implement retry logic for transient RPC errors
5. **Validation**: Verify profile exists before attempting modifications

---

## Full Method Reference

### Read-Only Properties

| Property | Type | Description |
|----------|------|-------------|
| `guid` | str | Immutable globally unique identifier |
| `name_` | str | Current profile name (mutable via async_set_name) |
| `tab_color` | Color \| None | Current tab color |
| `use_tab_color` | bool | Whether tab color is displayed |
| `badge_text_` | str | Current badge text |
| `badge_color_` | Color \| None | Current badge color |
| `badge_font_` | str | Badge font name |
| `badge_max_width_` | int | Max badge width in pixels |
| `badge_max_height_` | int | Max badge height in pixels |
| `badge_top_margin_` | int | Top margin in pixels |
| `badge_right_margin_` | int | Right margin in pixels |
| `cursor_type` | int | 1=underline, 2=vertical, 3=box |
| `blinking_cursor` | bool | Whether cursor blinks |
| `use_cursor_guide` | bool | Whether horizontal guide is shown |
| `cursor_guide_color` | Color \| None | Color of cursor guide |

### Async Setter Methods

| Method | Arguments | Purpose |
|--------|-----------|---------|
| `async_set_tab_color()` | color: Color | Set tab color |
| `async_set_use_tab_color()` | enabled: bool | Toggle tab color display |
| `async_set_badge_text()` | text: str | Update badge text |
| `async_set_badge_color()` | color: Color | Set badge color |
| `async_set_badge_font()` | font: str | Set badge font |
| `async_set_badge_max_width()` | pixels: int | Set max width |
| `async_set_badge_max_height()` | pixels: int | Set max height |
| `async_set_badge_top_margin()` | pixels: int | Set top margin |
| `async_set_badge_right_margin()` | pixels: int | Set right margin |
| `async_set_name()` | name: str | Rename profile |
| `async_set_cursor_type()` | type: int | Set cursor style |
| `async_set_blinking_cursor()` | enabled: bool | Toggle cursor blink |
| `async_set_use_cursor_guide()` | enabled: bool | Toggle cursor guide |
| `async_set_cursor_guide_color()` | color: Color | Set guide color |
| `async_make_default()` | — | Make this the default profile |

### Static Methods

| Method | Arguments | Returns |
|--------|-----------|---------|
| `async_get()` | app, guid | Profile object |
| `async_get_default()` | app | Default Profile |

---

## Related Documentation

- [iterm2.color.Color API](https://iterm2.com/python-api/color.html)
- [Session API Reference](./SESSION.md)
- [Agent Registry API](./AGENTS.md)
- [iTerm2 Official Profile Docs](https://iterm2.com/python-api/profile.html)
