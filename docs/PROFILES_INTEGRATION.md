# Profile Integration Guide for iterm-mcp

Quick implementation guide for adding profile-based team visual distinction to iterm-mcp's AgentRegistry and NotificationManager.

---

## 1. Profile Manager Module

Create `core/profiles.py` for centralized profile operations:

```python
"""Profile management for team-based visual distinction."""

import asyncio
import iterm2
from typing import Dict, Optional, Tuple
from core.agents import AgentRegistry, Team

# Standard colors for team distinction
TEAM_COLORS = {
    # Using HSL: (hue, saturation, lightness)
    "backend": iterm2.color.Color(0, 100, 40),      # Red
    "frontend": iterm2.color.Color(120, 100, 40),   # Green
    "devops": iterm2.color.Color(220, 100, 40),     # Blue
    "data": iterm2.color.Color(60, 100, 40),        # Yellow
    "ml": iterm2.color.Color(270, 100, 40),         # Purple
}

# Status colors (override team colors when needed)
STATUS_COLORS = {
    "running": iterm2.color.Color(60, 100, 40),     # Yellow
    "idle": iterm2.color.Color(0, 0, 50),           # Gray
    "error": iterm2.color.Color(0, 100, 40),        # Red
    "blocked": iterm2.color.Color(30, 100, 40),     # Orange
    "success": iterm2.color.Color(120, 100, 40),    # Green
}


class ProfileManager:
    """Manages iTerm2 profiles for agent team visualization."""

    def __init__(self, app: iterm2.Application, registry: AgentRegistry):
        """Initialize profile manager.

        Args:
            app: iTerm2 Application instance
            registry: AgentRegistry instance for agent metadata
        """
        self.app = app
        self.registry = registry
        self._profile_cache: Dict[str, iterm2.Profile] = {}
        self._team_profile_map: Dict[str, str] = {}  # team_name -> profile_guid

    async def get_profile_by_guid(self, guid: str) -> Optional[iterm2.Profile]:
        """Get profile with caching.

        Args:
            guid: Profile GUID

        Returns:
            Profile object or None if not found
        """
        if guid in self._profile_cache:
            return self._profile_cache[guid]

        try:
            profile = await iterm2.Profile.async_get(self.app, guid)
            self._profile_cache[guid] = profile
            return profile
        except Exception as e:
            return None

    async def get_or_create_team_profile(self, team: Team) -> iterm2.Profile:
        """Get or create a profile for a team.

        Args:
            team: Team object from AgentRegistry

        Returns:
            Configured profile for the team
        """
        # Check if team already has a profile
        if team.name in self._team_profile_map:
            guid = self._team_profile_map[team.name]
            profile = await self.get_profile_by_guid(guid)
            if profile:
                return profile

        # Create new profile from default
        default_profile = await iterm2.Profile.async_get_default(self.app)
        profile_name = f"team-{team.name}"

        await default_profile.async_set_name(profile_name)

        # Get team color
        color = TEAM_COLORS.get(team.name)
        if not color:
            # Generate color from team index
            teams = self.registry.list_teams()
            idx = teams.index(team) if team in teams else 0
            hue = (idx / max(len(teams), 1)) * 360
            color = iterm2.color.Color(hue, 75, 40)

        # Configure profile
        await default_profile.async_set_tab_color(color)
        await default_profile.async_set_use_tab_color(True)
        await default_profile.async_set_badge_text(f"Team: {team.name}")
        await default_profile.async_set_badge_color(color)

        # Cache
        self._team_profile_map[team.name] = default_profile.guid
        self._profile_cache[default_profile.guid] = default_profile

        return default_profile

    async def set_agent_status(self, agent_name: str, status: str, info: str = ""):
        """Update agent status badge.

        Args:
            agent_name: Agent name
            status: Status key (running, idle, error, blocked, success)
            info: Optional status info (e.g., "compiling")
        """
        agent = self.registry.get_agent(agent_name)
        if not agent:
            return

        profile_guid = agent.metadata.get("profile_guid")
        if not profile_guid:
            return

        profile = await self.get_profile_by_guid(profile_guid)
        if not profile:
            return

        # Build badge text
        team = agent.teams[0] if agent.teams else "?"
        badge_parts = [team, status.upper()]
        if info:
            badge_parts.append(info)
        badge_text = " | ".join(badge_parts)

        # Keep badge text short for tab display
        if len(badge_text) > 30:
            badge_text = badge_text[:27] + "..."

        try:
            await profile.async_set_badge_text(badge_text)

            # Update tab color based on status
            color = STATUS_COLORS.get(status)
            if color:
                await profile.async_set_tab_color(color)
        except Exception as e:
            # Log error but don't crash
            pass

    async def reset_agent_to_team_color(self, agent_name: str):
        """Reset agent profile to team color (from status color).

        Args:
            agent_name: Agent name
        """
        agent = self.registry.get_agent(agent_name)
        if not agent or not agent.teams:
            return

        profile_guid = agent.metadata.get("profile_guid")
        if not profile_guid:
            return

        profile = await self.get_profile_by_guid(profile_guid)
        if not profile:
            return

        team_name = agent.teams[0]
        color = TEAM_COLORS.get(team_name)
        if not color:
            return

        try:
            await profile.async_set_tab_color(color)
            badge = f"{team_name.upper()}: IDLE"
            await profile.async_set_badge_text(badge)
        except Exception as e:
            pass

    async def apply_profile_to_session(self, session: iterm2.Session,
                                       profile: iterm2.Profile):
        """Apply profile visual settings to a session.

        Args:
            session: iTerm2 session
            profile: Profile to apply from
        """
        try:
            props = iterm2.LocalWriteOnlyProfile()

            if profile.tab_color:
                props.set_tab_color(profile.tab_color)
            if profile.use_tab_color:
                props.set_use_tab_color(True)
            if profile.badge_text_:
                props.set_badge_text(profile.badge_text_)
            if profile.badge_color_:
                props.set_badge_color(profile.badge_color_)

            await session.async_set_profile_properties(props)
        except Exception as e:
            pass

    def clear_cache(self):
        """Clear profile cache (call after team updates)."""
        self._profile_cache.clear()
        self._team_profile_map.clear()
```

---

## 2. Integration with AgentRegistry

Extend AgentRegistry to track profile GUIDs:

```python
# In core/agents.py - modify register_agent method

async def register_agent_with_profile(self,
                                      name: str,
                                      session_id: str,
                                      teams: Optional[List[str]] = None,
                                      profile_guid: Optional[str] = None,
                                      metadata: Optional[Dict[str, str]] = None) -> Agent:
    """Register agent with profile information.

    Args:
        name: Unique agent name
        session_id: iTerm session ID
        teams: Team names
        profile_guid: Optional profile GUID for visual distinction
        metadata: Optional metadata dict

    Returns:
        Created/updated Agent
    """
    if metadata is None:
        metadata = {}

    if profile_guid:
        metadata["profile_guid"] = profile_guid

    return self.register_agent(
        name=name,
        session_id=session_id,
        teams=teams or [],
        metadata=metadata
    )
```

---

## 3. Integration with NotificationManager

Add profile updates to NotificationManager:

```python
# In core/feedback.py or new core/notifications.py

class NotificationManager:
    """Manage agent notifications with profile updates."""

    def __init__(self, app: iterm2.Application,
                 registry: AgentRegistry,
                 profile_manager: ProfileManager = None):
        self.app = app
        self.registry = registry
        self.profile_manager = profile_manager

    async def notify_agent_status(self, agent_name: str, status: str, info: str = ""):
        """Send notification and update profile badge.

        Args:
            agent_name: Agent name
            status: Status (running, idle, error, blocked, success)
            info: Additional info for badge
        """
        # Update profile if manager is available
        if self.profile_manager:
            await self.profile_manager.set_agent_status(agent_name, status, info)

        # Additional notification logic (logging, alerts, etc.)
        agent = self.registry.get_agent(agent_name)
        if agent:
            # Log, send to slack, etc.
            pass
```

---

## 4. Server Integration (MCP Tools)

Add MCP tools for profile management:

```python
# In iterm_mcpy/fastmcp_server.py - add profile tools

from fastmcp import Tool

@server.call_tool()
async def set_agent_status(agent_name: str, status: str, info: str = "") -> str:
    """Update agent status badge and tab color.

    Args:
        agent_name: Agent name
        status: Status (running, idle, error, blocked, success)
        info: Optional status info

    Returns:
        Status message
    """
    if not profile_manager:
        return "Profile manager not initialized"

    try:
        await profile_manager.set_agent_status(agent_name, status, info)
        return f"Updated {agent_name} status to {status}"
    except Exception as e:
        return f"Error: {e}"


@server.call_tool()
async def reset_agent_color(agent_name: str) -> str:
    """Reset agent tab color to team color.

    Args:
        agent_name: Agent name

    Returns:
        Status message
    """
    if not profile_manager:
        return "Profile manager not initialized"

    try:
        await profile_manager.reset_agent_to_team_color(agent_name)
        return f"Reset {agent_name} to team color"
    except Exception as e:
        return f"Error: {e}"


@server.call_tool()
async def list_team_colors() -> str:
    """List configured team colors.

    Returns:
        JSON string with team color mappings
    """
    import json
    colors = {}
    for team_name, color in TEAM_COLORS.items():
        colors[team_name] = {
            "hue": color.hue,
            "saturation": color.saturation,
            "lightness": color.lightness
        }
    return json.dumps(colors, indent=2)
```

---

## 5. Usage Examples

### Example 1: Create Team and Register Agent

```python
async def setup_agent_with_profile(app: iterm2.Application,
                                   registry: AgentRegistry,
                                   profile_manager: ProfileManager,
                                   agent_name: str,
                                   session_id: str,
                                   team_name: str):
    """Create team and register agent with profile."""

    # Create team if needed
    team = registry.get_team(team_name)
    if not team:
        team = registry.create_team(team_name)

    # Get or create team profile
    profile = await profile_manager.get_or_create_team_profile(team)

    # Register agent with profile
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

### Example 2: Update Status During Task

```python
async def run_agent_task(agent_name: str,
                         profile_manager: ProfileManager,
                         task_func):
    """Run task with status updates."""

    try:
        # Task starting
        await profile_manager.set_agent_status(agent_name, "running", "initializing")

        # Run task
        result = await task_func()

        # Task succeeded
        await profile_manager.set_agent_status(agent_name, "success")
        await asyncio.sleep(2)  # Show success briefly
        await profile_manager.reset_agent_to_team_color(agent_name)

        return result

    except Exception as e:
        # Task failed
        await profile_manager.set_agent_status(agent_name, "error", str(e)[:20])
        raise
```

### Example 3: Monitor Multiple Agents

```python
async def monitor_agent_statuses(registry: AgentRegistry,
                                 profile_manager: ProfileManager,
                                 session_statuses: Dict[str, str]):
    """Update all agents' profiles based on session status.

    Args:
        registry: Agent registry
        profile_manager: Profile manager
        session_statuses: Dict of session_id -> status
    """
    agents = registry.list_agents()

    for agent in agents:
        status = session_statuses.get(agent.session_id, "unknown")
        await profile_manager.set_agent_status(agent.name, status)
```

---

## 6. Configuration

Add profiles configuration to your settings:

```yaml
# config/profiles.yaml

teams:
  backend:
    color:
      hue: 0
      saturation: 100
      lightness: 40
  frontend:
    color:
      hue: 120
      saturation: 100
      lightness: 40
  devops:
    color:
      hue: 220
      saturation: 100
      lightness: 40

status_colors:
  running:
    hue: 60
    saturation: 100
    lightness: 40
  idle:
    hue: 0
    saturation: 0
    lightness: 50
  error:
    hue: 0
    saturation: 100
    lightness: 40
```

---

## 7. Testing Profile Features

```python
# tests/test_profile_manager.py

import pytest
import iterm2
from core.profile_manager import ProfileManager
from core.agents import AgentRegistry, Team

@pytest.mark.asyncio
async def test_create_team_profile():
    """Test creating a profile for a team."""
    async with iterm2.Application() as app:
        registry = AgentRegistry()
        manager = ProfileManager(app, registry)

        team = registry.create_team("test-team", "Test team")
        profile = await manager.get_or_create_team_profile(team)

        assert profile is not None
        assert "test-team" in profile.name_.lower()
        assert profile.use_tab_color is True


@pytest.mark.asyncio
async def test_set_agent_status():
    """Test updating agent status badge."""
    async with iterm2.Application() as app:
        registry = AgentRegistry()
        manager = ProfileManager(app, registry)

        # Setup
        team = registry.create_team("test")
        profile = await manager.get_or_create_team_profile(team)

        agent = registry.register_agent(
            name="test-agent",
            session_id="session-123",
            teams=["test"],
            metadata={"profile_guid": profile.guid}
        )

        # Update status
        await manager.set_agent_status("test-agent", "running", "compiling")

        # Verify
        profile = await manager.get_profile_by_guid(profile.guid)
        assert "running" in profile.badge_text_.lower()
```

---

## 8. Troubleshooting

### Profile Not Found
```python
# Check if profile GUID is valid
profile = await manager.get_profile_by_guid(guid)
if not profile:
    # Profile deleted or invalid GUID
    # Regenerate profile or clear metadata
    agent.metadata.pop("profile_guid", None)
```

### Color Changes Not Showing
```python
# Ensure use_tab_color is enabled
if profile.use_tab_color is False:
    await profile.async_set_use_tab_color(True)

# Refresh the session
await apply_profile_to_session(session, profile)
```

### Badge Text Truncated
```python
# Keep badge text short (<30 chars)
if len(badge_text) > 30:
    badge_text = badge_text[:27] + "..."
```

---

## Migration Checklist

- [ ] Create ProfileManager in core/profile_manager.py
- [ ] Add profile_guid to AgentRegistry.metadata
- [ ] Integrate ProfileManager with NotificationManager
- [ ] Add MCP tools for profile management
- [ ] Configure team colors in config/profiles.yaml
- [ ] Add tests in tests/test_profile_manager.py
- [ ] Update documentation with team color scheme
- [ ] Deploy and test with real agents

---

## Related Files

- `/Users/preston/MCP/iterm-mcp/docs/PROFILES.md` - Full Profile API reference
- `/Users/preston/MCP/iterm-mcp/core/agents.py` - AgentRegistry implementation
- `/Users/preston/MCP/iterm-mcp/core/feedback.py` - Notification/Feedback system
- `/Users/preston/MCP/iterm-mcp/iterm_mcpy/fastmcp_server.py` - MCP tools
