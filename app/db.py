"""SQLite persistence for rooms and danmaku messages.

Each call opens a short-lived connection (WAL mode), so the same helpers are
safe from both HTTP worker threads and the WebSocket handler thread.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS rooms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    anchor_name TEXT NOT NULL,
    stream_name TEXT NOT NULL UNIQUE,
    status      TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'ended')),
    created_at  TEXT NOT NULL,
    ended_at    TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id    INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    nickname   TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_room ON messages(room_id, id);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_stream_name() -> str:
    return f"stream_{uuid.uuid4().hex[:12]}"


def _db_path(path: str) -> str:
    if path.startswith("file:"):
        return path
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    return path


@contextmanager
def connection(db_path: str):
    conn = sqlite3.connect(_db_path(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    with connection(db_path) as conn:
        conn.executescript(SCHEMA)


def _room(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "anchor_name": row["anchor_name"],
        "stream_name": row["stream_name"],
        "status": row["status"],
        "created_at": row["created_at"],
        "ended_at": row["ended_at"],
    }


def _message(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "room_id": row["room_id"],
        "nickname": row["nickname"],
        "content": row["content"],
        "created_at": row["created_at"],
    }


def create_room(db_path: str, title: str, anchor_name: str, stream_name: str | None = None) -> dict:
    with connection(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO rooms (title, anchor_name, stream_name, status, created_at) VALUES (?, ?, ?, 'running', ?)",
            (title, anchor_name, stream_name or new_stream_name(), now_iso()),
        )
        row = conn.execute("SELECT * FROM rooms WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _room(row)


def list_rooms(db_path: str) -> list[dict]:
    with connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM rooms ORDER BY (status = 'running') DESC, id DESC"
        ).fetchall()
    return [_room(row) for row in rows]


def get_room(db_path: str, room_id: int) -> dict | None:
    with connection(db_path) as conn:
        row = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    return _room(row) if row else None


def stop_room(db_path: str, room_id: int) -> dict | None:
    """End a live room. Idempotent: an already ended room keeps its ended_at."""
    with connection(db_path) as conn:
        row = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
        if row is None:
            return None
        if row["status"] == "running":
            conn.execute(
                "UPDATE rooms SET status = 'ended', ended_at = ? WHERE id = ?",
                (now_iso(), room_id),
            )
            row = conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
    return _room(row)


def add_message(db_path: str, room_id: int, nickname: str, content: str) -> dict:
    with connection(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO messages (room_id, nickname, content, created_at) VALUES (?, ?, ?, ?)",
            (room_id, nickname, content, now_iso()),
        )
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _message(row)


def list_messages(db_path: str, room_id: int, limit: int = 100) -> list[dict]:
    limit = max(1, min(int(limit), 200))
    with connection(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM (SELECT * FROM messages WHERE room_id = ? ORDER BY id DESC LIMIT ?) "
            "ORDER BY id ASC",
            (room_id, limit),
        ).fetchall()
    return [_message(row) for row in rows]