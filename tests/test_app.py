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

    def start(self) -> None:
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


def test_create_app_registers_fetcher_with_available_hook(
    monkeypatch: pytest.MonkeyPatch, dummy_fetcher: List[_DummyFetcher]
) -> None:
    """When lifecycle hooks are available the fetcher should register lazily."""

    callbacks: List[Callable[[], None]] = []

    def fake_before_serving(self, func: Callable[[], None]) -> None:
        callbacks.append(func)

    # Ensure only the synthetic hook is available during registration.
    monkeypatch.setattr(app_module.Flask, "before_request", None, raising=False)
    monkeypatch.setattr(app_module.Flask, "before_app_serving", None, raising=False)
    monkeypatch.setattr(app_module.Flask, "before_first_request", None, raising=False)
    monkeypatch.setattr(app_module.Flask, "before_app_first_request", None, raising=False)
    monkeypatch.setattr(app_module.Flask, "before_serving", fake_before_serving, raising=False)

    config = AppConfig(
        mail=MailConfig(host="imap.example", username="user", password="secret"),
    )

    flask_app = app_module.create_app(config)

    assert flask_app.config["MAIL_FETCHER"] is not None
    assert len(dummy_fetcher) == 1
    assert flask_app.config["MAIL_FETCHER"] is dummy_fetcher[0]
    # The fetcher should not start until the hook is triggered manually.
    assert dummy_fetcher[0].started == 0
    assert len(callbacks) == 1

    callbacks[0]()
    assert dummy_fetcher[0].started == 1


def test_create_app_starts_fetcher_when_no_hooks_available(
    monkeypatch: pytest.MonkeyPatch, dummy_fetcher: List[_DummyFetcher]
) -> None:
    """If Flask exposes no lifecycle hooks the fetcher starts immediately."""

    monkeypatch.setattr(app_module.Flask, "before_serving", None, raising=False)
    monkeypatch.setattr(app_module.Flask, "before_app_serving", None, raising=False)
    monkeypatch.setattr(app_module.Flask, "before_first_request", None, raising=False)
    monkeypatch.setattr(app_module.Flask, "before_app_first_request", None, raising=False)
    monkeypatch.setattr(app_module.Flask, "before_request", None, raising=False)

    config = AppConfig(
        mail=MailConfig(host="imap.example", username="user", password="secret"),
    )

    flask_app = app_module.create_app(config)

    assert flask_app.config["MAIL_FETCHER"] is not None
    assert len(dummy_fetcher) == 1
    assert flask_app.config["MAIL_FETCHER"] is dummy_fetcher[0]
    assert dummy_fetcher[0].started == 1
