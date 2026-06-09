"""
CodingCat - Storage / SQLite layer
Handles settings persistence, session statistics, and Pomodoro history.
"""
from __future__ import annotations
import sqlite3
import os
import time
from typing import Any, Optional
from config import APP_NAME, DB_NAME

DB_PATH = os.path.join(os.path.expanduser("~"), ".coding_cat", DB_NAME)


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_type TEXT NOT NULL,
                started_at REAL NOT NULL,
                ended_at   REAL,
                duration_s REAL
            );
            CREATE TABLE IF NOT EXISTS stats (
                date       TEXT PRIMARY KEY,
                keystrokes INTEGER DEFAULT 0,
                active_s   REAL    DEFAULT 0,
                pomodoros  INTEGER DEFAULT 0
            );
        """)


def get_setting(key: str, default: Any = None) -> Any:
    try:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
            return row["value"] if row else default
    except Exception:
        return default


def set_setting(key: str, value: Any) -> None:
    try:
        with _get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings(key, value) VALUES (?,?)",
                (key, str(value))
            )
    except Exception:
        pass


def log_session(session_type: str, duration_s: float) -> None:
    try:
        now = time.time()
        with _get_conn() as conn:
            conn.execute(
                "INSERT INTO sessions(session_type,started_at,ended_at,duration_s) VALUES(?,?,?,?)",
                (session_type, now - duration_s, now, duration_s)
            )
            date = time.strftime("%Y-%m-%d")
            conn.execute("""
                INSERT INTO stats(date,pomodoros) VALUES(?,1)
                ON CONFLICT(date) DO UPDATE SET pomodoros=pomodoros+1
            """, (date,))
    except Exception:
        pass


def increment_keystrokes(count: int = 1) -> None:
    try:
        date = time.strftime("%Y-%m-%d")
        with _get_conn() as conn:
            conn.execute("""
                INSERT INTO stats(date,keystrokes) VALUES(?,?)
                ON CONFLICT(date) DO UPDATE SET keystrokes=keystrokes+?
            """, (date, count, count))
    except Exception:
        pass
