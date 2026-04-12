"""Optional background poller for ntfy.sh topics.

When an ntfy topic URL is configured the poller runs as a daemon thread and
periodically fetches new messages from the topic, storing them in the
:class:`~alarm_dashboard.message_store.MessageStore`.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import requests

from .message_store import MessageStore

LOGGER = logging.getLogger(__name__)


class NtfyPoller:
    """Background thread that polls an ntfy.sh topic for new messages."""

    def __init__(
        self,
        topic_url: str,
        message_store: MessageStore,
        poll_interval: int = 60,
        on_message: Optional[Callable[[], None]] = None,
    ) -> None:
        """Initialise the poller.

        Args:
            topic_url: Full URL of the ntfy topic (e.g. ``https://ntfy.sh/my-topic``).
            message_store: Destination store for incoming messages.
            poll_interval: Seconds between polls (default: 60).
            on_message: Optional callback invoked after a new message is stored.
                        Useful for triggering SSE notifications.
        """
        self._topic_url = topic_url.rstrip("/")
        self._message_store = message_store
        self._poll_interval = max(10, poll_interval)
        self._on_message = on_message
        self._last_poll_time: Optional[int] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background polling thread (idempotent)."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="ntfy-poller"
        )
        self._thread.start()
        LOGGER.info("ntfy poller started for topic: %s", self._topic_url)

    def stop(self) -> None:
        """Signal the polling thread to stop."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Internal polling loop
    # ------------------------------------------------------------------

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._poll_once()
            except Exception:
                LOGGER.error("Unexpected error in ntfy poller", exc_info=True)
            self._stop_event.wait(self._poll_interval)

    def _poll_once(self) -> None:
        """Fetch messages from ntfy since the last poll timestamp."""
        now = int(time.time())
        # On the very first poll look back one interval so recent messages are
        # not missed.
        since = self._last_poll_time if self._last_poll_time is not None else now - self._poll_interval

        url = f"{self._topic_url}/json"
        params: dict = {"poll": "1", "since": str(since)}

        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            LOGGER.warning("ntfy poll request failed: %s", exc)
            return

        self._last_poll_time = now

        # ntfy returns newline-delimited JSON (one object per line)
        for line in response.text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except Exception:
                continue

            if event.get("event") != "message":
                continue

            text = (event.get("message") or "").strip()
            if not text:
                continue

            expires_at = self._parse_ntfy_expires(event)
            result = self._message_store.add_with_absolute_expiry(
                text, expires_at, on_stored=self._on_message
            )
            if result:
                LOGGER.info("New ntfy message stored (%.80s)", text)

    @staticmethod
    def _parse_ntfy_expires(event: dict) -> datetime:
        """Parse the ntfy ``expires`` field (unix timestamp) into a datetime.

        Falls back to 60 minutes from now when the field is absent or invalid.
        """
        expires_unix = event.get("expires")
        if expires_unix is not None:
            try:
                return datetime.fromtimestamp(float(expires_unix), tz=timezone.utc)
            except (TypeError, ValueError, OSError):
                pass
        return datetime.now(timezone.utc) + timedelta(minutes=60)


def create_ntfy_poller(
    topic_url: Optional[str],
    message_store: MessageStore,
    poll_interval: int = 60,
    on_message: Optional[Callable[[], None]] = None,
) -> Optional[NtfyPoller]:
    """Return a configured :class:`NtfyPoller`, or *None* when no URL is given."""
    if not topic_url:
        return None
    return NtfyPoller(
        topic_url=topic_url,
        message_store=message_store,
        poll_interval=poll_interval,
        on_message=on_message,
    )


__all__ = ["NtfyPoller", "create_ntfy_poller"]
