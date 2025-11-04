"""Simple in-memory storage for alarms and their history."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict, List, Optional


class AlarmStore:
    """Thread-safe storage for the most recent alarm and a history list."""

    def __init__(self, max_history: int = 100) -> None:
        self._lock = threading.Lock()
        self._alarm: Optional[Dict[str, Any]] = None
        self._history: List[Dict[str, Any]] = []
        self._max_history = max_history

    def update(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            payload = dict(payload)
            payload["received_at"] = datetime.utcnow()
            self._alarm = payload
            self._history.insert(0, dict(payload))
            if len(self._history) > self._max_history:
                self._history.pop()

    def get(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if self._alarm is None:
                return None
            return dict(self._alarm)

    def latest(self) -> Optional[Dict[str, Any]]:
        """Return the most recent alarm payload if available."""

        with self._lock:
            if self._alarm is None:
                return None
            return dict(self._alarm)

    def history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return the stored alarm history in chronological order (newest first)."""

        with self._lock:
            items = self._history if limit is None else self._history[:limit]
            return [dict(item) for item in items]


__all__ = ["AlarmStore"]
