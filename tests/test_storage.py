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


def test_latest_returns_most_recent_by_alarm_timestamp():
    """latest() should return the alarm with the newest alarm timestamp, not reception order."""
    store = AlarmStore()

    older_payload = {"alarm": {"incident_number": "1", "timestamp": "2024-01-01T10:00:00+00:00"}}
    newer_payload = {"alarm": {"incident_number": "2", "timestamp": "2024-01-01T12:00:00+00:00"}}

    # Receive newer first, then older – latest() must still return the newer one
    store.update(newer_payload)
    store.update(older_payload)

    latest = store.latest()
    assert latest is not None
    assert latest["alarm"]["incident_number"] == "2"


def test_latest_updates_when_truly_newer_alarm_arrives():
    """latest() should update when an alarm with a later timestamp arrives after an older one."""
    store = AlarmStore()

    older_payload = {"alarm": {"incident_number": "A", "timestamp": "2024-03-01T08:00:00+00:00"}}
    newer_payload = {"alarm": {"incident_number": "B", "timestamp": "2024-03-01T09:30:00+00:00"}}

    store.update(older_payload)
    assert store.latest()["alarm"]["incident_number"] == "A"

    store.update(newer_payload)
    assert store.latest()["alarm"]["incident_number"] == "B"


def test_latest_falls_back_to_received_at_when_no_timestamp():
    """latest() should use received_at as fallback when alarm has no timestamp field."""
    store = AlarmStore()

    first_payload = {"alarm": {"incident_number": "X"}}
    second_payload = {"alarm": {"incident_number": "Y"}}

    store.update(first_payload)
    store.update(second_payload)

    # Both lack timestamps; received_at of second > first, so second should win
    latest = store.latest()
    assert latest is not None
    assert latest["alarm"]["incident_number"] == "Y"


def test_latest_persists_most_recent_by_date_across_restart(tmp_path):
    """After restart, latest() should still return the alarm with the newest timestamp."""
    history_path = tmp_path / "history.json"
    store = AlarmStore(persistence_path=history_path)

    older_payload = {"alarm": {"incident_number": "OLD", "timestamp": "2024-06-01T06:00:00+00:00"}}
    newer_payload = {"alarm": {"incident_number": "NEW", "timestamp": "2024-06-01T08:00:00+00:00"}}

    store.update(newer_payload)
    store.update(older_payload)

    restored = AlarmStore(persistence_path=history_path)
    latest = restored.latest()
    assert latest is not None
    assert latest["alarm"]["incident_number"] == "NEW"

