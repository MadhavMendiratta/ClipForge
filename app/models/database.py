"""SQLite database layer for presets and share tokens."""

import json
import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DB_PATH = Path("data/app.db")


def _get_db_path() -> Path:
    """Return the database path, ensuring the parent directory exists."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return DB_PATH


@contextmanager
def get_connection():
    """Context manager for a SQLite connection with row_factory."""
    conn = sqlite3.connect(str(_get_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create database tables if they don't exist."""
    with get_connection() as conn:
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
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_share_tokens_token
            ON share_tokens(token)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_share_tokens_video_id
            ON share_tokens(video_id)
        """)
    logger.info("Database initialized at %s", _get_db_path())


# ── Preset CRUD ──────────────────────────────────────────────────────────────


def create_preset(
    name: str,
    config_json: dict[str, Any],
    description: str = "",
) -> dict[str, Any]:
    """
    Create a new preset.

    Args:
        name: Name of the preset.
        config_json: Configuration dict to store.
        description: Optional description.

    Returns:
        The created preset as a dict.
    """
    preset_id = str(uuid.uuid4())
    created_at = datetime.now(UTC).isoformat()
    config_str = json.dumps(config_json)

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO presets (id, name, description, config_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (preset_id, name, description, config_str, created_at),
        )

    return {
        "id": preset_id,
        "name": name,
        "description": description,
        "config_json": config_json,
        "created_at": created_at,
    }


def list_presets() -> list[dict[str, Any]]:
    """Return all presets ordered by creation date."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM presets ORDER BY created_at DESC"
        ).fetchall()

    return [
        {
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "config_json": json.loads(row["config_json"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def get_preset(preset_id: str) -> Optional[dict[str, Any]]:
    """
    Get a preset by ID.

    Returns:
        Preset dict or None if not found.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM presets WHERE id = ?", (preset_id,)
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "config_json": json.loads(row["config_json"]),
        "created_at": row["created_at"],
    }


# ── Share Token CRUD ─────────────────────────────────────────────────────────


def create_share_token(
    video_id: str,
    expires_at: Optional[str] = None,
    max_views: Optional[int] = None,
) -> dict[str, Any]:
    """
    Create a share token for a video.

    Args:
        video_id: UUID of the video.
        expires_at: Optional ISO expiry timestamp.
        max_views: Optional max view count.

    Returns:
        The created share token as a dict.
    """
    token_id = str(uuid.uuid4())
    token = str(uuid.uuid4()).replace("-", "")
    created_at = datetime.now(UTC).isoformat()

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO share_tokens
               (id, video_id, token, expires_at, max_views, current_views, created_at)
               VALUES (?, ?, ?, ?, ?, 0, ?)""",
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


def get_share_token(token: str) -> Optional[dict[str, Any]]:
    """
    Look up a share token.

    Returns:
        Share token dict or None if not found.
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM share_tokens WHERE token = ?", (token,)
        ).fetchone()

    if row is None:
        return None

    return {
        "id": row["id"],
        "video_id": row["video_id"],
        "token": row["token"],
        "expires_at": row["expires_at"],
        "max_views": row["max_views"],
        "current_views": row["current_views"],
        "created_at": row["created_at"],
    }


def increment_share_views(token: str) -> None:
    """Increment the current_views counter for a share token."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE share_tokens SET current_views = current_views + 1 WHERE token = ?",
            (token,),
        )


def validate_share_token(token_data: dict[str, Any]) -> tuple[bool, str]:
    """
    Validate whether a share token is still usable.

    Args:
        token_data: The share token dict.

    Returns:
        (is_valid, reason) tuple.
    """
    # Check expiry
    if token_data.get("expires_at"):
        try:
            expires = datetime.fromisoformat(token_data["expires_at"])
            if datetime.now(UTC) > expires:
                return False, "Share link has expired"
        except ValueError:
            pass

    # Check view limit
    if token_data.get("max_views") is not None:
        if token_data["current_views"] >= token_data["max_views"]:
            return False, "Maximum views reached"

    return True, "valid"
