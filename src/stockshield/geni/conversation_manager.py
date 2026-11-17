"""Persistent SQLite-backed multi-turn conversation storage for GENI.

Configured with WAL mode, normal synchronous, foreign keys, and busy timeout
for high concurrency and zero cross-analysis context contamination.
"""

import json
import os
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from stockshield.geni.models import GeniConversationInfo, GeniMessage, MessageRole

DEFAULT_GENI_DB_PATH = Path("data/geni_chat.db")


class ConversationNotFoundError(Exception):
    """Raised when the specified conversation_id is not found."""

    pass


class ConversationRunMismatchError(Exception):
    """Raised when a conversation_id belongs to a different analysis run_id."""

    pass


def validate_conversation_id_safe(conversation_id: str) -> str:
    """Validate conversation_id syntax and guard against path traversal attacks."""
    if not isinstance(conversation_id, str):
        raise ValueError("conversation_id must be a string.")
    cleaned = conversation_id.strip()
    if ".." in cleaned or "/" in cleaned or "\\" in cleaned:
        raise ValueError("Path traversal sequences are strictly disallowed in conversation_id.")
    if not re.match(r"^conv_[a-zA-Z0-9_\-]+$", cleaned):
        raise ValueError(
            f"Invalid conversation_id syntax '{conversation_id}'. Expected pattern '^conv_[a-zA-Z0-9_\\-]+$'."
        )
    return cleaned


class GeniConversationManager:
    """Manages thread-safe, ACID-compliant multi-turn conversation threads."""

    def __init__(self, db_path: Optional[str] = None):
        raw_path = db_path or os.getenv("STOCKSHIELD_GENI_DB", str(DEFAULT_GENI_DB_PATH))
        self.db_path = Path(raw_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Create and configure a SQLite connection with WAL mode and foreign keys."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=15.0,
            check_same_thread=False,
            isolation_level=None,  # Autocommit mode; transactions handled explicitly
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 10000;")
        return conn

    def _initialize_database(self):
        """Create schema tables and performance indexes."""
        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS geni_conversations (
                        conversation_id TEXT PRIMARY KEY,
                        run_id TEXT NOT NULL,
                        ticker TEXT NOT NULL,
                        created_at_utc TEXT NOT NULL,
                        updated_at_utc TEXT NOT NULL
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS geni_messages (
                        message_id TEXT PRIMARY KEY,
                        conversation_id TEXT NOT NULL REFERENCES geni_conversations(conversation_id) ON DELETE CASCADE,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        sources_used_json TEXT,
                        created_at_utc TEXT NOT NULL,
                        metadata_json TEXT
                    );
                """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_geni_conv_run ON geni_conversations(run_id);"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_geni_msg_conv ON geni_messages(conversation_id, created_at_utc);"
                )
                conn.execute("COMMIT;")
            except Exception:
                conn.execute("ROLLBACK;")
                raise
            finally:
                conn.close()

    def create_conversation(self, run_id: str, ticker: str) -> GeniConversationInfo:
        """Initialize a new conversation thread bound to a specific analysis run."""
        conv_id = f"conv_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute(
                    """
                    INSERT INTO geni_conversations (conversation_id, run_id, ticker, created_at_utc, updated_at_utc)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    (conv_id, run_id, ticker.upper(), now_iso, now_iso),
                )
                conn.execute("COMMIT;")
                return GeniConversationInfo(
                    conversation_id=conv_id,
                    run_id=run_id,
                    ticker=ticker.upper(),
                    created_at_utc=now_iso,
                    updated_at_utc=now_iso,
                    message_count=0,
                )
            except Exception:
                conn.execute("ROLLBACK;")
                raise
            finally:
                conn.close()

    def get_conversation(self, conversation_id: str) -> Optional[GeniConversationInfo]:
        """Fetch conversation record by identifier."""
        valid_id = validate_conversation_id_safe(conversation_id)
        conn = self._get_connection()
        try:
            cur = conn.execute(
                """
                SELECT c.*, COUNT(m.message_id) AS message_count
                FROM geni_conversations c
                LEFT JOIN geni_messages m ON c.conversation_id = m.conversation_id
                WHERE c.conversation_id = ?
                GROUP BY c.conversation_id;
                """,
                (valid_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return GeniConversationInfo(
                conversation_id=row["conversation_id"],
                run_id=row["run_id"],
                ticker=row["ticker"],
                created_at_utc=row["created_at_utc"],
                updated_at_utc=row["updated_at_utc"],
                message_count=row["message_count"],
            )
        finally:
            conn.close()

    def validate_conversation_for_run(
        self, conversation_id: str, expected_run_id: str
    ) -> GeniConversationInfo:
        """Validate conversation existence and enforce run ownership."""
        info = self.get_conversation(conversation_id)
        if not info:
            raise ConversationNotFoundError(
                f"Conversation '{conversation_id}' was not found in conversation storage."
            )
        if info.run_id != expected_run_id:
            raise ConversationRunMismatchError(
                f"Conversation '{conversation_id}' is associated with analysis run '{info.run_id}', "
                f"not requested run '{expected_run_id}'. Cross-analysis context switching is strictly prohibited."
            )
        return info

    def add_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        sources_used: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GeniMessage:
        """Persist a single turn to the conversation thread and update timestamp."""
        valid_id = validate_conversation_id_safe(conversation_id)
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        sources_json = json.dumps(sources_used or [])
        meta_json = json.dumps(metadata or {})

        with self._lock:
            conn = self._get_connection()
            try:
                conn.execute("BEGIN IMMEDIATE;")
                conn.execute(
                    """
                    INSERT INTO geni_messages (message_id, conversation_id, role, content, sources_used_json, created_at_utc, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                    """,
                    (msg_id, valid_id, role.value, content, sources_json, now_iso, meta_json),
                )
                conn.execute(
                    """
                    UPDATE geni_conversations
                    SET updated_at_utc = ?
                    WHERE conversation_id = ?;
                    """,
                    (now_iso, valid_id),
                )
                conn.execute("COMMIT;")
                return GeniMessage(
                    message_id=msg_id,
                    conversation_id=valid_id,
                    role=role,
                    content=content,
                    sources_used=sources_used or [],
                    created_at_utc=now_iso,
                    metadata=metadata or {},
                )
            except Exception:
                conn.execute("ROLLBACK;")
                raise
            finally:
                conn.close()

    def get_messages(self, conversation_id: str, limit: int = 10) -> List[GeniMessage]:
        """Fetch the most recent turns in chronological order."""
        valid_id = validate_conversation_id_safe(conversation_id)
        conn = self._get_connection()
        try:
            # Query latest N messages and order chronologically
            cur = conn.execute(
                """
                SELECT * FROM (
                    SELECT * FROM geni_messages
                    WHERE conversation_id = ?
                    ORDER BY created_at_utc DESC
                    LIMIT ?
                ) ORDER BY created_at_utc ASC;
                """,
                (valid_id, limit),
            )
            rows = cur.fetchall()
            messages: List[GeniMessage] = []
            for r in rows:
                sources = []
                if r["sources_used_json"]:
                    try:
                        sources = json.loads(r["sources_used_json"])
                    except Exception:
                        sources = []
                meta = {}
                if r["metadata_json"]:
                    try:
                        meta = json.loads(r["metadata_json"])
                    except Exception:
                        meta = {}
                messages.append(
                    GeniMessage(
                        message_id=r["message_id"],
                        conversation_id=r["conversation_id"],
                        role=MessageRole(r["role"]),
                        content=r["content"],
                        sources_used=sources,
                        created_at_utc=r["created_at_utc"],
                        metadata=meta,
                    )
                )
            return messages
        finally:
            conn.close()

    def list_conversations_for_run(self, run_id: str) -> List[GeniConversationInfo]:
        """List all conversation threads created for a specific analysis run."""
        conn = self._get_connection()
        try:
            cur = conn.execute(
                """
                SELECT c.*, COUNT(m.message_id) AS message_count
                FROM geni_conversations c
                LEFT JOIN geni_messages m ON c.conversation_id = m.conversation_id
                WHERE c.run_id = ?
                GROUP BY c.conversation_id
                ORDER BY c.updated_at_utc DESC;
                """,
                (run_id,),
            )
            rows = cur.fetchall()
            return [
                GeniConversationInfo(
                    conversation_id=r["conversation_id"],
                    run_id=r["run_id"],
                    ticker=r["ticker"],
                    created_at_utc=r["created_at_utc"],
                    updated_at_utc=r["updated_at_utc"],
                    message_count=r["message_count"],
                )
                for r in rows
            ]
        finally:
            conn.close()
