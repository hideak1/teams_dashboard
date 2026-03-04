"""SQLite database for team dashboard — schema + CRUD.

Uses WAL mode for concurrent read/write support.
DB location: ~/.claude/team-dashboard.db
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

DB_PATH = Path.home() / ".claude" / "team-dashboard.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS teams (
    name TEXT PRIMARY KEY,
    description TEXT DEFAULT '',
    created_at INTEGER DEFAULT 0,
    lead_agent_id TEXT DEFAULT '',
    member_count INTEGER DEFAULT 0,
    task_count INTEGER DEFAULT 0,
    active INTEGER DEFAULT 1,
    config_json TEXT DEFAULT '{}',
    updated_at REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    team_name TEXT NOT NULL,
    name TEXT NOT NULL,
    agent_type TEXT DEFAULT '',
    model TEXT DEFAULT '',
    cwd TEXT DEFAULT '',
    color TEXT DEFAULT '',
    joined_at INTEGER DEFAULT 0,
    status TEXT DEFAULT 'idle',
    estimated_tokens INTEGER DEFAULT 0,
    updated_at REAL DEFAULT 0,
    FOREIGN KEY (team_name) REFERENCES teams(name)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT DEFAULT '',
    team_name TEXT DEFAULT '',
    agent_name TEXT DEFAULT '',
    hook_event TEXT NOT NULL,
    tool_name TEXT DEFAULT '',
    input_size INTEGER DEFAULT 0,
    output_size INTEGER DEFAULT 0,
    estimated_tokens INTEGER DEFAULT 0,
    payload_json TEXT DEFAULT '{}',
    created_at REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tasks (
    team_name TEXT NOT NULL,
    task_id TEXT NOT NULL,
    subject TEXT DEFAULT '',
    active_form TEXT DEFAULT '',
    owner TEXT DEFAULT '',
    status TEXT DEFAULT 'pending',
    blocks_json TEXT DEFAULT '[]',
    blocked_by_json TEXT DEFAULT '[]',
    updated_at REAL DEFAULT 0,
    PRIMARY KEY (team_name, task_id)
);

CREATE TABLE IF NOT EXISTS inbox_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_name TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    from_agent TEXT DEFAULT '',
    text TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    timestamp TEXT DEFAULT '',
    is_read INTEGER DEFAULT 0,
    created_at REAL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_events_team ON events(team_name);
CREATE INDEX IF NOT EXISTS idx_events_agent ON events(agent_name);
CREATE INDEX IF NOT EXISTS idx_events_created ON events(created_at);
CREATE INDEX IF NOT EXISTS idx_agents_team ON agents(team_name);
CREATE INDEX IF NOT EXISTS idx_tasks_team ON tasks(team_name);
CREATE INDEX IF NOT EXISTS idx_inbox_team ON inbox_messages(team_name);

CREATE TABLE IF NOT EXISTS session_map (
    session_id TEXT PRIMARY KEY,
    team_name TEXT DEFAULT '',
    agent_name TEXT DEFAULT '',
    agent_id TEXT DEFAULT '',
    cwd TEXT DEFAULT '',
    updated_at REAL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_session_map_team ON session_map(team_name);

CREATE TABLE IF NOT EXISTS pane_map (
    pane_id TEXT PRIMARY KEY,
    team_name TEXT DEFAULT '',
    agent_name TEXT DEFAULT '',
    agent_id TEXT DEFAULT '',
    updated_at REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT ''
);
"""


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()


# --- Teams ---


def upsert_team(name: str, description: str, created_at: int, lead: str,
                member_count: int, task_count: int, active: bool, config_json: str):
    conn = get_conn()
    conn.execute(
        """INSERT INTO teams (name, description, created_at, lead_agent_id,
           member_count, task_count, active, config_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(name) DO UPDATE SET
             description=excluded.description,
             created_at=excluded.created_at,
             lead_agent_id=excluded.lead_agent_id,
             member_count=excluded.member_count,
             task_count=excluded.task_count,
             active=excluded.active,
             config_json=excluded.config_json,
             updated_at=excluded.updated_at""",
        (name, description, created_at, lead, member_count, task_count,
         1 if active else 0, config_json, time.time()),
    )
    conn.commit()
    conn.close()


def get_all_teams() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM teams ORDER BY active DESC, created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_team(name: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM teams WHERE name=?", (name,)).fetchone()
    conn.close()
    return dict(row) if row else None


# --- Agents ---


def upsert_agent(agent_id: str, team_name: str, name: str, agent_type: str,
                 model: str, cwd: str, color: str, joined_at: int, status: str):
    conn = get_conn()
    conn.execute(
        """INSERT INTO agents (agent_id, team_name, name, agent_type, model, cwd, color, joined_at, status, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(agent_id) DO UPDATE SET
             team_name=excluded.team_name, name=excluded.name, agent_type=excluded.agent_type,
             model=excluded.model, cwd=excluded.cwd, color=excluded.color,
             status=excluded.status, updated_at=excluded.updated_at""",
        (agent_id, team_name, name, agent_type, model, cwd, color, joined_at, status, time.time()),
    )
    conn.commit()
    conn.close()


def get_agents_for_team(team_name: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM agents WHERE team_name=? ORDER BY joined_at", (team_name,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_agent_tokens(agent_id: str, tokens: int):
    conn = get_conn()
    conn.execute("UPDATE agents SET estimated_tokens = estimated_tokens + ? WHERE agent_id=?", (tokens, agent_id))
    conn.commit()
    conn.close()


# --- Events ---


def insert_event(session_id: str, team_name: str, agent_name: str, hook_event: str,
                 tool_name: str, input_size: int, output_size: int,
                 estimated_tokens: int, payload_json: str):
    conn = get_conn()
    conn.execute(
        """INSERT INTO events (session_id, team_name, agent_name, hook_event, tool_name,
           input_size, output_size, estimated_tokens, payload_json, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (session_id, team_name, agent_name, hook_event, tool_name,
         input_size, output_size, estimated_tokens, payload_json, time.time()),
    )
    conn.commit()
    conn.close()


def get_events(team_name: str = "", agent_name: str = "", limit: int = 100) -> list[dict]:
    conn = get_conn()
    sql = "SELECT * FROM events WHERE 1=1"
    params: list = []
    if team_name:
        sql += " AND team_name=?"
        params.append(team_name)
    if agent_name:
        sql += " AND agent_name=?"
        params.append(agent_name)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_token_stats(team_name: str = "") -> list[dict]:
    conn = get_conn()
    sql = """SELECT agent_name, SUM(estimated_tokens) as total_tokens,
             COUNT(*) as event_count FROM events WHERE 1=1"""
    params: list = []
    if team_name:
        sql += " AND team_name=?"
        params.append(team_name)
    sql += " GROUP BY agent_name ORDER BY total_tokens DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_token_timeline(team_name: str = "", agent_name: str = "", bucket_seconds: int = 60) -> list[dict]:
    conn = get_conn()
    sql = f"""SELECT CAST(created_at / {bucket_seconds} AS INTEGER) * {bucket_seconds} as bucket,
              agent_name, SUM(estimated_tokens) as tokens
              FROM events WHERE estimated_tokens > 0"""
    params: list = []
    if team_name:
        sql += " AND team_name=?"
        params.append(team_name)
    if agent_name:
        sql += " AND agent_name=?"
        params.append(agent_name)
    sql += " GROUP BY bucket, agent_name ORDER BY bucket"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Tasks ---


def upsert_task(team_name: str, task_id: str, subject: str, active_form: str,
                owner: str, status: str, blocks_json: str, blocked_by_json: str):
    conn = get_conn()
    conn.execute(
        """INSERT INTO tasks (team_name, task_id, subject, active_form, owner, status, blocks_json, blocked_by_json, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(team_name, task_id) DO UPDATE SET
             subject=excluded.subject, active_form=excluded.active_form,
             owner=excluded.owner, status=excluded.status,
             blocks_json=excluded.blocks_json, blocked_by_json=excluded.blocked_by_json,
             updated_at=excluded.updated_at""",
        (team_name, task_id, subject, active_form, owner or "", status, blocks_json, blocked_by_json, time.time()),
    )
    conn.commit()
    conn.close()


def get_tasks_for_team(team_name: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM tasks WHERE team_name=? ORDER BY CAST(task_id AS INTEGER)", (team_name,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Inbox ---


def upsert_inbox_message(team_name: str, agent_name: str, from_agent: str,
                         text: str, summary: str, timestamp: str, is_read: bool):
    conn = get_conn()
    # Use team+agent+timestamp as dedup key
    existing = conn.execute(
        "SELECT id FROM inbox_messages WHERE team_name=? AND agent_name=? AND timestamp=? AND from_agent=?",
        (team_name, agent_name, timestamp, from_agent),
    ).fetchone()
    if not existing:
        conn.execute(
            """INSERT INTO inbox_messages (team_name, agent_name, from_agent, text, summary, timestamp, is_read, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (team_name, agent_name, from_agent, text, summary, timestamp, 1 if is_read else 0, time.time()),
        )
        conn.commit()
    conn.close()


def get_inbox_for_team(team_name: str, limit: int = 50) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM inbox_messages WHERE team_name=? ORDER BY timestamp DESC LIMIT ?",
        (team_name, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Session map ---


def upsert_session_map(session_id: str, team_name: str, agent_name: str,
                       agent_id: str = "", cwd: str = ""):
    conn = get_conn()
    conn.execute(
        """INSERT INTO session_map (session_id, team_name, agent_name, agent_id, cwd, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(session_id) DO UPDATE SET
             team_name=excluded.team_name, agent_name=excluded.agent_name,
             agent_id=excluded.agent_id, cwd=excluded.cwd, updated_at=excluded.updated_at""",
        (session_id, team_name, agent_name, agent_id, cwd, time.time()),
    )
    conn.commit()
    conn.close()


def get_session_agent(session_id: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM session_map WHERE session_id=?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_pane_map(pane_id: str, team_name: str, agent_name: str, agent_id: str = ""):
    conn = get_conn()
    conn.execute(
        """INSERT INTO pane_map (pane_id, team_name, agent_name, agent_id, updated_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(pane_id) DO UPDATE SET
             team_name=excluded.team_name, agent_name=excluded.agent_name,
             agent_id=excluded.agent_id, updated_at=excluded.updated_at""",
        (pane_id, team_name, agent_name, agent_id, time.time()),
    )
    conn.commit()
    conn.close()


def get_pane_agent(pane_id: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM pane_map WHERE pane_id=?", (pane_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def match_session_to_agent(cwd: str) -> Optional[dict]:
    """Match a session to an agent by comparing cwd paths."""
    if not cwd:
        return None
    conn = get_conn()
    # Try exact cwd match against known agents
    row = conn.execute("SELECT * FROM agents WHERE cwd=? LIMIT 1", (cwd,)).fetchone()
    conn.close()
    return dict(row) if row else None


# --- Per-agent queries ---


def get_tasks_for_agent(team_name: str, agent_name: str) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM tasks WHERE team_name=? AND owner=? ORDER BY CAST(task_id AS INTEGER)",
        (team_name, agent_name),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_inbox_for_agent(team_name: str, agent_name: str, limit: int = 50) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        """SELECT * FROM inbox_messages
           WHERE team_name=? AND (agent_name=? OR from_agent=?)
           ORDER BY timestamp DESC LIMIT ?""",
        (team_name, agent_name, agent_name, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Meta (key-value store for watcher state) ---


def get_meta(key: str) -> Optional[str]:
    conn = get_conn()
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def set_meta(key: str, value: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


# --- Global stats ---


def get_global_stats() -> dict:
    conn = get_conn()
    teams = conn.execute("SELECT COUNT(*) as c, SUM(active) as a FROM teams").fetchone()
    agents = conn.execute("SELECT COUNT(*) as c FROM agents").fetchone()
    tasks = conn.execute("SELECT COUNT(*) as total, SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as done FROM tasks").fetchone()
    tokens = conn.execute("SELECT COALESCE(SUM(estimated_tokens), 0) as t FROM events").fetchone()
    conn.close()
    return {
        "total_teams": teams["c"] or 0,
        "active_teams": int(teams["a"] or 0),
        "total_agents": agents["c"] or 0,
        "total_tasks": tasks["total"] or 0,
        "completed_tasks": int(tasks["done"] or 0),
        "total_estimated_tokens": tokens["t"] or 0,
    }
