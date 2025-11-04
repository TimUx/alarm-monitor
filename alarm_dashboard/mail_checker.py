"""Background task for polling the IMAP server for alarm emails."""

from __future__ import annotations

import imaplib
import logging
import ssl
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from .config import MailConfig

LOGGER = logging.getLogger(__name__)


@dataclass
class MailState:
    """Track mail state across polling cycles."""

    last_uid: Optional[int] = None


class AlarmMailFetcher:
    """Poll the IMAP mailbox and invoke a callback when new messages arrive."""

    def __init__(
        self,
        config: MailConfig,
        callback: Callable[[bytes], None],
        poll_interval: int = 60,
    ) -> None:
        self.config = config
        self.callback = callback
        self.poll_interval = poll_interval
        self._state = MailState()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._poll_once()
            except Exception as exc:  # pragma: no cover - safety net
                LOGGER.exception("Error while polling mailbox: %s", exc)
            time.sleep(self.poll_interval)

    # pylint: disable=too-many-locals
    def _poll_once(self) -> None:
        config = self.config
        LOGGER.debug("Connecting to IMAP server %s", config.host)
        if config.use_ssl:
            context = ssl.create_default_context()
            server = imaplib.IMAP4_SSL(config.host, config.port, ssl_context=context)
        else:
            server = imaplib.IMAP4(config.host, config.port)

        try:
            server.login(config.username, config.password)
            server.select(config.mailbox)
            LOGGER.debug("Searching for messages with criteria: %s", config.search_criteria)
            typ, data = server.uid("SEARCH", None, config.search_criteria)
            if typ != "OK":
                LOGGER.warning("IMAP search failed with response: %s", typ)
                return

            uids = [int(uid) for uid in data[0].split() if uid]
            for uid in sorted(uids):
                if self._state.last_uid is not None and uid <= self._state.last_uid:
                    continue
                LOGGER.info("Fetching new message UID %s", uid)
                result, message_data = server.uid("FETCH", str(uid), "(RFC822)")
                if result != "OK":
                    LOGGER.warning("Failed to fetch message UID %s", uid)
                    continue
                if not message_data or not message_data[0]:
                    continue
                raw_email = message_data[0][1]
                self.callback(raw_email)
                self._state.last_uid = uid
        finally:
            try:
                server.logout()
            except imaplib.IMAP4.error:
                LOGGER.debug("Failed to cleanly log out from IMAP server")


__all__ = ["AlarmMailFetcher"]
