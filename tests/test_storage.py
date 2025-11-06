"""Tests for the persistent alarm storage."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alarm_dashboard.storage import AlarmStore


def test_alarm_store_persists_and_restores_history(tmp_path):
    history_path = tmp_path / "history.json"

    store = AlarmStore(persistence_path=history_path)
    assert store.history() == []

    payload = {"alarm": {"keyword": "Test"}}
    store.update(payload)

    history = store.history()
    assert len(history) == 1
    assert isinstance(history[0]["received_at"], datetime)
    assert history_path.exists()

    restored_store = AlarmStore(persistence_path=history_path)
    restored_history = restored_store.history()
    assert len(restored_history) == 1
    assert restored_history[0]["alarm"]["keyword"] == "Test"
    assert isinstance(restored_history[0]["received_at"], datetime)

    latest = restored_store.latest()
    assert latest is not None
    assert latest["alarm"]["keyword"] == "Test"
    assert isinstance(latest["received_at"], datetime)
