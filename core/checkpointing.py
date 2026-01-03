"""State persistence and checkpointing for sessions and agents.

This module provides checkpointing capabilities for crash recovery, session resumption,
and state replay for debugging. Inspired by patterns from LangGraph, AutoGen, and
Agency Swarm frameworks.

Key features:
- Automatic checkpoint creation on major operations
- FileCheckpointer for local development
- SQLiteCheckpointer for production use
- Session and agent state serialization
"""

import json
import os
import sqlite3
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Union, runtime_checkable

from pydantic import BaseModel, Field


class SessionState(BaseModel):
    """Serializable state of an iTerm session."""

    session_id: str = Field(..., description="The iTerm session ID")
    persistent_id: str = Field(..., description="Persistent ID for reconnection")
    name: str = Field(..., description="Session name")
    max_lines: int = Field(default=50, description="Max lines to retrieve")
    is_monitoring: bool = Field(default=False, description="Whether monitoring is active")
    last_screen_update: float = Field(default=0.0, description="Timestamp of last screen update")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Optional context data
    last_command: Optional[str] = Field(default=None, description="Last command executed")
    last_output: Optional[str] = Field(default=None, description="Last captured output")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional session metadata")


class AgentState(BaseModel):
    """Serializable state of an agent."""

    name: str = Field(..., description="Agent name")
    session_id: str = Field(..., description="Associated session ID")
    teams: List[str] = Field(default_factory=list, description="Team memberships")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, str] = Field(default_factory=dict, description="Agent metadata")


class TeamState(BaseModel):
    """Serializable state of a team."""

    name: str = Field(..., description="Team name")
    description: str = Field(default="", description="Team description")
    parent_team: Optional[str] = Field(default=None, description="Parent team name")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RegistryState(BaseModel):
    """Serializable state of the agent registry."""

    agents: Dict[str, AgentState] = Field(default_factory=dict)
    teams: Dict[str, TeamState] = Field(default_factory=dict)
    active_session: Optional[str] = Field(default=None)
    message_history: List[Dict[str, Any]] = Field(default_factory=list)


class Checkpoint(BaseModel):
    """A complete checkpoint containing session and registry state."""

    checkpoint_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = Field(default="1.0", description="Checkpoint format version")

    # Session states
    sessions: Dict[str, SessionState] = Field(default_factory=dict)

    # Registry state (agents, teams, messages)
    registry: Optional[RegistryState] = Field(default=None)

    # Metadata about what triggered this checkpoint
    trigger: str = Field(default="manual", description="What triggered this checkpoint")
    metadata: Dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class Checkpointer(Protocol):
    """Protocol for checkpoint storage backends.

    Checkpointers handle saving and loading checkpoint data.
    Implementations include file-based and SQLite-based storage.
    """

    async def save(self, checkpoint: Checkpoint) -> str:
        """Save a checkpoint.

        Args:
            checkpoint: The checkpoint to save

        Returns:
            The checkpoint ID
        """
        ...

    async def load(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Load a checkpoint by ID.

        Args:
            checkpoint_id: The checkpoint ID to load

        Returns:
            The checkpoint if found, None otherwise
        """
        ...

    async def list_checkpoints(
        self,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """List available checkpoints.

        Args:
            session_id: Optional filter by session ID
            limit: Maximum number of checkpoints to return

        Returns:
            List of checkpoint metadata dicts with id, created_at, trigger
        """
        ...

    async def delete(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint.

        Args:
            checkpoint_id: The checkpoint ID to delete

        Returns:
            True if deleted, False if not found
        """
        ...

    async def get_latest(self, session_id: Optional[str] = None) -> Optional[Checkpoint]:
        """Get the most recent checkpoint.

        Args:
            session_id: Optional filter by session ID

        Returns:
            The latest checkpoint if any exist
        """
        ...


class FileCheckpointer:
    """File-based checkpointer for local development.

    Stores checkpoints as JSON files in a directory structure.
    Good for development and debugging, not recommended for production.
    """

    def __init__(self, checkpoint_dir: Optional[str] = None):
        """Initialize the file checkpointer.

        Args:
            checkpoint_dir: Directory to store checkpoints.
                           Defaults to ~/.iterm-mcp/checkpoints/
        """
        if checkpoint_dir is None:
            checkpoint_dir = os.path.expanduser("~/.iterm-mcp/checkpoints")

        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Index file for quick lookups
        self.index_file = self.checkpoint_dir / "index.json"
        self._index: Dict[str, Dict[str, Any]] = {}
        self._load_index()

    def _load_index(self) -> None:
        """Load the checkpoint index from disk."""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r') as f:
                    self._index = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._index = {}

    def _save_index(self) -> None:
        """Save the checkpoint index to disk."""
        with open(self.index_file, 'w') as f:
            json.dump(self._index, f, indent=2, default=str)

    def _get_checkpoint_path(self, checkpoint_id: str) -> Path:
        """Get the file path for a checkpoint."""
        return self.checkpoint_dir / f"{checkpoint_id}.json"

    async def save(self, checkpoint: Checkpoint) -> str:
        """Save a checkpoint to disk.

        Args:
            checkpoint: The checkpoint to save

        Returns:
            The checkpoint ID
        """
        checkpoint_path = self._get_checkpoint_path(checkpoint.checkpoint_id)

        # Serialize checkpoint to JSON
        checkpoint_data = checkpoint.model_dump(mode='json')

        with open(checkpoint_path, 'w') as f:
            json.dump(checkpoint_data, f, indent=2, default=str)

        # Update index
        session_ids = list(checkpoint.sessions.keys())
        self._index[checkpoint.checkpoint_id] = {
            "created_at": checkpoint.created_at.isoformat(),
            "trigger": checkpoint.trigger,
            "session_ids": session_ids,
            "has_registry": checkpoint.registry is not None
        }
        self._save_index()

        return checkpoint.checkpoint_id

    async def load(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Load a checkpoint from disk.

        Args:
            checkpoint_id: The checkpoint ID to load

        Returns:
            The checkpoint if found, None otherwise
        """
        checkpoint_path = self._get_checkpoint_path(checkpoint_id)

        if not checkpoint_path.exists():
            return None

        try:
            with open(checkpoint_path, 'r') as f:
                data = json.load(f)
            return Checkpoint.model_validate(data)
        except (json.JSONDecodeError, IOError, Exception):
            return None

    async def list_checkpoints(
        self,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """List available checkpoints.

        Args:
            session_id: Optional filter by session ID
            limit: Maximum number of checkpoints to return

        Returns:
            List of checkpoint metadata dicts
        """
        results = []

        for cp_id, meta in self._index.items():
            # Filter by session if specified
            if session_id and session_id not in meta.get("session_ids", []):
                continue

            results.append({
                "checkpoint_id": cp_id,
                "created_at": meta.get("created_at"),
                "trigger": meta.get("trigger"),
                "session_ids": meta.get("session_ids", []),
                "has_registry": meta.get("has_registry", False)
            })

        # Sort by created_at descending
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        return results[:limit]

    async def delete(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint from disk.

        Args:
            checkpoint_id: The checkpoint ID to delete

        Returns:
            True if deleted, False if not found
        """
        checkpoint_path = self._get_checkpoint_path(checkpoint_id)

        if not checkpoint_path.exists():
            return False

        try:
            checkpoint_path.unlink()
            if checkpoint_id in self._index:
                del self._index[checkpoint_id]
                self._save_index()
            return True
        except IOError:
            return False

    async def get_latest(self, session_id: Optional[str] = None) -> Optional[Checkpoint]:
        """Get the most recent checkpoint.

        Args:
            session_id: Optional filter by session ID

        Returns:
            The latest checkpoint if any exist
        """
        checkpoints = await self.list_checkpoints(session_id=session_id, limit=1)

        if not checkpoints:
            return None

        return await self.load(checkpoints[0]["checkpoint_id"])


class SQLiteCheckpointer:
    """SQLite-based checkpointer for production use.

    Provides efficient storage and querying of checkpoints using SQLite.
    Suitable for production deployments with many checkpoints.
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the SQLite checkpointer.

        Args:
            db_path: Path to SQLite database file.
                    Defaults to ~/.iterm-mcp/checkpoints.db
        """
        if db_path is None:
            db_dir = os.path.expanduser("~/.iterm-mcp")
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, "checkpoints.db")

        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    version TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    data TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoint_sessions (
                    checkpoint_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    PRIMARY KEY (checkpoint_id, session_id),
                    FOREIGN KEY (checkpoint_id) REFERENCES checkpoints(checkpoint_id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_checkpoints_created_at
                ON checkpoints(created_at DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_checkpoint_sessions_session_id
                ON checkpoint_sessions(session_id)
            """)
            conn.commit()

    async def save(self, checkpoint: Checkpoint) -> str:
        """Save a checkpoint to SQLite.

        Args:
            checkpoint: The checkpoint to save

        Returns:
            The checkpoint ID
        """
        checkpoint_data = checkpoint.model_dump_json()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO checkpoints
                (checkpoint_id, created_at, version, trigger, data)
                VALUES (?, ?, ?, ?, ?)
            """, (
                checkpoint.checkpoint_id,
                checkpoint.created_at.isoformat(),
                checkpoint.version,
                checkpoint.trigger,
                checkpoint_data
            ))

            # Store session associations for efficient querying
            conn.execute(
                "DELETE FROM checkpoint_sessions WHERE checkpoint_id = ?",
                (checkpoint.checkpoint_id,)
            )
            for session_id in checkpoint.sessions.keys():
                conn.execute("""
                    INSERT INTO checkpoint_sessions (checkpoint_id, session_id)
                    VALUES (?, ?)
                """, (checkpoint.checkpoint_id, session_id))

            conn.commit()

        return checkpoint.checkpoint_id

    async def load(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Load a checkpoint from SQLite.

        Args:
            checkpoint_id: The checkpoint ID to load

        Returns:
            The checkpoint if found, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT data FROM checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,)
            )
            row = cursor.fetchone()

            if row is None:
                return None

            try:
                data = json.loads(row[0])
                return Checkpoint.model_validate(data)
            except (json.JSONDecodeError, Exception):
                return None

    async def list_checkpoints(
        self,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """List available checkpoints.

        Args:
            session_id: Optional filter by session ID
            limit: Maximum number of checkpoints to return

        Returns:
            List of checkpoint metadata dicts
        """
        with sqlite3.connect(self.db_path) as conn:
            if session_id:
                cursor = conn.execute("""
                    SELECT c.checkpoint_id, c.created_at, c.trigger
                    FROM checkpoints c
                    INNER JOIN checkpoint_sessions cs ON c.checkpoint_id = cs.checkpoint_id
                    WHERE cs.session_id = ?
                    ORDER BY c.created_at DESC
                    LIMIT ?
                """, (session_id, limit))
            else:
                cursor = conn.execute("""
                    SELECT checkpoint_id, created_at, trigger
                    FROM checkpoints
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))

            results = []
            for row in cursor.fetchall():
                # Get session IDs for this checkpoint
                sessions_cursor = conn.execute(
                    "SELECT session_id FROM checkpoint_sessions WHERE checkpoint_id = ?",
                    (row[0],)
                )
                session_ids = [s[0] for s in sessions_cursor.fetchall()]

                results.append({
                    "checkpoint_id": row[0],
                    "created_at": row[1],
                    "trigger": row[2],
                    "session_ids": session_ids
                })

            return results

    async def delete(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint from SQLite.

        Args:
            checkpoint_id: The checkpoint ID to delete

        Returns:
            True if deleted, False if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    async def get_latest(self, session_id: Optional[str] = None) -> Optional[Checkpoint]:
        """Get the most recent checkpoint.

        Args:
            session_id: Optional filter by session ID

        Returns:
            The latest checkpoint if any exist
        """
        checkpoints = await self.list_checkpoints(session_id=session_id, limit=1)

        if not checkpoints:
            return None

        return await self.load(checkpoints[0]["checkpoint_id"])

    async def cleanup_old_checkpoints(
        self,
        max_age_days: int = 7,
        max_count: int = 100
    ) -> int:
        """Clean up old checkpoints to manage storage.

        Args:
            max_age_days: Delete checkpoints older than this
            max_count: Keep at most this many checkpoints

        Returns:
            Number of checkpoints deleted
        """
        from datetime import timedelta

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        deleted_count = 0

        with sqlite3.connect(self.db_path) as conn:
            # Delete by age
            cursor = conn.execute(
                "DELETE FROM checkpoints WHERE created_at < ?",
                (cutoff_date.isoformat(),)
            )
            deleted_count += cursor.rowcount

            # Delete oldest if over count limit
            cursor = conn.execute("""
                DELETE FROM checkpoints WHERE checkpoint_id IN (
                    SELECT checkpoint_id FROM checkpoints
                    ORDER BY created_at DESC
                    LIMIT -1 OFFSET ?
                )
            """, (max_count,))
            deleted_count += cursor.rowcount

            conn.commit()

        return deleted_count


class CheckpointManager:
    """High-level manager for checkpointing operations.

    Provides a unified interface for creating, loading, and managing
    checkpoints across sessions and agents.
    """

    def __init__(
        self,
        checkpointer: Optional[Union[FileCheckpointer, SQLiteCheckpointer]] = None,
        auto_checkpoint: bool = True,
        checkpoint_interval: int = 5
    ):
        """Initialize the checkpoint manager.

        Args:
            checkpointer: Storage backend. Defaults to FileCheckpointer.
            auto_checkpoint: Whether to auto-checkpoint on major operations.
            checkpoint_interval: Operations between auto-checkpoints.
        """
        self.checkpointer = checkpointer or FileCheckpointer()
        self.auto_checkpoint = auto_checkpoint
        self.checkpoint_interval = checkpoint_interval
        self._operation_count = 0
        self._last_checkpoint_id: Optional[str] = None

    async def create_checkpoint(
        self,
        sessions: Optional[Dict[str, "SessionState"]] = None,
        registry: Optional["RegistryState"] = None,
        trigger: str = "manual",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Checkpoint:
        """Create and save a new checkpoint.

        Args:
            sessions: Session states to include
            registry: Registry state to include
            trigger: What triggered this checkpoint
            metadata: Additional metadata

        Returns:
            The created checkpoint
        """
        checkpoint = Checkpoint(
            sessions=sessions or {},
            registry=registry,
            trigger=trigger,
            metadata=metadata or {}
        )

        await self.checkpointer.save(checkpoint)
        self._last_checkpoint_id = checkpoint.checkpoint_id
        self._operation_count = 0

        return checkpoint

    async def restore_checkpoint(
        self,
        checkpoint_id: Optional[str] = None
    ) -> Optional[Checkpoint]:
        """Restore from a checkpoint.

        Args:
            checkpoint_id: Specific checkpoint to restore.
                          If None, restores from latest.

        Returns:
            The restored checkpoint, or None if not found
        """
        if checkpoint_id:
            return await self.checkpointer.load(checkpoint_id)
        return await self.checkpointer.get_latest()

    async def should_auto_checkpoint(self) -> bool:
        """Check if an auto-checkpoint should be created.

        Returns:
            True if auto-checkpoint threshold reached
        """
        if not self.auto_checkpoint:
            return False

        self._operation_count += 1
        return self._operation_count >= self.checkpoint_interval

    async def list_checkpoints(
        self,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """List available checkpoints.

        Args:
            session_id: Optional filter by session
            limit: Maximum results

        Returns:
            List of checkpoint metadata
        """
        return await self.checkpointer.list_checkpoints(
            session_id=session_id,
            limit=limit
        )

    async def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint.

        Args:
            checkpoint_id: Checkpoint to delete

        Returns:
            True if deleted
        """
        return await self.checkpointer.delete(checkpoint_id)

    @property
    def last_checkpoint_id(self) -> Optional[str]:
        """Get the ID of the last created checkpoint."""
        return self._last_checkpoint_id
