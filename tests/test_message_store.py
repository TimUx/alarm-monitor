"""Tests for the MessageStore."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alarm_dashboard.message_store import MessageStore
from alarm_dashboard.ntfy_client import NtfyPoller


# ---------------------------------------------------------------------------
# add / get_active
# ---------------------------------------------------------------------------


def test_add_returns_message_with_fields():
    store = MessageStore()
    msg = store.add("Übung fällt aus", ttl_minutes=60)
    assert msg["text"] == "Übung fällt aus"
    assert "id" in msg
    assert "created_at" in msg
    assert "expires_at" in msg


def test_get_active_returns_non_expired():
    store = MessageStore()
    store.add("Aktiv", ttl_minutes=60)
    active = store.get_active()
    assert len(active) == 1
    assert active[0]["text"] == "Aktiv"


def test_get_active_excludes_expired():
    store = MessageStore()
    msg = store.add("Abgelaufen", ttl_minutes=1)
    # Manually expire by back-dating expires_at
    with store._lock:
        store._messages[0]["expires_at"] = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        ).isoformat()
    active = store.get_active()
    assert active == []


def test_get_active_newest_first():
    store = MessageStore()
    store.add("Erste", ttl_minutes=60)
    store.add("Zweite", ttl_minutes=60)
    active = store.get_active()
    assert len(active) == 2
    assert active[0]["text"] == "Zweite"
    assert active[1]["text"] == "Erste"


# ---------------------------------------------------------------------------
# TTL clamping
# ---------------------------------------------------------------------------


def test_ttl_clamped_to_max():
    store = MessageStore(max_ttl_hours=1)
    msg = store.add("Test", ttl_minutes=600)  # 10 hours – over the 1h max
    expires_at = datetime.fromisoformat(msg["expires_at"])
    created_at = datetime.fromisoformat(msg["created_at"])
    delta = expires_at - created_at
    assert delta <= timedelta(hours=1, seconds=5)


def test_ttl_minimum_one_minute():
    store = MessageStore()
    msg = store.add("Min", ttl_minutes=0)
    expires_at = datetime.fromisoformat(msg["expires_at"])
    created_at = datetime.fromisoformat(msg["created_at"])
    delta = expires_at - created_at
    assert delta >= timedelta(minutes=1)


# ---------------------------------------------------------------------------
# add_with_absolute_expiry
# ---------------------------------------------------------------------------


def test_add_with_absolute_expiry_stores_message():
    store = MessageStore()
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    msg = store.add_with_absolute_expiry("ntfy Nachricht", expires)
    assert msg is not None
    assert msg["text"] == "ntfy Nachricht"


def test_add_with_absolute_expiry_rejects_past():
    store = MessageStore()
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    result = store.add_with_absolute_expiry("Alt", past)
    assert result is None
    assert store.get_active() == []


def test_add_with_absolute_expiry_rejects_empty_text():
    store = MessageStore()
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    result = store.add_with_absolute_expiry("  ", expires)
    assert result is None


def test_add_with_absolute_expiry_clamps_to_max_ttl():
    store = MessageStore(max_ttl_hours=1)
    far_future = datetime.now(timezone.utc) + timedelta(days=30)
    msg = store.add_with_absolute_expiry("Weit entfernt", far_future)
    assert msg is not None
    expires_at = datetime.fromisoformat(msg["expires_at"])
    assert expires_at <= datetime.now(timezone.utc) + timedelta(hours=1, seconds=5)


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def test_delete_removes_message():
    store = MessageStore()
    msg = store.add("Zu löschen", ttl_minutes=60)
    result = store.delete(msg["id"])
    assert result is True
    assert store.get_active() == []


def test_delete_returns_false_for_unknown_id():
    store = MessageStore()
    result = store.delete("00000000-0000-0000-0000-000000000000")
    assert result is False


def test_delete_returns_false_for_invalid_id():
    store = MessageStore()
    result = store.delete("not-a-uuid")
    assert result is False


def test_delete_by_source_id_removes_matching_messages():
    store = MessageStore()
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    store.add_with_absolute_expiry("A", expires, source_id="seq-1")
    store.add_with_absolute_expiry("B", expires, source_id="seq-2")
    result = store.delete_by_source_id("seq-1")
    assert result is True
    active = store.get_active()
    assert len(active) == 1
    assert active[0]["text"] == "B"


def test_delete_by_source_id_returns_false_for_unknown_id():
    store = MessageStore()
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    store.add_with_absolute_expiry("A", expires, source_id="seq-1")
    assert store.delete_by_source_id("seq-unknown") is False


# ---------------------------------------------------------------------------
# prune_expired
# ---------------------------------------------------------------------------


def test_prune_expired_removes_expired_only():
    store = MessageStore()
    store.add("Aktiv", ttl_minutes=60)
    expired_msg = store.add("Abgelaufen", ttl_minutes=1)
    # Back-date the expired message
    with store._lock:
        for m in store._messages:
            if m["id"] == expired_msg["id"]:
                m["expires_at"] = (
                    datetime.now(timezone.utc) - timedelta(minutes=1)
                ).isoformat()
    pruned = store.prune_expired()
    assert pruned == 1
    active = store.get_active()
    assert len(active) == 1
    assert active[0]["text"] == "Aktiv"


# ---------------------------------------------------------------------------
# on_stored callback
# ---------------------------------------------------------------------------


def test_on_stored_callback_called():
    called = []
    store = MessageStore()
    store.add("Callback-Test", ttl_minutes=60, on_stored=lambda: called.append(True))
    assert called == [True]


def test_on_stored_callback_not_called_on_rejected():
    called = []
    store = MessageStore()
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    store.add_with_absolute_expiry(
        "Alt", past, on_stored=lambda: called.append(True)
    )
    assert called == []


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_persistence_round_trip(tmp_path: Path):
    path = tmp_path / "messages.json"
    store1 = MessageStore(persistence_path=path)
    store1.add("Persistent", ttl_minutes=60)

    store2 = MessageStore(persistence_path=path)
    active = store2.get_active()
    assert len(active) == 1
    assert active[0]["text"] == "Persistent"


def test_persistence_file_created(tmp_path: Path):
    path = tmp_path / "messages.json"
    store = MessageStore(persistence_path=path)
    store.add("Test", ttl_minutes=60)
    assert path.exists()


def test_delete_persisted(tmp_path: Path):
    path = tmp_path / "messages.json"
    store1 = MessageStore(persistence_path=path)
    msg = store1.add("Zu löschen", ttl_minutes=60)
    store1.delete(msg["id"])

    store2 = MessageStore(persistence_path=path)
    assert store2.get_active() == []


# ---------------------------------------------------------------------------
# NtfyPoller – settings-driven behaviour
# ---------------------------------------------------------------------------


def _make_settings(topic_url="https://ntfy.sh/test", poll_interval=60, default_ttl=60):
    return {
        "ntfy_topic_url": topic_url,
        "ntfy_poll_interval": poll_interval,
        "message_default_ttl_minutes": default_ttl,
    }


def test_ntfy_poller_uses_default_ttl_from_settings():
    """NtfyPoller._resolve_expires should fall back to settings default_ttl."""
    event_without_expires = {"event": "message", "message": "Test"}
    result = NtfyPoller._resolve_expires(event_without_expires, default_ttl_minutes=30)
    delta = result - datetime.now(timezone.utc)
    # Allow ±5 seconds tolerance
    assert timedelta(minutes=29, seconds=55) <= delta <= timedelta(minutes=30, seconds=5)


def test_ntfy_poller_uses_ntfy_expires_when_present():
    """NtfyPoller._resolve_expires should honour ntfy-provided expires timestamp."""
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    event_with_expires = {
        "event": "message",
        "message": "Test",
        "expires": future.timestamp(),
    }
    result = NtfyPoller._resolve_expires(event_with_expires, default_ttl_minutes=30)
    # Should match future within a second
    assert abs((result - future).total_seconds()) < 2


def test_ntfy_poller_skips_poll_when_no_topic_url():
    """NtfyPoller._poll_once should do nothing when ntfy_topic_url is empty."""
    store = MessageStore()
    settings = _make_settings(topic_url="")
    poller = NtfyPoller(get_effective_settings=lambda: settings, message_store=store)

    # _poll_once should return without calling requests
    with patch("alarm_dashboard.ntfy_client.requests.get") as mock_get:
        poller._poll_once()
    mock_get.assert_not_called()
    assert store.get_active() == []


def test_ntfy_poller_applies_default_ttl_when_no_expires_in_event():
    """NtfyPoller should store a message with default TTL when no expires field."""
    store = MessageStore()
    settings = _make_settings(topic_url="https://ntfy.sh/test", default_ttl=45)
    poller = NtfyPoller(get_effective_settings=lambda: settings, message_store=store)

    ntfy_response = '{"id":"abc","event":"message","message":"Übung fällt aus"}\n'
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.text = ntfy_response

    with patch("alarm_dashboard.ntfy_client.requests.get", return_value=mock_resp):
        poller._poll_once()

    active = store.get_active()
    assert len(active) == 1
    assert active[0]["text"] == "Übung fällt aus"

    expires_at = datetime.fromisoformat(active[0]["expires_at"])
    delta = expires_at - datetime.now(timezone.utc)
    # Should be around 45 minutes
    assert timedelta(minutes=44) <= delta <= timedelta(minutes=46)


def test_ntfy_poller_resets_last_poll_time_on_url_change():
    """NtfyPoller should reset its poll history when the topic URL changes."""
    store = MessageStore()
    settings = {"ntfy_topic_url": "https://ntfy.sh/topic-a", "ntfy_poll_interval": 60, "message_default_ttl_minutes": 60}
    poller = NtfyPoller(get_effective_settings=lambda: settings, message_store=store)

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.text = '{"id":"1","event":"message","message":"Msg A"}\n'

    with patch("alarm_dashboard.ntfy_client.requests.get", return_value=mock_resp):
        poller._poll_once()

    assert poller._last_topic_url == "https://ntfy.sh/topic-a"
    first_poll_time = poller._last_poll_time

    # Change the URL
    settings["ntfy_topic_url"] = "https://ntfy.sh/topic-b"
    mock_resp.text = '{"id":"2","event":"message","message":"Msg B"}\n'

    with patch("alarm_dashboard.ntfy_client.requests.get", return_value=mock_resp):
        poller._poll_once()

    # Should have reset and used the new URL
    assert poller._last_topic_url == "https://ntfy.sh/topic-b"


def test_ntfy_poller_deletes_message_on_message_delete_event():
    store = MessageStore()
    settings = _make_settings(topic_url="https://ntfy.sh/test")
    poller = NtfyPoller(get_effective_settings=lambda: settings, message_store=store)

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.text = (
        '{"id":"abc","event":"message","message":"Zu löschen"}\n'
        '{"event":"message_delete","sequence_id":"abc"}\n'
    )

    with patch("alarm_dashboard.ntfy_client.requests.get", return_value=mock_resp):
        poller._poll_once()

    assert store.get_active() == []


def test_ntfy_poller_deletes_message_on_deleted_flag_event():
    store = MessageStore()
    settings = _make_settings(topic_url="https://ntfy.sh/test")
    poller = NtfyPoller(get_effective_settings=lambda: settings, message_store=store)

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.text = (
        '{"id":"abc","event":"message","message":"Zu löschen"}\n'
        '{"id":"abc","event":"message","deleted":true}\n'
    )

    with patch("alarm_dashboard.ntfy_client.requests.get", return_value=mock_resp):
        poller._poll_once()

    assert store.get_active() == []
