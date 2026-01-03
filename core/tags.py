"""Session tagging and locking utilities.

Note: SessionTagLockManager is NOT thread-safe. If concurrent access from
multiple threads is expected, external synchronization should be used.
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple, Union


# Default cooldown period in seconds
DEFAULT_FOCUS_COOLDOWN_SECONDS = 5.0


def _utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


@dataclass
class LockInfo:
    """Information about a session lock.

    Note: The pending_requests set is not thread-safe. Concurrent modifications
    from multiple threads may lead to race conditions.
    """

    owner: str
    locked_at: datetime = field(default_factory=_utc_now)
    pending_requests: Set[str] = field(default_factory=set)


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
        self._locks: Dict[str, LockInfo] = {}

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

    def has_tag(self, session_id: str, tag: str) -> bool:
        """Check if a session has a specific tag."""
        return tag.strip() in self._tags.get(session_id, set())

    def has_any_tags(self, session_id: str, tags: List[str]) -> bool:
        """Check if a session has any of the specified tags (OR match)."""
        session_tags = self._tags.get(session_id, set())
        check_tags = self._normalize_tags(tags)
        return bool(session_tags & check_tags)

    def has_all_tags(self, session_id: str, tags: List[str]) -> bool:
        """Check if a session has all of the specified tags (AND match)."""
        session_tags = self._tags.get(session_id, set())
        check_tags = self._normalize_tags(tags)
        return check_tags <= session_tags

    def sessions_with_tag(self, tag: str) -> List[str]:
        """Get all session IDs that have a specific tag."""
        tag = tag.strip()
        return [sid for sid, tags in self._tags.items() if tag in tags]

    def sessions_with_tags(
        self, tags: List[str], match_all: bool = False
    ) -> List[str]:
        """Get all session IDs that match the specified tags.

        Args:
            tags: List of tags to match
            match_all: If True, session must have ALL tags. If False, ANY tag matches.

        Returns:
            List of session IDs that match the criteria
        """
        if match_all:
            return [sid for sid in self._tags if self.has_all_tags(sid, tags)]
        else:
            return [sid for sid in self._tags if self.has_any_tags(sid, tags)]

    # ---------------------- Lock management --------------------- #
    def lock_session(self, session_id: str, agent: str) -> Tuple[bool, Optional[str]]:
        """Lock a session for an agent. Returns (acquired, current_owner)."""
        lock_info = self._locks.get(session_id)
        if lock_info is None:
            self._locks[session_id] = LockInfo(owner=agent)
            return True, agent
        if lock_info.owner == agent:
            return True, agent
        return False, lock_info.owner

    def unlock_session(self, session_id: str, agent: Optional[str] = None) -> bool:
        """Unlock a session if unlocked or owned by the provided agent."""
        lock_info = self._locks.get(session_id)
        if lock_info is None:
            return True
        if agent is None or agent == lock_info.owner:
            self._locks.pop(session_id, None)
            return True
        return False

    def is_locked(self, session_id: str) -> bool:
        """Check if a session is locked."""
        return session_id in self._locks

    def lock_owner(self, session_id: str) -> Optional[str]:
        """Get lock owner for a session."""
        lock_info = self._locks.get(session_id)
        return lock_info.owner if lock_info else None

    def get_lock_info(self, session_id: str) -> Optional[LockInfo]:
        """Get full lock info for a session."""
        return self._locks.get(session_id)

    def get_locked_at(self, session_id: str) -> Optional[datetime]:
        """Get the timestamp when a session was locked."""
        lock_info = self._locks.get(session_id)
        return lock_info.locked_at if lock_info else None

    def add_access_request(self, session_id: str, requester: str) -> bool:
        """Add a pending access request from an agent.

        Returns True if the request was added (session is locked by another agent).
        """
        lock_info = self._locks.get(session_id)
        if lock_info is None or lock_info.owner == requester:
            return False
        lock_info.pending_requests.add(requester)
        return True

    def remove_access_request(self, session_id: str, requester: str) -> bool:
        """Remove a pending access request."""
        lock_info = self._locks.get(session_id)
        if lock_info and requester in lock_info.pending_requests:
            lock_info.pending_requests.discard(requester)
            return True
        return False

    def get_pending_requests(self, session_id: str) -> List[str]:
        """Get list of agents waiting for access to a session."""
        lock_info = self._locks.get(session_id)
        return sorted(lock_info.pending_requests) if lock_info else []

    def get_pending_request_count(self, session_id: str) -> int:
        """Get count of pending access requests for a session."""
        lock_info = self._locks.get(session_id)
        return len(lock_info.pending_requests) if lock_info else 0

    def release_locks_by_agent(self, agent: str) -> List[str]:
        """Release all locks held by an agent (e.g., on termination).

        Returns list of session IDs that were unlocked.
        """
        to_release = [sid for sid, lock in self._locks.items() if lock.owner == agent]
        for sid in to_release:
            self._locks.pop(sid, None)
        return to_release

    def get_locks_by_agent(self, agent: str) -> List[str]:
        """Get all session IDs locked by a specific agent."""
        return [sid for sid, lock in self._locks.items() if lock.owner == agent]

    def get_all_locks(self) -> Dict[str, str]:
        """Get all locks as a dict of session_id -> owner."""
        return {sid: lock.owner for sid, lock in self._locks.items()}

    def check_permission(self, session_id: str, requester: Optional[str]) -> Tuple[bool, Optional[str]]:
        """Return (allowed, owner) for a write attempt."""
        lock_info = self._locks.get(session_id)
        if lock_info is None:
            return True, None
        if requester and requester == lock_info.owner:
            return True, lock_info.owner
        return False, lock_info.owner

    # ---------------------- Combined info ----------------------- #
    def describe(self, session_id: str) -> Dict[str, Union[List[str], Optional[str], bool, int]]:
        """Return full tags and lock info for a session."""
        lock_info = self._locks.get(session_id)
        return {
            "tags": self.get_tags(session_id),
            "locked": lock_info is not None,
            "locked_by": lock_info.owner if lock_info else None,
            "locked_at": lock_info.locked_at.isoformat() if lock_info else None,
            "pending_access_requests": len(lock_info.pending_requests) if lock_info else 0,
        }
