"""Tests for the Flask application factory."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, List

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from alarm_dashboard.config import AppConfig, MailConfig
from alarm_dashboard import app as app_module


class _DummyFetcher:
    """Simple stand-in for ``AlarmMailFetcher`` used in tests."""

    def __init__(self, config: MailConfig, callback: Callable[[bytes], None], poll_interval: int) -> None:
        self.config = config
        self.callback = callback
        self.poll_interval = poll_interval
        self.started = 0
        self.stopped = 0
        self.raise_on_start: Exception | None = None

    def start(self) -> None:
        if self.raise_on_start is not None:
            raise self.raise_on_start
        self.started += 1

    def stop(self) -> None:  # pragma: no cover - defensive
        self.stopped += 1


@pytest.fixture
def dummy_fetcher(monkeypatch: pytest.MonkeyPatch) -> List[_DummyFetcher]:
    """Patch the mail fetcher with a dummy implementation and track instances."""

    created: List[_DummyFetcher] = []

    def _factory(config: MailConfig, callback: Callable[[bytes], None], poll_interval: int) -> _DummyFetcher:
        instance = _DummyFetcher(config, callback, poll_interval)
        created.append(instance)
        return instance

    monkeypatch.setattr(app_module, "AlarmMailFetcher", _factory)
    return created


def test_create_app_without_mail_skips_fetcher(monkeypatch: pytest.MonkeyPatch) -> None:
    """The factory should not construct a mail fetcher when configuration is absent."""

    config = AppConfig(mail=None)

    def _fail_factory(*_args, **_kwargs):
        raise AssertionError("Fetcher should not be constructed when mail config is missing")

    monkeypatch.setattr(app_module, "AlarmMailFetcher", _fail_factory)

    flask_app = app_module.create_app(config)

    assert flask_app.config["MAIL_FETCHER"] is None


def test_create_app_starts_fetcher_immediately(dummy_fetcher: List[_DummyFetcher]) -> None:
    """The mail fetcher should be constructed and started during app creation."""

    config = AppConfig(
        mail=MailConfig(host="imap.example", username="user", password="secret"),
    )

    flask_app = app_module.create_app(config)

    assert len(dummy_fetcher) == 1
    assert flask_app.config["MAIL_FETCHER"] is dummy_fetcher[0]
    assert dummy_fetcher[0].started == 1


def test_create_app_stops_fetcher_on_teardown(dummy_fetcher: List[_DummyFetcher]) -> None:
    """The fetcher should be stopped when the application context tears down."""

    config = AppConfig(
        mail=MailConfig(host="imap.example", username="user", password="secret"),
    )

    flask_app = app_module.create_app(config)

    with flask_app.app_context():
        assert dummy_fetcher[0].stopped == 0

    assert dummy_fetcher[0].stopped == 0

    cleanup = flask_app.config.get("MAIL_FETCHER_CLEANUP")
    assert callable(cleanup)

    cleanup()

    assert dummy_fetcher[0].stopped == 1


def test_fetcher_continues_running_after_request(dummy_fetcher: List[_DummyFetcher]) -> None:
    """Issuing a request should not stop the background mail fetcher."""

    config = AppConfig(
        mail=MailConfig(host="imap.example", username="user", password="secret"),
    )

    flask_app = app_module.create_app(config)

    with flask_app.test_client() as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert flask_app.config["MAIL_FETCHER"] is dummy_fetcher[0]
    assert dummy_fetcher[0].stopped == 0


def test_create_app_logs_and_discards_fetcher_when_start_fails(
    monkeypatch: pytest.MonkeyPatch, dummy_fetcher: List[_DummyFetcher]
) -> None:
    """If starting the fetcher raises, the failure should be reported and ignored."""

    config = AppConfig(
        mail=MailConfig(host="imap.example", username="user", password="secret"),
    )

    def _factory(
        config: MailConfig, callback: Callable[[bytes], None], poll_interval: int
    ) -> _DummyFetcher:
        instance = _DummyFetcher(config, callback, poll_interval)
        instance.raise_on_start = RuntimeError("boom")
        dummy_fetcher.append(instance)
        return instance

    monkeypatch.setattr(app_module, "AlarmMailFetcher", _factory)

    flask_app = app_module.create_app(config)

    assert flask_app.config["MAIL_FETCHER"] is None
    assert dummy_fetcher[0].started == 0


def test_create_app_uses_instance_history_path() -> None:
    """A default history file should be created inside the instance folder."""

    config = AppConfig(mail=None, history_file=None)

    flask_app = app_module.create_app(config)

    store = flask_app.config["ALARM_STORE"]
    expected_path = Path(flask_app.instance_path) / "alarm_history.json"

    assert store._persistence_path == expected_path  # type: ignore[attr-defined]
    assert config.history_file == str(expected_path)


def test_history_persists_between_app_instances(tmp_path) -> None:
    """Entries written by one app instance should load in subsequent ones."""

    history_file = tmp_path / "history.json"
    config = AppConfig(mail=None, history_file=str(history_file))

    first_app = app_module.create_app(config)
    first_store = first_app.config["ALARM_STORE"]
    first_store.update({"alarm": {"keyword": "Persist"}})

    second_app = app_module.create_app(config)
    second_store = second_app.config["ALARM_STORE"]

    history = second_store.history()
    assert history
    assert history[0]["alarm"]["keyword"] == "Persist"


def test_process_email_ignores_duplicates_by_incident_number(
    tmp_path: Path, dummy_fetcher: List[_DummyFetcher]
) -> None:
    """The app should ignore alarms with duplicate incident numbers."""
    import textwrap

    history_path = tmp_path / "history.json"
    config = AppConfig(
        mail=MailConfig(
            host="imap.example.com",
            port=993,
            use_ssl=True,
            username="user@example.com",
            password="secret",
            mailbox="INBOX",
            search_criteria="UNSEEN",
        ),
        poll_interval=60,
        history_file=str(history_path),
    )

    application = app_module.create_app(config)
    store = application.config["ALARM_STORE"]
    assert len(dummy_fetcher) == 1
    
    callback = dummy_fetcher[0].callback
    
    # First alarm with incident number 12345
    raw_email_1 = textwrap.dedent(
        """
        Subject: Alarm 1

        <INCIDENT>
          <ENR>12345</ENR>
          <STICHWORT>F3Y</STICHWORT>
          <EBEGINN>24.07.2026 18:42:11</EBEGINN>
        </INCIDENT>
        """
    ).lstrip().encode("utf-8")
    
    callback(raw_email_1)
    
    history = store.history()
    assert len(history) == 1
    assert history[0]["alarm"]["incident_number"] == "12345"
    
    # Second alarm with same incident number (should be ignored)
    raw_email_2 = textwrap.dedent(
        """
        Subject: Alarm 2 (Duplicate)

        <INCIDENT>
          <ENR>12345</ENR>
          <STICHWORT>F4Y</STICHWORT>
          <EBEGINN>24.07.2026 19:00:00</EBEGINN>
        </INCIDENT>
        """
    ).lstrip().encode("utf-8")
    
    callback(raw_email_2)
    
    # Should still have only one entry
    history = store.history()
    assert len(history) == 1
    assert history[0]["alarm"]["incident_number"] == "12345"
    # Should be the first one (not updated)
    assert history[0]["alarm"]["keyword_primary"] == "F3Y"
    
    # Third alarm with different incident number (should be added)
    raw_email_3 = textwrap.dedent(
        """
        Subject: Alarm 3

        <INCIDENT>
          <ENR>67890</ENR>
          <STICHWORT>F5Y</STICHWORT>
          <EBEGINN>24.07.2026 20:00:00</EBEGINN>
        </INCIDENT>
        """
    ).lstrip().encode("utf-8")
    
    callback(raw_email_3)
    
    # Should now have two entries
    history = store.history()
    assert len(history) == 2
    assert history[0]["alarm"]["incident_number"] == "67890"
    assert history[1]["alarm"]["incident_number"] == "12345"


def test_process_email_rejects_alarms_without_incident_number(
    tmp_path: Path, dummy_fetcher: List[_DummyFetcher]
) -> None:
    """The app should reject alarms without incident number (ENR)."""
    import textwrap

    history_path = tmp_path / "history.json"
    config = AppConfig(
        mail=MailConfig(
            host="imap.example.com",
            port=993,
            use_ssl=True,
            username="user@example.com",
            password="secret",
            mailbox="INBOX",
            search_criteria="UNSEEN",
        ),
        poll_interval=60,
        history_file=str(history_path),
    )

    application = app_module.create_app(config)
    store = application.config["ALARM_STORE"]
    assert len(dummy_fetcher) == 1
    
    callback = dummy_fetcher[0].callback
    
    # Alarm without incident number (should be rejected)
    raw_email = textwrap.dedent(
        """
        Subject: Alarm without ENR

        <INCIDENT>
          <STICHWORT>F3Y</STICHWORT>
          <EBEGINN>24.07.2026 18:42:11</EBEGINN>
        </INCIDENT>
        """
    ).lstrip().encode("utf-8")
    
    callback(raw_email)
    
    # Should have no entries
    history = store.history()
    assert len(history) == 0
    
    # Now send a valid alarm with incident number
    raw_email_valid = textwrap.dedent(
        """
        Subject: Valid Alarm

        <INCIDENT>
          <ENR>12345</ENR>
          <STICHWORT>F4Y</STICHWORT>
          <EBEGINN>24.07.2026 19:00:00</EBEGINN>
        </INCIDENT>
        """
    ).lstrip().encode("utf-8")
    
    callback(raw_email_valid)
    
    # Should now have one entry
    history = store.history()
    assert len(history) == 1
    assert history[0]["alarm"]["incident_number"] == "12345"


