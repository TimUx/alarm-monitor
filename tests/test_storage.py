"""Tests for the persistent alarm storage."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import sys
import pytest

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


def test_has_incident_number_returns_false_for_empty_history():
    """has_incident_number should return False when history is empty."""
    store = AlarmStore()
    assert store.has_incident_number("12345") is False


def test_has_incident_number_raises_error_for_none():
    """has_incident_number should raise ValueError for None."""
    store = AlarmStore()
    with pytest.raises(ValueError, match="must not be None or empty"):
        store.has_incident_number(None)


def test_has_incident_number_raises_error_for_empty_string():
    """has_incident_number should raise ValueError for empty string."""
    store = AlarmStore()
    with pytest.raises(ValueError, match="must not be None or empty"):
        store.has_incident_number("")


def test_has_incident_number_detects_existing_incident():
    """has_incident_number should return True when incident number exists."""
    store = AlarmStore()
    payload = {"alarm": {"keyword": "Test", "incident_number": "12345"}}
    store.update(payload)
    assert store.has_incident_number("12345") is True


def test_has_incident_number_returns_false_for_nonexistent_incident():
    """has_incident_number should return False when incident number doesn't exist."""
    store = AlarmStore()
    payload = {"alarm": {"keyword": "Test", "incident_number": "12345"}}
    store.update(payload)
    assert store.has_incident_number("67890") is False


def test_has_incident_number_works_with_multiple_entries():
    """has_incident_number should find incidents in a multi-entry history."""
    store = AlarmStore()
    
    payload1 = {"alarm": {"keyword": "Test1", "incident_number": "11111"}}
    payload2 = {"alarm": {"keyword": "Test2", "incident_number": "22222"}}
    payload3 = {"alarm": {"keyword": "Test3", "incident_number": "33333"}}
    
    store.update(payload1)
    store.update(payload2)
    store.update(payload3)
    
    assert store.has_incident_number("11111") is True
    assert store.has_incident_number("22222") is True
    assert store.has_incident_number("33333") is True
    assert store.has_incident_number("44444") is False


def test_has_incident_number_with_alarm_without_incident_number():
    """has_incident_number should handle alarms without incident_number field."""
    store = AlarmStore()
    payload = {"alarm": {"keyword": "Test"}}  # No incident_number
    store.update(payload)
    assert store.has_incident_number("12345") is False


def test_has_incident_number_persists_across_restarts(tmp_path):
    """has_incident_number should work with persisted history."""
    history_path = tmp_path / "history.json"
    
    # First store instance
    store1 = AlarmStore(persistence_path=history_path)
    payload = {"alarm": {"keyword": "Test", "incident_number": "99999"}}
    store1.update(payload)
    
    # Second store instance (simulating restart)
    store2 = AlarmStore(persistence_path=history_path)
    assert store2.has_incident_number("99999") is True
    assert store2.has_incident_number("88888") is False

