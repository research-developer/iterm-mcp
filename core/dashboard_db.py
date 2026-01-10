"""
SQLite database for dashboard observability data.

Stores:
- Claude responses (captured from iTerm2 triggers)
- Teams and their configurations
- Agents and their states
- External services (railway, vercel, resend, etc.)
- Repos and worktrees
"""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = Path.home() / ".iterm-mcp" / "dashboard.db"

# Schema version for migrations
SCHEMA_VERSION = 1

SCHEMA = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- Captured Claude responses (from iTerm2 triggers)
CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    agent_name TEXT,
    session_id TEXT,
    response_type TEXT,  -- 'success' (green), 'neutral' (white), 'error' (red), 'tool' (tool call)
    first_line TEXT,
    full_content TEXT,
    repo_path TEXT,
    duration_ms INTEGER,  -- how long the response took
    tool_name TEXT,  -- if this was a tool call
    FOREIGN KEY (agent_name) REFERENCES agents(name)
);

-- Teams (can be linked to repos)
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    repo_path TEXT,
    parent_team TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_team) REFERENCES teams(name)
);

-- Agents
CREATE TABLE IF NOT EXISTS agents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    session_id TEXT,
    team_name TEXT,
    role TEXT,  -- builder, tester, debugger, researcher, etc.
    status TEXT DEFAULT 'idle',  -- active, idle, error, offline
    agent_type TEXT,  -- claude, gemini, codex, copilot
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_activity DATETIME,
    metadata JSON,
    FOREIGN KEY (team_name) REFERENCES teams(name)
);

-- External Services (railway, vercel, resend, etc.)
CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    service_type TEXT,  -- 'hosting', 'email', 'database', 'ai', 'monitoring'
    provider TEXT,  -- 'railway', 'vercel', 'resend', 'supabase', etc.
    team_name TEXT,
    repo_path TEXT,
    config JSON,  -- connection details, API endpoints, env vars
    status TEXT DEFAULT 'unknown',  -- 'running', 'stopped', 'error', 'unknown'
    url TEXT,  -- service URL if applicable
    last_checked DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, team_name),
    FOREIGN KEY (team_name) REFERENCES teams(name)
);

-- Repos and worktrees
CREATE TABLE IF NOT EXISTS repos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    name TEXT,
    team_name TEXT,
    branch TEXT,
    worktree_path TEXT,
    remote_url TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_name) REFERENCES teams(name)
);

-- Response statistics (aggregated for performance)
CREATE TABLE IF NOT EXISTS response_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    agent_name TEXT,
    response_type TEXT,
    count INTEGER DEFAULT 0,
    avg_duration_ms REAL,
    UNIQUE(date, agent_name, response_type)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_responses_timestamp ON responses(timestamp);
CREATE INDEX IF NOT EXISTS idx_responses_agent ON responses(agent_name);
CREATE INDEX IF NOT EXISTS idx_responses_type ON responses(response_type);
CREATE INDEX IF NOT EXISTS idx_responses_session ON responses(session_id);
CREATE INDEX IF NOT EXISTS idx_agents_team ON agents(team_name);
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);
CREATE INDEX IF NOT EXISTS idx_services_team ON services(team_name);
CREATE INDEX IF NOT EXISTS idx_services_status ON services(status);

-- Full-text search for responses
CREATE VIRTUAL TABLE IF NOT EXISTS responses_fts USING fts5(
    first_line,
    full_content,
    content='responses',
    content_rowid='id'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS responses_ai AFTER INSERT ON responses BEGIN
    INSERT INTO responses_fts(rowid, first_line, full_content)
    VALUES (new.id, new.first_line, new.full_content);
END;

CREATE TRIGGER IF NOT EXISTS responses_ad AFTER DELETE ON responses BEGIN
    INSERT INTO responses_fts(responses_fts, rowid, first_line, full_content)
    VALUES ('delete', old.id, old.first_line, old.full_content);
END;

CREATE TRIGGER IF NOT EXISTS responses_au AFTER UPDATE ON responses BEGIN
    INSERT INTO responses_fts(responses_fts, rowid, first_line, full_content)
    VALUES ('delete', old.id, old.first_line, old.full_content);
    INSERT INTO responses_fts(rowid, first_line, full_content)
    VALUES (new.id, new.first_line, new.full_content);
END;
"""


class DashboardDB:
    """SQLite database for dashboard observability data."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._connect() as conn:
            conn.executescript(SCHEMA)

            # Set schema version if not exists
            cursor = conn.execute("SELECT version FROM schema_version LIMIT 1")
            if cursor.fetchone() is None:
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )
            conn.commit()
        logger.info(f"Dashboard database initialized at {self.db_path}")

    @contextmanager
    def _connect(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # -------------------------------------------------------------------------
    # Response methods
    # -------------------------------------------------------------------------

    def add_response(
        self,
        agent_name: Optional[str] = None,
        session_id: Optional[str] = None,
        response_type: str = "neutral",
        first_line: Optional[str] = None,
        full_content: Optional[str] = None,
        repo_path: Optional[str] = None,
        duration_ms: Optional[int] = None,
        tool_name: Optional[str] = None,
    ) -> int:
        """Add a captured response to the database."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO responses
                (agent_name, session_id, response_type, first_line, full_content,
                 repo_path, duration_ms, tool_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (agent_name, session_id, response_type, first_line, full_content,
                 repo_path, duration_ms, tool_name),
            )
            conn.commit()
            return cursor.lastrowid

    def get_responses(
        self,
        agent_name: Optional[str] = None,
        response_type: Optional[str] = None,
        session_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Query responses with optional filters."""
        query = "SELECT * FROM responses WHERE 1=1"
        params = []

        if agent_name:
            query += " AND agent_name = ?"
            params.append(agent_name)
        if response_type:
            query += " AND response_type = ?"
            params.append(response_type)
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if since:
            query += " AND timestamp >= ?"
            # Use space separator to match SQLite's CURRENT_TIMESTAMP format
            params.append(since.strftime("%Y-%m-%d %H:%M:%S"))

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._connect() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def search_responses(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Full-text search across responses."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT r.* FROM responses r
                JOIN responses_fts fts ON r.id = fts.rowid
                WHERE responses_fts MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    # -------------------------------------------------------------------------
    # Team methods
    # -------------------------------------------------------------------------

    def add_team(
        self,
        name: str,
        description: Optional[str] = None,
        repo_path: Optional[str] = None,
        parent_team: Optional[str] = None,
    ) -> int:
        """Add or update a team."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO teams (name, description, repo_path, parent_team)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    description = excluded.description,
                    repo_path = excluded.repo_path,
                    parent_team = excluded.parent_team,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (name, description, repo_path, parent_team),
            )
            conn.commit()
            return cursor.lastrowid

    def get_teams(self, parent_team: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all teams, optionally filtered by parent."""
        with self._connect() as conn:
            if parent_team:
                cursor = conn.execute(
                    "SELECT * FROM teams WHERE parent_team = ? ORDER BY name",
                    (parent_team,),
                )
            else:
                cursor = conn.execute("SELECT * FROM teams ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]

    def get_team(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific team by name."""
        with self._connect() as conn:
            cursor = conn.execute("SELECT * FROM teams WHERE name = ?", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # -------------------------------------------------------------------------
    # Agent methods
    # -------------------------------------------------------------------------

    def add_agent(
        self,
        name: str,
        session_id: Optional[str] = None,
        team_name: Optional[str] = None,
        role: Optional[str] = None,
        status: str = "idle",
        agent_type: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> int:
        """Add or update an agent."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO agents (name, session_id, team_name, role, status, agent_type, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    session_id = excluded.session_id,
                    team_name = excluded.team_name,
                    role = excluded.role,
                    status = excluded.status,
                    agent_type = excluded.agent_type,
                    metadata = excluded.metadata,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (name, session_id, team_name, role, status, agent_type,
                 json.dumps(metadata) if metadata else None),
            )
            conn.commit()
            return cursor.lastrowid

    def update_agent_status(self, name: str, status: str) -> None:
        """Update an agent's status."""
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE agents
                SET status = ?, updated_at = CURRENT_TIMESTAMP, last_activity = CURRENT_TIMESTAMP
                WHERE name = ?
                """,
                (status, name),
            )
            conn.commit()

    def get_agents(
        self,
        team_name: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get agents with optional filters."""
        query = "SELECT * FROM agents WHERE 1=1"
        params = []

        if team_name:
            query += " AND team_name = ?"
            params.append(team_name)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY name"

        with self._connect() as conn:
            cursor = conn.execute(query, params)
            rows = [dict(row) for row in cursor.fetchall()]
            # Parse metadata JSON
            for row in rows:
                if row.get("metadata"):
                    try:
                        row["metadata"] = json.loads(row["metadata"])
                    except json.JSONDecodeError:
                        pass
            return rows

    def get_agent(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific agent by name."""
        with self._connect() as conn:
            cursor = conn.execute("SELECT * FROM agents WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                if result.get("metadata"):
                    try:
                        result["metadata"] = json.loads(result["metadata"])
                    except json.JSONDecodeError:
                        pass
                return result
            return None

    # -------------------------------------------------------------------------
    # Service methods
    # -------------------------------------------------------------------------

    def add_service(
        self,
        name: str,
        service_type: Optional[str] = None,
        provider: Optional[str] = None,
        team_name: Optional[str] = None,
        repo_path: Optional[str] = None,
        config: Optional[Dict] = None,
        status: str = "unknown",
        url: Optional[str] = None,
    ) -> int:
        """Add or update a service."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO services (name, service_type, provider, team_name, repo_path, config, status, url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(name, team_name) DO UPDATE SET
                    service_type = excluded.service_type,
                    provider = excluded.provider,
                    repo_path = excluded.repo_path,
                    config = excluded.config,
                    status = excluded.status,
                    url = excluded.url
                """,
                (name, service_type, provider, team_name, repo_path,
                 json.dumps(config) if config else None, status, url),
            )
            conn.commit()
            return cursor.lastrowid

    def update_service_status(self, name: str, team_name: Optional[str], status: str) -> None:
        """Update a service's status."""
        with self._connect() as conn:
            if team_name:
                conn.execute(
                    """
                    UPDATE services
                    SET status = ?, last_checked = CURRENT_TIMESTAMP
                    WHERE name = ? AND team_name = ?
                    """,
                    (status, name, team_name),
                )
            else:
                conn.execute(
                    """
                    UPDATE services
                    SET status = ?, last_checked = CURRENT_TIMESTAMP
                    WHERE name = ?
                    """,
                    (status, name),
                )
            conn.commit()

    def get_services(
        self,
        team_name: Optional[str] = None,
        service_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get services with optional filters."""
        query = "SELECT * FROM services WHERE 1=1"
        params = []

        if team_name:
            query += " AND team_name = ?"
            params.append(team_name)
        if service_type:
            query += " AND service_type = ?"
            params.append(service_type)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY name"

        with self._connect() as conn:
            cursor = conn.execute(query, params)
            rows = [dict(row) for row in cursor.fetchall()]
            # Parse config JSON
            for row in rows:
                if row.get("config"):
                    try:
                        row["config"] = json.loads(row["config"])
                    except json.JSONDecodeError:
                        pass
            return rows

    # -------------------------------------------------------------------------
    # Repo methods
    # -------------------------------------------------------------------------

    def add_repo(
        self,
        path: str,
        name: Optional[str] = None,
        team_name: Optional[str] = None,
        branch: Optional[str] = None,
        worktree_path: Optional[str] = None,
        remote_url: Optional[str] = None,
    ) -> int:
        """Add or update a repo."""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO repos (path, name, team_name, branch, worktree_path, remote_url)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    name = excluded.name,
                    team_name = excluded.team_name,
                    branch = excluded.branch,
                    worktree_path = excluded.worktree_path,
                    remote_url = excluded.remote_url,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (path, name, team_name, branch, worktree_path, remote_url),
            )
            conn.commit()
            return cursor.lastrowid

    def get_repos(self, team_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get repos, optionally filtered by team."""
        with self._connect() as conn:
            if team_name:
                cursor = conn.execute(
                    "SELECT * FROM repos WHERE team_name = ? ORDER BY name",
                    (team_name,),
                )
            else:
                cursor = conn.execute("SELECT * FROM repos ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]

    # -------------------------------------------------------------------------
    # Statistics methods
    # -------------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Get aggregated statistics."""
        with self._connect() as conn:
            stats = {}

            # Response counts by type
            cursor = conn.execute(
                """
                SELECT response_type, COUNT(*) as count
                FROM responses
                GROUP BY response_type
                """
            )
            stats["responses_by_type"] = {
                row["response_type"]: row["count"] for row in cursor.fetchall()
            }

            # Total responses
            cursor = conn.execute("SELECT COUNT(*) as count FROM responses")
            stats["total_responses"] = cursor.fetchone()["count"]

            # Agent counts by status
            cursor = conn.execute(
                """
                SELECT status, COUNT(*) as count
                FROM agents
                GROUP BY status
                """
            )
            stats["agents_by_status"] = {
                row["status"]: row["count"] for row in cursor.fetchall()
            }

            # Total agents
            cursor = conn.execute("SELECT COUNT(*) as count FROM agents")
            stats["total_agents"] = cursor.fetchone()["count"]

            # Total teams
            cursor = conn.execute("SELECT COUNT(*) as count FROM teams")
            stats["total_teams"] = cursor.fetchone()["count"]

            # Service counts by status
            cursor = conn.execute(
                """
                SELECT status, COUNT(*) as count
                FROM services
                GROUP BY status
                """
            )
            stats["services_by_status"] = {
                row["status"]: row["count"] for row in cursor.fetchall()
            }

            # Recent activity (last 24 hours)
            cursor = conn.execute(
                """
                SELECT COUNT(*) as count
                FROM responses
                WHERE timestamp >= datetime('now', '-24 hours')
                """
            )
            stats["responses_last_24h"] = cursor.fetchone()["count"]

            # Error rate (last 24 hours)
            cursor = conn.execute(
                """
                SELECT
                    COUNT(CASE WHEN response_type = 'error' THEN 1 END) * 100.0 /
                    NULLIF(COUNT(*), 0) as error_rate
                FROM responses
                WHERE timestamp >= datetime('now', '-24 hours')
                """
            )
            row = cursor.fetchone()
            stats["error_rate_24h"] = round(row["error_rate"] or 0, 2)

            return stats

    def get_response_timeline(
        self,
        hours: int = 24,
        bucket_minutes: int = 60,
    ) -> List[Dict[str, Any]]:
        """Get response counts over time for charting."""
        # Validate hours to prevent SQL injection (must be positive integer)
        hours = max(1, min(int(hours), 720))  # Cap at 30 days
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT
                    strftime('%Y-%m-%d %H:00:00', timestamp) as bucket,
                    response_type,
                    COUNT(*) as count
                FROM responses
                WHERE timestamp >= datetime('now', ? || ' hours')
                GROUP BY bucket, response_type
                ORDER BY bucket
                """,
                (f"-{hours}",),
            )
            return [dict(row) for row in cursor.fetchall()]


# Global database instance
_db: Optional[DashboardDB] = None


def get_db() -> DashboardDB:
    """Get or create the global database instance."""
    global _db
    if _db is None:
        _db = DashboardDB()
    return _db
