"""Tests for the IMAP polling helper."""

from __future__ import annotations

import imaplib
import ssl
from typing import List, Tuple

import pytest

from alarm_dashboard.config import MailConfig
from alarm_dashboard.mail_checker import AlarmMailFetcher


class DummyIMAPServer:
    """Minimal IMAP server stub used for testing."""

    def __init__(self) -> None:
        self._encoding = "ASCII"
        self.login_calls: List[Tuple[str, str]] = []
        self.logout_called = False

    # The signature follows ``imaplib.IMAP4.login``
    def login(self, username: str, password: str) -> None:  # pragma: no cover - exercised indirectly
        self.login_calls.append((username, password))
        if self._encoding != "utf-8":
            raise imaplib.IMAP4.error("encoding not updated")

    def select(self, _mailbox: str) -> Tuple[str, List[bytes]]:
        return "OK", [b""]

    def uid(self, *_args: object) -> Tuple[str, List[bytes]]:
        return "OK", [b""]

    def logout(self) -> None:
        self.logout_called = True


@pytest.mark.parametrize("use_ssl", [True, False])
def test_poll_uses_utf8_encoding(monkeypatch: pytest.MonkeyPatch, use_ssl: bool) -> None:
    """The fetcher forces UTF-8 before authenticating to preserve credentials."""

    dummy_server = DummyIMAPServer()

    def fake_imap_ssl(_host: str, _port: int, ssl_context=None) -> DummyIMAPServer:  # type: ignore[override]
        return dummy_server

    def fake_imap(_host: str, _port: int) -> DummyIMAPServer:  # type: ignore[override]
        return dummy_server

    if use_ssl:
        monkeypatch.setattr("imaplib.IMAP4_SSL", fake_imap_ssl)
    else:
        monkeypatch.setattr("imaplib.IMAP4", fake_imap)

    # Ensure we don't require a real SSL context when testing the SSL path.
    monkeypatch.setattr(ssl, "create_default_context", lambda: None)

    config = MailConfig(
        host="imap.example.com",
        username="alarm",
        password="pässword",
        port=993 if use_ssl else 143,
        use_ssl=use_ssl,
    )

    fetcher = AlarmMailFetcher(config, callback=lambda _raw: None, poll_interval=0)

    # ``_poll_once`` raises if the encoding is not adapted.
    fetcher._poll_once()

    assert dummy_server.logout_called is True
    assert dummy_server.login_calls == [("alarm", "pässword")]
