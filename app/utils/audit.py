"""Per-request audit log.

Requirement 7 asks for a log of every query with its intent, the tool(s) used,
how long it took, the response and a timestamp. We write that to a SQLite table
(queryable later) and mirror a one-line summary into the rotating app log.
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings

log = logging.getLogger("app.audit")

_initialised = False


def _connect() -> sqlite3.Connection:
    global _initialised
    db = get_settings().audit_db
    Path(db).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    if not _initialised:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS request_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                intent TEXT NOT NULL,
                tools TEXT NOT NULL,
                execution_ms INTEGER NOT NULL,
                response TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
        _initialised = True
    return conn


def record(query: str, intent: str, tools: list[str], execution_ms: int, response: str) -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO request_logs (query, intent, tools, execution_ms, response, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (query, intent, ", ".join(tools) or "-", execution_ms, response,
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()
    log.info("query=%r intent=%s tools=%s time=%dms", query, intent, tools or "-", execution_ms)
