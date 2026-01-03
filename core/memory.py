"""Cross-agent memory store for context sharing and long-term learning.

This module provides a memory store interface and implementations that enable
agents to share context, learn from past interactions, and maintain long-term
knowledge across sessions.

Based on patterns from:
- LangGraph Store: Namespace-based organization
- CrewAI Memory: Short-term and long-term persistence
- AG2: Knowledge bases shared across agents
"""

import asyncio
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple, Union, runtime_checkable

from pydantic import BaseModel, Field


class Memory(BaseModel):
    """A single memory entry with metadata."""

    key: str = Field(..., description="Unique key within the namespace")
    value: Any = Field(..., description="The stored value (JSON-serializable)")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the memory was created/updated"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata (tags, source, etc.)"
    )
    namespace: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="The namespace this memory belongs to"
    )

    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True


class MemorySearchResult(BaseModel):
    """A search result with relevance score."""

    memory: Memory = Field(..., description="The matching memory")
    score: float = Field(default=1.0, description="Relevance score (0-1)")
    match_context: Optional[str] = Field(
        default=None,
        description="Context around the match (for full-text search)"
    )


@runtime_checkable
class MemoryStore(Protocol):
    """Protocol for memory store implementations.

    Memory stores provide namespace-based organization for cross-agent
    context sharing. Namespaces are tuples of strings that allow
    hierarchical organization (e.g., ("project-x", "agent", "memories")).
    """

    async def store(
        self,
        namespace: Tuple[str, ...],
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Store a value in the memory store.

        Args:
            namespace: Hierarchical namespace tuple
            key: Unique key within the namespace
            value: JSON-serializable value to store
            metadata: Optional metadata to associate with the memory
        """
        ...

    async def retrieve(
        self,
        namespace: Tuple[str, ...],
        key: str
    ) -> Optional[Memory]:
        """Retrieve a specific memory by key.

        Args:
            namespace: Hierarchical namespace tuple
            key: The key to retrieve

        Returns:
            The Memory if found, None otherwise
        """
        ...

    async def search(
        self,
        namespace: Tuple[str, ...],
        query: str,
        limit: int = 10
    ) -> List[MemorySearchResult]:
        """Search for memories matching a query.

        Args:
            namespace: Hierarchical namespace tuple (can be partial for broader search)
            query: Search query string
            limit: Maximum number of results to return

        Returns:
            List of MemorySearchResult sorted by relevance
        """
        ...

    async def list_keys(
        self,
        namespace: Tuple[str, ...]
    ) -> List[str]:
        """List all keys in a namespace.

        Args:
            namespace: Hierarchical namespace tuple

        Returns:
            List of keys in the namespace
        """
        ...

    async def delete(
        self,
        namespace: Tuple[str, ...],
        key: str
    ) -> bool:
        """Delete a memory by key.

        Args:
            namespace: Hierarchical namespace tuple
            key: The key to delete

        Returns:
            True if deleted, False if not found
        """
        ...

    async def list_namespaces(
        self,
        prefix: Optional[Tuple[str, ...]] = None
    ) -> List[Tuple[str, ...]]:
        """List all namespaces, optionally filtered by prefix.

        Args:
            prefix: Optional namespace prefix to filter by

        Returns:
            List of namespace tuples
        """
        ...


class FileMemoryStore:
    """JSON file-based memory store for development and simple use cases.

    Stores memories in a JSON file with namespace-based organization.
    Suitable for development and single-agent scenarios. Not recommended
    for production with high concurrency.
    """

    def __init__(self, file_path: Optional[str] = None):
        """Initialize the file-based memory store.

        Args:
            file_path: Path to the JSON file. Defaults to ~/.iterm-mcp/memories.json
        """
        if file_path is None:
            file_path = os.path.expanduser("~/.iterm-mcp/memories.json")

        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = asyncio.Lock()
        self._data: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._load()

    def _namespace_key(self, namespace: Tuple[str, ...]) -> str:
        """Convert namespace tuple to string key."""
        return "/".join(namespace) if namespace else "/"

    def _load(self) -> None:
        """Load memories from file."""
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r') as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._data = {}
        else:
            self._data = {}

    def _save(self) -> None:
        """Save memories to file."""
        with open(self.file_path, 'w') as f:
            json.dump(self._data, f, indent=2, default=str)

    async def store(
        self,
        namespace: Tuple[str, ...],
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Store a value in the memory store."""
        async with self._lock:
            ns_key = self._namespace_key(namespace)
            if ns_key not in self._data:
                self._data[ns_key] = {}

            self._data[ns_key][key] = {
                "key": key,
                "value": value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metadata": metadata or {},
                "namespace": list(namespace)
            }
            self._save()

    async def retrieve(
        self,
        namespace: Tuple[str, ...],
        key: str
    ) -> Optional[Memory]:
        """Retrieve a specific memory by key."""
        async with self._lock:
            ns_key = self._namespace_key(namespace)
            if ns_key in self._data and key in self._data[ns_key]:
                data = self._data[ns_key][key]
                return Memory(
                    key=data["key"],
                    value=data["value"],
                    timestamp=datetime.fromisoformat(data["timestamp"]),
                    metadata=data.get("metadata", {}),
                    namespace=tuple(data.get("namespace", []))
                )
            return None

    async def search(
        self,
        namespace: Tuple[str, ...],
        query: str,
        limit: int = 10
    ) -> List[MemorySearchResult]:
        """Search for memories matching a query (simple substring match)."""
        async with self._lock:
            results: List[MemorySearchResult] = []
            query_lower = query.lower()
            ns_prefix = self._namespace_key(namespace)

            for ns_key, memories in self._data.items():
                # Check if namespace matches prefix
                if not ns_key.startswith(ns_prefix):
                    continue

                for key, data in memories.items():
                    # Search in key, value (if string), and metadata
                    score = 0.0
                    match_context = None

                    # Check key
                    if query_lower in key.lower():
                        score = max(score, 0.8)
                        match_context = f"Key: {key}"

                    # Check value (convert to string for searching)
                    value_str = json.dumps(data["value"]) if not isinstance(data["value"], str) else data["value"]
                    if query_lower in value_str.lower():
                        score = max(score, 1.0)
                        # Extract context around match
                        idx = value_str.lower().find(query_lower)
                        start = max(0, idx - 30)
                        end = min(len(value_str), idx + len(query) + 30)
                        match_context = f"...{value_str[start:end]}..."

                    # Check metadata
                    metadata_str = json.dumps(data.get("metadata", {}))
                    if query_lower in metadata_str.lower():
                        score = max(score, 0.6)
                        if match_context is None:
                            match_context = f"Metadata match"

                    if score > 0:
                        memory = Memory(
                            key=data["key"],
                            value=data["value"],
                            timestamp=datetime.fromisoformat(data["timestamp"]),
                            metadata=data.get("metadata", {}),
                            namespace=tuple(data.get("namespace", []))
                        )
                        results.append(MemorySearchResult(
                            memory=memory,
                            score=score,
                            match_context=match_context
                        ))

            # Sort by score (descending) and limit
            results.sort(key=lambda x: x.score, reverse=True)
            return results[:limit]

    async def list_keys(
        self,
        namespace: Tuple[str, ...]
    ) -> List[str]:
        """List all keys in a namespace."""
        async with self._lock:
            ns_key = self._namespace_key(namespace)
            if ns_key in self._data:
                return list(self._data[ns_key].keys())
            return []

    async def delete(
        self,
        namespace: Tuple[str, ...],
        key: str
    ) -> bool:
        """Delete a memory by key."""
        async with self._lock:
            ns_key = self._namespace_key(namespace)
            if ns_key in self._data and key in self._data[ns_key]:
                del self._data[ns_key][key]
                # Remove empty namespaces
                if not self._data[ns_key]:
                    del self._data[ns_key]
                self._save()
                return True
            return False

    async def list_namespaces(
        self,
        prefix: Optional[Tuple[str, ...]] = None
    ) -> List[Tuple[str, ...]]:
        """List all namespaces, optionally filtered by prefix."""
        async with self._lock:
            namespaces: List[Tuple[str, ...]] = []
            prefix_key = self._namespace_key(prefix) if prefix else ""

            for ns_key in self._data.keys():
                if prefix_key and not ns_key.startswith(prefix_key):
                    continue
                # Convert back to tuple
                if ns_key == "/":
                    namespaces.append(())
                else:
                    namespaces.append(tuple(ns_key.split("/")))

            return namespaces

    async def clear_namespace(
        self,
        namespace: Tuple[str, ...]
    ) -> int:
        """Clear all memories in a namespace.

        Args:
            namespace: The namespace to clear

        Returns:
            Number of memories deleted
        """
        async with self._lock:
            ns_key = self._namespace_key(namespace)
            if ns_key in self._data:
                count = len(self._data[ns_key])
                del self._data[ns_key]
                self._save()
                return count
            return 0

    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the memory store.

        Returns:
            Dictionary with stats (total memories, namespaces, etc.)
        """
        async with self._lock:
            total_memories = sum(len(memories) for memories in self._data.values())
            total_namespaces = len(self._data)

            top_namespaces = sorted(
                [{"namespace": ns, "count": len(memories)}
                 for ns, memories in self._data.items()],
                key=lambda x: x["count"],
                reverse=True
            )[:10]

            return {
                "total_memories": total_memories,
                "total_namespaces": total_namespaces,
                "top_namespaces": top_namespaces,
                "file_path": str(self.file_path)
            }

    async def close(self) -> None:
        """Close the memory store and release any resources.

        For FileMemoryStore, this saves any pending changes.
        """
        async with self._lock:
            self._save()

    async def __aenter__(self) -> "FileMemoryStore":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()


class SQLiteMemoryStore:
    """SQLite-based memory store with FTS5 full-text search.

    Provides production-ready storage with efficient full-text search
    capabilities. Recommended for multi-agent scenarios and production use.
    """

    def __init__(self, db_path: Optional[str] = None):
        """Initialize the SQLite memory store.

        Args:
            db_path: Path to the SQLite database. Defaults to
                     ITERM_MCP_MEMORY_DB_PATH env var or ~/.iterm-mcp/memories.db
        """
        if db_path is None:
            db_path = os.environ.get(
                "ITERM_MCP_MEMORY_DB_PATH",
                os.path.expanduser("~/.iterm-mcp/memories.db")
            )

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = asyncio.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Main memories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    namespace TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    UNIQUE(namespace, key)
                )
            """)

            # Create index on namespace for efficient prefix queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_namespace
                ON memories(namespace)
            """)

            # Check if FTS5 table exists and has correct schema
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='memories_fts'
            """)
            fts_exists = cursor.fetchone() is not None

            # Check if we need to recreate FTS5 (if schema changed)
            needs_recreate = False
            expected_columns = {'key', 'value_text', 'metadata_text', 'namespace'}
            if fts_exists:
                # Check column names to detect schema mismatch
                cursor.execute("PRAGMA table_info(memories_fts)")
                columns = cursor.fetchall()
                # Column name is at index 1 in PRAGMA table_info result
                actual_columns = {col[1] for col in columns}
                if actual_columns != expected_columns:
                    needs_recreate = True

            if needs_recreate:
                # Drop old triggers first
                cursor.execute("DROP TRIGGER IF EXISTS memories_ai")
                cursor.execute("DROP TRIGGER IF EXISTS memories_ad")
                cursor.execute("DROP TRIGGER IF EXISTS memories_au")
                # Drop old FTS table
                cursor.execute("DROP TABLE IF EXISTS memories_fts")
                fts_exists = False

            if not fts_exists:
                # FTS5 virtual table for full-text search
                # Using contentless FTS5 table that stores its own data
                cursor.execute("""
                    CREATE VIRTUAL TABLE memories_fts USING fts5(
                        key,
                        value_text,
                        metadata_text,
                        namespace
                    )
                """)

                # Triggers to keep FTS in sync with main table
                # For standalone FTS5 tables (not using content= option),
                # we use standard DELETE and INSERT operations
                cursor.execute("""
                    CREATE TRIGGER memories_ai AFTER INSERT ON memories BEGIN
                        INSERT INTO memories_fts(rowid, key, value_text, metadata_text, namespace)
                        VALUES (new.id, new.key, new.value, new.metadata, new.namespace);
                    END
                """)

                cursor.execute("""
                    CREATE TRIGGER memories_ad AFTER DELETE ON memories BEGIN
                        DELETE FROM memories_fts WHERE rowid = old.id;
                    END
                """)

                cursor.execute("""
                    CREATE TRIGGER memories_au AFTER UPDATE ON memories BEGIN
                        DELETE FROM memories_fts WHERE rowid = old.id;
                        INSERT INTO memories_fts(rowid, key, value_text, metadata_text, namespace)
                        VALUES (new.id, new.key, new.value, new.metadata, new.namespace);
                    END
                """)

                # Rebuild FTS index from existing data (for migration)
                cursor.execute("""
                    INSERT INTO memories_fts(rowid, key, value_text, metadata_text, namespace)
                    SELECT id, key, value, metadata, namespace FROM memories
                """)

            conn.commit()

    def _namespace_key(self, namespace: Tuple[str, ...]) -> str:
        """Convert namespace tuple to string key."""
        return "/".join(namespace) if namespace else "/"

    def _parse_namespace(self, ns_key: str) -> Tuple[str, ...]:
        """Parse namespace string back to tuple."""
        if ns_key == "/":
            return ()
        return tuple(ns_key.split("/"))

    async def store(
        self,
        namespace: Tuple[str, ...],
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Store a value in the memory store."""
        async with self._lock:
            ns_key = self._namespace_key(namespace)
            value_json = json.dumps(value)
            metadata_json = json.dumps(metadata or {})
            timestamp = datetime.now(timezone.utc).isoformat()

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO memories (namespace, key, value, timestamp, metadata)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(namespace, key) DO UPDATE SET
                        value = excluded.value,
                        timestamp = excluded.timestamp,
                        metadata = excluded.metadata
                """, (ns_key, key, value_json, timestamp, metadata_json))
                conn.commit()

    async def retrieve(
        self,
        namespace: Tuple[str, ...],
        key: str
    ) -> Optional[Memory]:
        """Retrieve a specific memory by key."""
        async with self._lock:
            ns_key = self._namespace_key(namespace)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT namespace, key, value, timestamp, metadata
                    FROM memories
                    WHERE namespace = ? AND key = ?
                """, (ns_key, key))

                row = cursor.fetchone()
                if row:
                    return Memory(
                        key=row[1],
                        value=json.loads(row[2]),
                        timestamp=datetime.fromisoformat(row[3]),
                        metadata=json.loads(row[4]),
                        namespace=self._parse_namespace(row[0])
                    )
                return None

    async def search(
        self,
        namespace: Tuple[str, ...],
        query: str,
        limit: int = 10
    ) -> List[MemorySearchResult]:
        """Search for memories using FTS5 full-text search.

        Falls back to LIKE-based search if FTS5 query fails (e.g., due to
        special characters that can't be properly escaped).
        """
        async with self._lock:
            ns_prefix = self._namespace_key(namespace)
            results: List[MemorySearchResult] = []

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                try:
                    # Use FTS5 search with BM25 ranking
                    # Escape special FTS5 characters (double quotes)
                    escaped_query = query.replace('"', '""')

                    # Search in FTS table and join with main table for full data
                    # Filter by namespace using SQL WHERE clause (not in FTS5 MATCH)
                    # to avoid issues with special characters like / in namespace
                    cursor.execute("""
                        SELECT
                            m.namespace,
                            m.key,
                            m.value,
                            m.timestamp,
                            m.metadata,
                            bm25(memories_fts) as score,
                            snippet(memories_fts, 1, '<b>', '</b>', '...', 32) as match_context
                        FROM memories_fts
                        JOIN memories m ON memories_fts.rowid = m.id
                        WHERE memories_fts MATCH ?
                        AND m.namespace LIKE ?
                        ORDER BY bm25(memories_fts)
                        LIMIT ?
                    """, (f'"{escaped_query}"', f'{ns_prefix}%', limit))

                    for row in cursor.fetchall():
                        memory = Memory(
                            key=row[1],
                            value=json.loads(row[2]),
                            timestamp=datetime.fromisoformat(row[3]),
                            metadata=json.loads(row[4]),
                            namespace=self._parse_namespace(row[0])
                        )
                        # Convert BM25 score (negative, lower is better) to 0-1 range
                        bm25_score = row[5]
                        normalized_score = 1.0 / (1.0 + abs(bm25_score))

                        results.append(MemorySearchResult(
                            memory=memory,
                            score=normalized_score,
                            match_context=row[6]
                        ))

                except sqlite3.OperationalError:
                    # FTS5 query failed, fall back to LIKE-based search
                    like_pattern = f'%{query}%'
                    cursor.execute("""
                        SELECT namespace, key, value, timestamp, metadata
                        FROM memories
                        WHERE namespace LIKE ?
                        AND (key LIKE ? OR value LIKE ? OR metadata LIKE ?)
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """, (f'{ns_prefix}%', like_pattern, like_pattern, like_pattern, limit))

                    for row in cursor.fetchall():
                        memory = Memory(
                            key=row[1],
                            value=json.loads(row[2]),
                            timestamp=datetime.fromisoformat(row[3]),
                            metadata=json.loads(row[4]),
                            namespace=self._parse_namespace(row[0])
                        )
                        # LIKE search doesn't have relevance scoring, use 0.5
                        results.append(MemorySearchResult(
                            memory=memory,
                            score=0.5,
                            match_context=None
                        ))

            return results

    async def list_keys(
        self,
        namespace: Tuple[str, ...]
    ) -> List[str]:
        """List all keys in a namespace."""
        async with self._lock:
            ns_key = self._namespace_key(namespace)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT key FROM memories
                    WHERE namespace = ?
                    ORDER BY key
                """, (ns_key,))

                return [row[0] for row in cursor.fetchall()]

    async def delete(
        self,
        namespace: Tuple[str, ...],
        key: str
    ) -> bool:
        """Delete a memory by key."""
        async with self._lock:
            ns_key = self._namespace_key(namespace)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM memories
                    WHERE namespace = ? AND key = ?
                """, (ns_key, key))
                conn.commit()
                return cursor.rowcount > 0

    async def list_namespaces(
        self,
        prefix: Optional[Tuple[str, ...]] = None
    ) -> List[Tuple[str, ...]]:
        """List all namespaces, optionally filtered by prefix."""
        async with self._lock:
            prefix_key = self._namespace_key(prefix) if prefix else ""

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                if prefix_key:
                    cursor.execute("""
                        SELECT DISTINCT namespace FROM memories
                        WHERE namespace LIKE ?
                        ORDER BY namespace
                    """, (f'{prefix_key}%',))
                else:
                    cursor.execute("""
                        SELECT DISTINCT namespace FROM memories
                        ORDER BY namespace
                    """)

                return [self._parse_namespace(row[0]) for row in cursor.fetchall()]

    async def clear_namespace(
        self,
        namespace: Tuple[str, ...]
    ) -> int:
        """Clear all memories in a namespace.

        Args:
            namespace: The namespace to clear

        Returns:
            Number of memories deleted
        """
        async with self._lock:
            ns_key = self._namespace_key(namespace)

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM memories
                    WHERE namespace = ?
                """, (ns_key,))
                conn.commit()
                return cursor.rowcount

    async def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the memory store.

        Returns:
            Dictionary with stats (total memories, namespaces, etc.)
        """
        async with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM memories")
                total_memories = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(DISTINCT namespace) FROM memories")
                total_namespaces = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT namespace, COUNT(*) as count
                    FROM memories
                    GROUP BY namespace
                    ORDER BY count DESC
                    LIMIT 10
                """)
                top_namespaces = [
                    {"namespace": row[0], "count": row[1]}
                    for row in cursor.fetchall()
                ]

                return {
                    "total_memories": total_memories,
                    "total_namespaces": total_namespaces,
                    "top_namespaces": top_namespaces,
                    "db_path": str(self.db_path)
                }

    async def close(self) -> None:
        """Close the memory store and release any resources.

        Note: SQLite connections are opened and closed per-operation using
        context managers, so this method is mainly for consistency with
        other store implementations and for explicit cleanup signaling.
        """
        # SQLite connections are managed per-operation, no persistent
        # connection to close. This method exists for API consistency.
        pass

    async def __aenter__(self) -> "SQLiteMemoryStore":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()


# Factory function to get the appropriate store
def get_memory_store(
    store_type: str = "sqlite",
    **kwargs: Any
) -> Union[FileMemoryStore, SQLiteMemoryStore]:
    """Get a memory store instance.

    Args:
        store_type: "file" for FileMemoryStore, "sqlite" for SQLiteMemoryStore
        **kwargs: Additional arguments passed to the store constructor

    Returns:
        A MemoryStore implementation
    """
    if store_type == "file":
        return FileMemoryStore(**kwargs)
    elif store_type == "sqlite":
        return SQLiteMemoryStore(**kwargs)
    else:
        raise ValueError(f"Unknown store type: {store_type}")
