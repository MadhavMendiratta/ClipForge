"""SQLite database layer for presets and share tokens."""

import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from app.core.settings import settings

logger = logging.getLogger(__name__)


@contextmanager
def get_connection():
    conn = sqlite3.connect(str(settings.database_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)

    with get_connection() as conn:
        conn.execute("PRAGMA journal_mode=WAL")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS presets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                config_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS share_tokens (
                id TEXT PRIMARY KEY,
                video_id TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TEXT,
                max_views INTEGER,
                current_views INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_token ON share_tokens(token)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_video ON share_tokens(video_id)")


# ───── PRESETS CRUD ─────

def create_preset(name: str, config_json: dict[str, Any], description: str = "") -> dict:
    preset_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).isoformat()

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO presets VALUES (?, ?, ?, ?, ?)",
            (preset_id, name, description, json.dumps(config_json), created_at),
        )

    return {
        "id": preset_id,
        "name": name,
        "description": description,
        "config_json": config_json,
        "created_at": created_at,
    }


def list_presets() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM presets ORDER BY created_at DESC").fetchall()

    return [
        {
            "id": r["id"],
            "name": r["name"],
            "description": r["description"],
            "config_json": json.loads(r["config_json"]),
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def get_preset(preset_id: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM presets WHERE id=?", (preset_id,)).fetchone()

    if not row:
        return None

    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "config_json": json.loads(row["config_json"]),
        "created_at": row["created_at"],
    }


def update_preset(preset_id: str, name: str, config_json: dict, description: str = "") -> bool:
    with get_connection() as conn:
        res = conn.execute(
            "UPDATE presets SET name=?, description=?, config_json=? WHERE id=?",
            (name, description, json.dumps(config_json), preset_id),
        )
    return res.rowcount > 0


def delete_preset(preset_id: str) -> bool:
    with get_connection() as conn:
        res = conn.execute("DELETE FROM presets WHERE id=?", (preset_id,))
    return res.rowcount > 0


# ───── SHARE TOKENS CRUD ─────

def create_share_token(video_id: str, expires_at: Optional[str] = None, max_views: Optional[int] = None) -> dict:
    token_id = str(uuid.uuid4())
    token = str(uuid.uuid4()).replace("-", "")
    created_at = datetime.now(UTC).isoformat()

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO share_tokens VALUES (?, ?, ?, ?, ?, 0, ?)",
            (token_id, video_id, token, expires_at, max_views, created_at),
        )

    return {
        "id": token_id,
        "video_id": video_id,
        "token": token,
        "expires_at": expires_at,
        "max_views": max_views,
        "current_views": 0,
        "created_at": created_at,
    }


def get_share_token(token: str) -> Optional[dict]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM share_tokens WHERE token=?", (token,)).fetchone()

    if not row:
        return None

    return dict(row)


def increment_share_views(token: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE share_tokens SET current_views = current_views + 1 WHERE token=?",
            (token,),
        )


def delete_share_token(token: str) -> bool:
    with get_connection() as conn:
        res = conn.execute("DELETE FROM share_tokens WHERE token=?", (token,))
    return res.rowcount > 0


def validate_share_token(token_data: dict) -> tuple[bool, str]:
    if token_data.get("expires_at"):
        if datetime.now(UTC) > datetime.fromisoformat(token_data["expires_at"]):
            return False, "expired"

    if token_data.get("max_views") is not None:
        if token_data["current_views"] >= token_data["max_views"]:
            return False, "limit reached"

    return True, "valid"