"""Simple storage for alarms and their history with optional persistence."""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

LOGGER = logging.getLogger(__name__)


PathType = Union[str, "Path"]


class AlarmStore:
    """Thread-safe storage for the most recent alarm and a history list."""

    def __init__(
        self,
        max_history: int = 100,
        persistence_path: Optional[PathType] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._alarm: Optional[Dict[str, Any]] = None
        self._history: List[Dict[str, Any]] = []
        self._max_history = max_history
        self._persistence_path = Path(persistence_path) if persistence_path else None

        if self._persistence_path is not None:
            self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
            self._load_persisted_state()

    def update(self, payload: Dict[str, Any]) -> None:
        with self._lock:
            payload = dict(payload)
            payload["received_at"] = datetime.utcnow()
            self._alarm = payload
            self._history.insert(0, dict(payload))
            if len(self._history) > self._max_history:
                self._history.pop()
            self._persist_locked()

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

    def _load_persisted_state(self) -> None:
        if self._persistence_path is None:
            return
        if not self._persistence_path.exists():
            return

        try:
            with self._persistence_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.warning(
                "Failed to read persisted alarm history from %s: %s",
                self._persistence_path,
                exc,
            )
            return

        history_items: List[Dict[str, Any]] = []
        if isinstance(data, dict):
            raw_history = data.get("history", [])
            raw_alarm = data.get("alarm")
        else:
            raw_history = data
            raw_alarm = None

        if isinstance(raw_history, list):
            for item in raw_history[: self._max_history]:
                if isinstance(item, dict):
                    history_items.append(self._restore_entry(item))

        self._history = history_items

        if isinstance(raw_alarm, dict):
            self._alarm = self._restore_entry(raw_alarm)
        elif self._history:
            self._alarm = dict(self._history[0])

    def _persist_locked(self) -> None:
        if self._persistence_path is None:
            return

        data = {
            "alarm": self._prepare_for_storage(self._alarm),
            "history": [
                self._prepare_for_storage(item) for item in self._history[: self._max_history]
            ],
        }

        tmp_path = self._persistence_path.with_suffix(".tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            tmp_path.replace(self._persistence_path)
        except Exception as exc:  # pragma: no cover - defensive
            LOGGER.warning(
                "Failed to persist alarm history to %s: %s",
                self._persistence_path,
                exc,
            )
            tmp_path.unlink(missing_ok=True)

    @staticmethod
    def _prepare_for_storage(entry: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if entry is None:
            return None
        serialised = dict(entry)
        received = serialised.get("received_at")
        if isinstance(received, datetime):
            serialised["received_at"] = received.isoformat()
        return serialised

    @staticmethod
    def _restore_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        restored = dict(entry)
        received = restored.get("received_at")
        if isinstance(received, str):
            try:
                restored["received_at"] = datetime.fromisoformat(received)
            except ValueError:
                pass
        return restored


__all__ = ["AlarmStore"]
