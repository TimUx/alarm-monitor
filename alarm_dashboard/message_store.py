"""Thread-safe, persistent store for dashboard messages."""

from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

LOGGER = logging.getLogger(__name__)

PathType = Union[str, "Path"]

_DEFAULT_TTL_MINUTES = 60
_MAX_MESSAGES = 100

# UUID4 format validation: 8-4-4-4-12 hex digits
import re as _re
_UUID_RE = _re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
)


class MessageStore:
    """Thread-safe storage for timed dashboard messages with optional persistence."""

    def __init__(
        self,
        max_ttl_hours: int = 72,
        persistence_path: Optional[PathType] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._messages: List[Dict[str, Any]] = []
        self._max_ttl_hours = max(1, max_ttl_hours)
        self._persistence_path = Path(persistence_path) if persistence_path else None

        if self._persistence_path is not None:
            self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_persisted()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(
        self,
        text: str,
        ttl_minutes: int = _DEFAULT_TTL_MINUTES,
        on_stored: Optional[Callable[[], None]] = None,
    ) -> Dict[str, Any]:
        """Add a new message with the given TTL in minutes and return the stored entry."""
        max_ttl_minutes = self._max_ttl_hours * 60
        clamped_ttl = max(1, min(ttl_minutes, max_ttl_minutes))

        now = datetime.now(timezone.utc)
        message: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "text": text,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=clamped_ttl)).isoformat(),
        }

        with self._lock:
            self._messages.insert(0, message)
            if len(self._messages) > _MAX_MESSAGES:
                self._messages.pop()
            self._persist_locked()

        if on_stored:
            try:
                on_stored()
            except Exception:
                LOGGER.warning("Error in on_stored callback", exc_info=True)

        return message

    def add_with_absolute_expiry(
        self,
        text: str,
        expires_at: datetime,
        on_stored: Optional[Callable[[], None]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Add a message with an absolute expiry datetime (e.g. from ntfy).

        Returns the stored entry, or None if the message is already expired
        or the text is empty.
        """
        if not text or not text.strip():
            return None

        now = datetime.now(timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= now:
            return None

        max_expires_at = now + timedelta(hours=self._max_ttl_hours)
        clamped_expires_at = min(expires_at, max_expires_at)

        message: Dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "text": text.strip(),
            "created_at": now.isoformat(),
            "expires_at": clamped_expires_at.isoformat(),
        }

        with self._lock:
            self._messages.insert(0, message)
            if len(self._messages) > _MAX_MESSAGES:
                self._messages.pop()
            self._persist_locked()

        if on_stored:
            try:
                on_stored()
            except Exception:
                LOGGER.warning("Error in on_stored callback", exc_info=True)

        return message

    def get_active(self) -> List[Dict[str, Any]]:
        """Return all non-expired messages, newest first."""
        now = datetime.now(timezone.utc)
        with self._lock:
            return [
                dict(msg) for msg in self._messages
                if self._parse_expires_at(msg) > now
            ]

    def delete(self, message_id: str) -> bool:
        """Delete a message by ID.  Returns True if found and removed."""
        if not message_id or not _UUID_RE.match(message_id):
            return False
        with self._lock:
            original_len = len(self._messages)
            self._messages = [m for m in self._messages if m.get("id") != message_id]
            deleted = len(self._messages) < original_len
            if deleted:
                self._persist_locked()
        return deleted

    def prune_expired(self) -> int:
        """Remove expired messages.  Returns the number removed."""
        now = datetime.now(timezone.utc)
        with self._lock:
            before = len(self._messages)
            self._messages = [
                m for m in self._messages if self._parse_expires_at(m) > now
            ]
            pruned = before - len(self._messages)
            if pruned > 0:
                self._persist_locked()
        return pruned

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_expires_at(message: Dict[str, Any]) -> datetime:
        """Parse expires_at from a message dict.  Returns epoch (past) on failure."""
        raw = message.get("expires_at")
        if raw:
            try:
                dt = datetime.fromisoformat(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (ValueError, TypeError):
                pass
        return datetime.min.replace(tzinfo=timezone.utc)

    def _load_persisted(self) -> None:
        if self._persistence_path is None or not self._persistence_path.exists():
            return
        try:
            with self._persistence_path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                self._messages = [m for m in data if isinstance(m, dict)]
        except Exception as exc:
            LOGGER.warning(
                "Failed to load persisted messages from %s: %s",
                self._persistence_path,
                exc,
            )

    def _persist_locked(self) -> None:
        if self._persistence_path is None:
            return
        tmp_path = self._persistence_path.with_suffix(".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as fh:
                json.dump(self._messages, fh, ensure_ascii=False, indent=2)
            tmp_path.replace(self._persistence_path)
        except Exception as exc:
            LOGGER.warning(
                "Failed to persist messages to %s: %s",
                self._persistence_path,
                exc,
            )
            tmp_path.unlink(missing_ok=True)


__all__ = ["MessageStore"]
