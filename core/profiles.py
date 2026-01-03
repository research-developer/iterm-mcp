"""Profile management for iTerm MCP with team-based color distribution.

This module manages Dynamic Profiles for iTerm2, providing:
- Base MCP Agent profile with automation-friendly shell settings
- Team-specific profiles with evenly-distributed colors
- Maximum-gap color distribution algorithm for optimal visual distinction
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import uuid

# Constants
DYNAMIC_PROFILES_DIR = Path.home() / "Library/Application Support/iTerm2/DynamicProfiles"
MCP_PROFILES_FILE = DYNAMIC_PROFILES_DIR / "iterm-mcp-profiles.json"

# Base profile identifiers (stable)
MCP_AGENT_PROFILE_NAME = "MCP Agent"
MCP_AGENT_PROFILE_GUID = "2A486A23-AC84-401F-A1B6-02239228FA94"

# Backwards compatibility alias
MCP_AGENT_BASE_GUID = MCP_AGENT_PROFILE_GUID

# Color constraints for team profiles
MIN_SATURATION = 50  # Minimum saturation (0-100)
MAX_SATURATION = 85  # Maximum saturation (0-100)
MIN_LIGHTNESS = 25   # Minimum lightness - not too dark
MAX_LIGHTNESS = 45   # Maximum lightness - not too light (readable on dark bg)


@dataclass
class HSLColor:
    """HSL color representation for profile colors."""
    hue: float        # 0-360 degrees
    saturation: float  # 0-100 percent
    lightness: float   # 0-100 percent

    def to_rgb(self) -> Tuple[float, float, float]:
        """Convert HSL to RGB (0-1 range for iTerm2).

        Returns:
            Tuple of (red, green, blue) in 0-1 range
        """
        h = self.hue / 360
        s = self.saturation / 100
        l = self.lightness / 100

        if s == 0:
            return (l, l, l)

        def hue_to_rgb(p: float, q: float, t: float) -> float:
            if t < 0:
                t += 1
            if t > 1:
                t -= 1
            if t < 1/6:
                return p + (q - p) * 6 * t
            if t < 1/2:
                return q
            if t < 2/3:
                return p + (q - p) * (2/3 - t) * 6
            return p

        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q

        r = hue_to_rgb(p, q, h + 1/3)
        g = hue_to_rgb(p, q, h)
        b = hue_to_rgb(p, q, h - 1/3)

        return (r, g, b)

    def to_iterm_dict(self) -> Dict:
        """Convert to iTerm2 Dynamic Profile color format."""
        r, g, b = self.to_rgb()
        return {
            "Red Component": r,
            "Green Component": g,
            "Blue Component": b,
            "Color Space": "sRGB"
        }


# Alias for backwards compatibility with expected export name
TeamProfileColor = HSLColor


@dataclass
class TeamProfile:
    """Represents a team's iTerm profile."""
    team_name: str
    guid: str
    color: HSLColor
    parent_guid: str = MCP_AGENT_BASE_GUID

    def to_dynamic_profile(self) -> Dict:
        """Convert to iTerm2 Dynamic Profile format."""
        return {
            "Name": f"MCP Team: {self.team_name}",
            "Guid": self.guid,
            "Dynamic Profile Parent GUID": self.parent_guid,
            "Custom Tab Color": True,
            "Tab Color": self.color.to_iterm_dict(),
            "Badge Text": f"🤖 {self.team_name}",
            "Tags": ["mcp", "agent", "team", self.team_name]
        }


class ColorDistributor:
    """Maximum-gap color distribution for optimal visual distinction.

    Uses the "biggest gap" algorithm to place new colors maximally
    distant from existing colors on the hue wheel.
    """

    def __init__(self, saturation: float = 70, lightness: float = 38):
        """Initialize with color constraints.

        Args:
            saturation: Default saturation (50-85 recommended)
            lightness: Default lightness (25-45 recommended)
        """
        self.saturation = max(MIN_SATURATION, min(MAX_SATURATION, saturation))
        self.lightness = max(MIN_LIGHTNESS, min(MAX_LIGHTNESS, lightness))
        self._used_hues: List[float] = []

    def get_next_color(self) -> HSLColor:
        """Get the next color using maximum-gap distribution.

        Places new hues in the largest gap between existing hues
        on the color wheel (0-360 degrees).

        Returns:
            HSLColor with maximally-distant hue
        """
        if not self._used_hues:
            # First color: start at a pleasant hue (teal-ish)
            hue = 180.0
        else:
            hue = self._find_largest_gap()

        self._used_hues.append(hue)
        return HSLColor(hue, self.saturation, self.lightness)

    def _find_largest_gap(self) -> float:
        """Find the midpoint of the largest gap between used hues.

        Treats the hue wheel as circular (360 wraps to 0).

        Returns:
            Hue value (0-360) at the center of the largest gap
        """
        if not self._used_hues:
            return 180.0

        # Sort hues for gap analysis
        sorted_hues = sorted(self._used_hues)

        # Find gaps between consecutive hues
        gaps: List[Tuple[float, float, float]] = []  # (gap_size, start, end)

        for i in range(len(sorted_hues)):
            start = sorted_hues[i]
            end = sorted_hues[(i + 1) % len(sorted_hues)]

            # Handle wrap-around (e.g., 350 -> 10 is a 20-degree gap)
            if end <= start:
                gap = (360 - start) + end
            else:
                gap = end - start

            gaps.append((gap, start, end))

        # Find largest gap
        largest = max(gaps, key=lambda x: x[0])
        gap_size, start, end = largest

        # Return midpoint of largest gap
        if end <= start:
            # Wrap-around case
            midpoint = (start + gap_size / 2) % 360
        else:
            midpoint = start + gap_size / 2

        return midpoint

    def add_existing_hue(self, hue: float) -> None:
        """Register an existing hue to avoid collision.

        Args:
            hue: Hue value (0-360)
        """
        normalized = hue % 360
        if normalized not in self._used_hues:
            self._used_hues.append(normalized)

    def reset(self) -> None:
        """Clear all used hues."""
        self._used_hues.clear()

    @property
    def used_hues(self) -> List[float]:
        """Get list of used hues."""
        return self._used_hues.copy()


class ProfileManager:
    """Manages iTerm Dynamic Profiles for MCP agents and teams.

    Provides:
    - Team profile creation with auto-assigned colors
    - Profile persistence via Dynamic Profiles JSON
    - Integration with AgentRegistry for team-profile mapping
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize the ProfileManager.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger("iterm-mcp.profiles")
        self.color_distributor = ColorDistributor()
        self._team_profiles: Dict[str, TeamProfile] = {}
        self._profiles_dirty = False

        # Ensure Dynamic Profiles directory exists
        DYNAMIC_PROFILES_DIR.mkdir(parents=True, exist_ok=True)

        # Load existing profiles
        self._load_profiles()

    def _load_profiles(self) -> None:
        """Load existing profiles from the Dynamic Profiles file."""
        if not MCP_PROFILES_FILE.exists():
            self.logger.info("No existing profiles file, will create on first save")
            return

        try:
            with open(MCP_PROFILES_FILE, 'r') as f:
                data = json.load(f)

            for profile in data.get("Profiles", []):
                # Skip the base MCP Agent profile
                if profile.get("Guid") == MCP_AGENT_BASE_GUID:
                    continue

                # Extract team name from profile name
                name = profile.get("Name", "")
                if name.startswith("MCP Team: "):
                    team_name = name[len("MCP Team: "):]

                    # Extract color from tab color
                    tab_color = profile.get("Tab Color", {})
                    r = tab_color.get("Red Component", 0.5)
                    g = tab_color.get("Green Component", 0.5)
                    b = tab_color.get("Blue Component", 0.5)

                    # Convert RGB to HSL (approximate)
                    hue = self._rgb_to_hue(r, g, b)

                    team_profile = TeamProfile(
                        team_name=team_name,
                        guid=profile.get("Guid", str(uuid.uuid4())),
                        color=HSLColor(hue, self.color_distributor.saturation,
                                      self.color_distributor.lightness)
                    )

                    self._team_profiles[team_name] = team_profile
                    self.color_distributor.add_existing_hue(hue)

                    self.logger.debug(f"Loaded team profile: {team_name} (hue={hue:.1f})")

            self.logger.info(f"Loaded {len(self._team_profiles)} team profiles")

        except Exception as e:
            self.logger.error(f"Error loading profiles: {e}")

    def _rgb_to_hue(self, r: float, g: float, b: float) -> float:
        """Convert RGB (0-1) to hue (0-360).

        Simplified conversion for extracting existing hues.
        """
        max_c = max(r, g, b)
        min_c = min(r, g, b)
        delta = max_c - min_c

        if delta == 0:
            return 0.0

        if max_c == r:
            hue = 60 * (((g - b) / delta) % 6)
        elif max_c == g:
            hue = 60 * (((b - r) / delta) + 2)
        else:
            hue = 60 * (((r - g) / delta) + 4)

        return hue % 360

    def get_or_create_team_profile(self, team_name: str) -> TeamProfile:
        """Get or create a profile for a team.

        Args:
            team_name: Name of the team

        Returns:
            TeamProfile for the team

        Raises:
            ValueError: If team_name is empty or None
        """
        if not team_name or not team_name.strip():
            raise ValueError("team_name cannot be empty or None")

        team_name = team_name.strip()

        if team_name in self._team_profiles:
            return self._team_profiles[team_name]

        # Create new team profile with next available color
        color = self.color_distributor.get_next_color()
        guid = str(uuid.uuid4()).upper()

        profile = TeamProfile(
            team_name=team_name,
            guid=guid,
            color=color
        )

        self._team_profiles[team_name] = profile
        self._profiles_dirty = True

        self.logger.info(f"Created team profile: {team_name} (hue={color.hue:.1f})")

        return profile

    def get_team_profile(self, team_name: str) -> Optional[TeamProfile]:
        """Get a team's profile if it exists.

        Args:
            team_name: Name of the team

        Returns:
            TeamProfile or None
        """
        return self._team_profiles.get(team_name)

    def remove_team_profile(self, team_name: str) -> bool:
        """Remove a team's profile.

        Args:
            team_name: Name of the team

        Returns:
            True if removed, False if not found
        """
        if team_name in self._team_profiles:
            profile = self._team_profiles.pop(team_name)
            # Note: We don't remove from color_distributor to maintain gap distribution
            self._profiles_dirty = True
            self.logger.info(f"Removed team profile: {team_name}")
            return True
        return False

    def save_profiles(self) -> None:
        """Save all profiles to the Dynamic Profiles file."""
        if not self._profiles_dirty and MCP_PROFILES_FILE.exists():
            return

        # Build the complete profiles list
        profiles = []

        # Add base MCP Agent profile
        profiles.append({
            "Name": "MCP Agent",
            "Guid": MCP_AGENT_BASE_GUID,
            "Dynamic Profile Parent Name": "Default",
            "Initial Text": "unsetopt correct correctall 2>/dev/null; setopt NO_CORRECT NO_CORRECT_ALL 2>/dev/null",
            "Badge Text": "🤖",
            "Custom Tab Color": True,
            "Tab Color": {
                "Red Component": 0.2,
                "Green Component": 0.25,
                "Blue Component": 0.3,
                "Color Space": "sRGB"
            },
            "Tags": ["mcp", "agent"]
        })

        # Add team profiles
        for team_profile in self._team_profiles.values():
            profiles.append(team_profile.to_dynamic_profile())

        # Write to file
        data = {"Profiles": profiles}

        try:
            with open(MCP_PROFILES_FILE, 'w') as f:
                json.dump(data, f, indent=2)

            self._profiles_dirty = False
            self.logger.info(f"Saved {len(profiles)} profiles to {MCP_PROFILES_FILE}")

        except Exception as e:
            self.logger.error(f"Error saving profiles: {e}")
            raise

    def list_team_profiles(self) -> List[TeamProfile]:
        """List all team profiles.

        Returns:
            List of TeamProfile objects
        """
        return list(self._team_profiles.values())

    def get_base_profile_guid(self) -> str:
        """Get the GUID of the base MCP Agent profile.

        Returns:
            GUID string for the base profile
        """
        return MCP_AGENT_BASE_GUID

    def get_profile_guid_for_agent(self, team_name: Optional[str] = None) -> str:
        """Get the appropriate profile GUID for an agent.

        Args:
            team_name: Optional team name; if None, returns base profile

        Returns:
            Profile GUID
        """
        if team_name:
            profile = self.get_or_create_team_profile(team_name)
            return profile.guid
        return MCP_AGENT_BASE_GUID


# Module-level instance for easy access
_profile_manager: Optional[ProfileManager] = None


def get_profile_manager(logger: Optional[logging.Logger] = None) -> ProfileManager:
    """Get or create the global ProfileManager instance.

    Args:
        logger: Optional logger instance

    Returns:
        ProfileManager instance
    """
    global _profile_manager
    if _profile_manager is None:
        _profile_manager = ProfileManager(logger)
    return _profile_manager
