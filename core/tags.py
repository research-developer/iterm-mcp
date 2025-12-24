"""Session tagging and locking utilities."""

import time
from typing import Dict, List, Optional, Set, Tuple, Union


# Default cooldown period in seconds
DEFAULT_FOCUS_COOLDOWN_SECONDS = 5.0


class FocusCooldownManager:
    """Manages focus cooldown to prevent rapid session switching.

    When an agent focuses a session, other focus requests are blocked
    for a cooldown period. This prevents race conditions and UI thrashing.
    """

    def __init__(self, cooldown_seconds: float = DEFAULT_FOCUS_COOLDOWN_SECONDS) -> None:
        self._cooldown_seconds = cooldown_seconds
        self._last_focus_time: Optional[float] = None
        self._last_focus_session: Optional[str] = None
        self._last_focus_agent: Optional[str] = None

    @property
    def cooldown_seconds(self) -> float:
        """Get the cooldown period in seconds."""
        return self._cooldown_seconds

    @cooldown_seconds.setter
    def cooldown_seconds(self, value: float) -> None:
        """Set the cooldown period in seconds."""
        self._cooldown_seconds = max(0.0, value)

    def check_cooldown(self, session_id: str, agent: Optional[str] = None) -> Tuple[bool, Optional[str], float]:
        """Check if focus is allowed based on cooldown.

        Args:
            session_id: The session attempting to focus
            agent: The agent requesting focus (optional)

        Returns:
            Tuple of (allowed, blocking_agent, remaining_seconds)
            - allowed: True if focus is permitted
            - blocking_agent: The agent that triggered the cooldown (if blocked)
            - remaining_seconds: Seconds remaining in cooldown (0 if allowed)
        """
        if self._last_focus_time is None:
            return True, None, 0.0

        elapsed = time.monotonic() - self._last_focus_time
        remaining = self._cooldown_seconds - elapsed

        if remaining <= 0:
            return True, None, 0.0

        # Same session focusing again is allowed (idempotent)
        if session_id == self._last_focus_session:
            return True, None, 0.0

        # Same agent focusing different session is allowed
        if agent is not None and agent == self._last_focus_agent:
            return True, None, 0.0

        return False, self._last_focus_agent, remaining

    def record_focus(self, session_id: str, agent: Optional[str] = None) -> None:
        """Record a focus event to start the cooldown timer.

        Args:
            session_id: The session that was focused
            agent: The agent that triggered the focus (optional)
        """
        self._last_focus_time = time.monotonic()
        self._last_focus_session = session_id
        self._last_focus_agent = agent

    def reset(self) -> None:
        """Reset the cooldown state (for testing or admin override)."""
        self._last_focus_time = None
        self._last_focus_session = None
        self._last_focus_agent = None

    def get_status(self) -> Dict[str, Optional[Union[str, float]]]:
        """Get current cooldown status for debugging/visibility."""
        if self._last_focus_time is None:
            return {
                "in_cooldown": False,
                "last_session": None,
                "last_agent": None,
                "remaining_seconds": 0.0,
            }

        elapsed = time.monotonic() - self._last_focus_time
        remaining = max(0.0, self._cooldown_seconds - elapsed)

        return {
            "in_cooldown": remaining > 0,
            "last_session": self._last_focus_session,
            "last_agent": self._last_focus_agent,
            "remaining_seconds": round(remaining, 2),
        }


class SessionTagLockManager:
    """In-memory manager for session tags and locks."""

    def __init__(self) -> None:
        self._tags: Dict[str, Set[str]] = {}
        self._locks: Dict[str, str] = {}

    # ---------------------- Tag management ---------------------- #
    @staticmethod
    def _normalize_tags(tags: List[str]) -> Set[str]:
        """Normalize and deduplicate tags."""
        return {t.strip() for t in tags if t.strip()}

    def set_tags(self, session_id: str, tags: List[str], append: bool = True) -> List[str]:
        """Set or append tags for a session."""
        normalized = self._normalize_tags(tags)
        if not normalized and not append:
            # Replace-with-empty semantics: clear all tags when append is False
            self._tags.pop(session_id, None)
            return []

        if append:
            existing = self._tags.get(session_id, set())
            existing.update(normalized)
            self._tags[session_id] = existing
        else:
            self._tags[session_id] = normalized

        return sorted(self._tags.get(session_id, set()))

    def remove_tags(self, session_id: str, tags: List[str]) -> List[str]:
        """Remove specific tags from a session."""
        if session_id not in self._tags:
            return []

        remaining = self._tags[session_id] - self._normalize_tags(tags)
        if remaining:
            self._tags[session_id] = remaining
        else:
            self._tags.pop(session_id, None)

        return sorted(self._tags.get(session_id, set()))

    def get_tags(self, session_id: str) -> List[str]:
        """Get tags for a session."""
        return sorted(self._tags.get(session_id, set()))

    # ---------------------- Lock management --------------------- #
    def lock_session(self, session_id: str, agent: str) -> Tuple[bool, Optional[str]]:
        """Lock a session for an agent. Returns (acquired, current_owner)."""
        owner = self._locks.get(session_id)
        if owner is None or owner == agent:
            self._locks[session_id] = agent
            return True, agent
        return False, owner

    def unlock_session(self, session_id: str, agent: Optional[str] = None) -> bool:
        """Unlock a session if unlocked or owned by the provided agent."""
        owner = self._locks.get(session_id)
        if owner is None:
            return True
        if agent is None or agent == owner:
            self._locks.pop(session_id, None)
            return True
        return False

    def is_locked(self, session_id: str) -> bool:
        """Check if a session is locked."""
        return session_id in self._locks

    def lock_owner(self, session_id: str) -> Optional[str]:
        """Get lock owner for a session."""
        return self._locks.get(session_id)

    def release_locks_by_agent(self, agent: str) -> None:
        """Release all locks held by an agent (e.g., on termination)."""
        to_release = [sid for sid, owner in self._locks.items() if owner == agent]
        for sid in to_release:
            self._locks.pop(sid, None)

    def check_permission(self, session_id: str, requester: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Return (allowed, owner) for a write attempt."""
        owner = self._locks.get(session_id)
        if owner is None:
            return True, None
        if requester and requester == owner:
            return True, owner
        return False, owner

    # ---------------------- Combined info ----------------------- #
    def describe(self, session_id: str) -> Dict[str, Union[List[str], Optional[str]]]:
        """Return tags and lock owner for a session."""
        return {
            "tags": self.get_tags(session_id),
            "locked_by": self.lock_owner(session_id),
        }
