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
