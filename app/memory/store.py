"""Conversation memory, kept in SQLite under a session id.

Every chat turn is saved here. The agent replays the most recent turns for a
session so follow-up questions ("which subject is highest?") resolve without the
user repeating themselves, and GET /chat/history reads the whole thread back.
"""

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings

log = logging.getLogger("app.memory")

_initialised = False


def _connect() -> sqlite3.Connection:
    global _initialised
    db = get_settings().memory_db
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    if not _initialised:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                student_id TEXT NOT NULL,
                message TEXT NOT NULL,
                response TEXT NOT NULL,
                intent TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
        _initialised = True
    return conn


def new_session() -> str:
    return uuid.uuid4().hex


def save_turn(session_id: str, student_id: str, message: str, response: str, intent: str) -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO turns (session_id, student_id, message, response, intent, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, student_id, message, response, intent,
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def recent_turns(session_id: str, limit: int) -> list[dict]:
    """The last `limit` turns for a session, oldest first (for replay into the model)."""
    conn = _connect()
    rows = conn.execute(
        "SELECT message, response, intent, created_at FROM turns "
        "WHERE session_id = ? ORDER BY id DESC LIMIT ?",
        (session_id, limit),
    ).fetchall()
    conn.close()
    rows.reverse()
    return [{"message": m, "response": r, "intent": i, "created_at": ts} for m, r, i, ts in rows]


def all_turns(session_id: str) -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT message, response, intent, created_at FROM turns "
        "WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()
    conn.close()
    return [{"message": m, "response": r, "intent": i, "created_at": ts} for m, r, i, ts in rows]


def latest_session() -> str | None:
    """The most recently used session — lets GET /chat/history work with no args."""
    conn = _connect()
    row = conn.execute("SELECT session_id FROM turns ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    return row[0] if row else None
