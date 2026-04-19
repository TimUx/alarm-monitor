"""Optional background poller for ntfy.sh topics.

The poller runs as a permanent daemon thread.  Its topic URL, poll interval,
and default message TTL are read from the effective application settings on
every poll cycle, so changes made through the Settings UI take effect
immediately without requiring a restart.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Optional

import requests

from .message_store import MessageStore

LOGGER = logging.getLogger(__name__)

_DEFAULT_POLL_INTERVAL = 60
_DEFAULT_TTL_MINUTES = 60
_TRUTHY_DELETE_VALUES = {True, 1, "1", "true", "True", "yes", "on"}


class NtfyPoller:
    """Background thread that polls an ntfy.sh topic for new messages.

    The topic URL, poll interval (in seconds) and default message TTL (in
    minutes) are retrieved on every iteration via the ``get_effective_settings``
    callable so that they can be changed at run-time through the Settings UI.
    """

    def __init__(
        self,
        get_effective_settings: Callable[[], Dict],
        message_store: MessageStore,
        on_message: Optional[Callable[[], None]] = None,
    ) -> None:
        """Initialise the poller.

        Args:
            get_effective_settings: Zero-argument callable that returns the
                current effective settings dict.  The poller reads
                ``ntfy_topic_url``, ``ntfy_poll_interval``, and
                ``message_default_ttl_minutes`` from this dict on each cycle.
            message_store: Destination store for incoming messages.
            on_message: Optional callback invoked after a new message is stored.
                        Useful for triggering SSE notifications.
        """
        self._get_effective_settings = get_effective_settings
        self._message_store = message_store
        self._on_message = on_message
        self._last_poll_time: Optional[int] = None
        self._last_topic_url: Optional[str] = None
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
        LOGGER.info("ntfy poller thread started")

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
            settings = self._get_effective_settings()
            interval = max(10, int(settings.get("ntfy_poll_interval") or _DEFAULT_POLL_INTERVAL))
            self._stop_event.wait(interval)

    def _poll_once(self) -> None:
        """Fetch messages from ntfy since the last poll timestamp.

        If no topic URL is configured the method returns immediately without
        making any network requests.
        """
        settings = self._get_effective_settings()
        topic_url = (settings.get("ntfy_topic_url") or "").strip()
        if not topic_url:
            return  # Not configured – skip this cycle

        topic_url = topic_url.rstrip("/")

        # Reset history if the topic URL has changed to avoid missing messages
        if topic_url != self._last_topic_url:
            LOGGER.info("ntfy topic URL changed to: %s", topic_url)
            self._last_poll_time = None
            self._last_topic_url = topic_url

        default_ttl_minutes = max(
            1, int(settings.get("message_default_ttl_minutes") or _DEFAULT_TTL_MINUTES)
        )
        poll_interval = max(10, int(settings.get("ntfy_poll_interval") or _DEFAULT_POLL_INTERVAL))

        now = int(time.time())
        # On the very first poll look back one interval so recent messages
        # from just before start-up are not missed.
        since = self._last_poll_time if self._last_poll_time is not None else now - poll_interval

        url = f"{topic_url}/json"
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

            event_type = str(event.get("event") or "")
            if event_type not in {"message", "message_delete", "message_clear"}:
                continue

            source_id = self._resolve_source_id(event)

            if event_type in {"message_delete", "message_clear"}:
                if source_id and self._message_store.delete_by_source_id(source_id):
                    LOGGER.info("Removed ntfy message by source_id=%s", source_id)
                    if self._on_message:
                        try:
                            self._on_message()
                        except Exception:
                            LOGGER.warning("Error in on_message callback", exc_info=True)
                continue

            if self._is_deleted_message_event(event):
                if source_id and self._message_store.delete_by_source_id(source_id):
                    LOGGER.info("Removed ntfy message by delete-flag source_id=%s", source_id)
                    if self._on_message:
                        try:
                            self._on_message()
                        except Exception:
                            LOGGER.warning("Error in on_message callback", exc_info=True)
                continue

            text = (event.get("message") or "").strip()
            if not text:
                continue

            expires_at = self._resolve_expires(event, default_ttl_minutes)
            result = self._message_store.add_with_absolute_expiry(
                text, expires_at, source_id=source_id, on_stored=self._on_message
            )
            if result:
                LOGGER.info("New ntfy message stored (%.80s)", text)

    @staticmethod
    def _resolve_expires(event: dict, default_ttl_minutes: int) -> datetime:
        """Determine the expiry time for a ntfy message.

        Uses the ntfy ``expires`` field (unix timestamp) when present.
        Falls back to ``default_ttl_minutes`` from now when the field is
        absent or invalid – which is the common case when messages are sent
        via the ntfy browser UI or the standard app without an explicit TTL.
        """
        expires_unix = event.get("expires")
        if expires_unix is not None:
            try:
                return datetime.fromtimestamp(float(expires_unix), tz=timezone.utc)
            except (TypeError, ValueError, OSError):
                pass
        return datetime.now(timezone.utc) + timedelta(minutes=default_ttl_minutes)

    @staticmethod
    def _resolve_source_id(event: dict) -> Optional[str]:
        """Resolve a stable source ID for linking updates/deletes to stored messages."""
        for key in ("sequence_id", "id"):
            value = (event.get(key) or "").strip()
            if value:
                return value
        return None

    @staticmethod
    def _is_deleted_message_event(event: dict) -> bool:
        """Return True when a message event carries an explicit delete marker."""
        deleted_flag = event.get("deleted")
        return deleted_flag in _TRUTHY_DELETE_VALUES


def create_ntfy_poller(
    get_effective_settings: Callable[[], Dict],
    message_store: MessageStore,
    on_message: Optional[Callable[[], None]] = None,
) -> "NtfyPoller":
    """Return a configured :class:`NtfyPoller`.

    The poller is always created (even if no topic URL is configured yet) so
    that it picks up a URL configured later through the Settings UI without
    requiring a restart.
    """
    return NtfyPoller(
        get_effective_settings=get_effective_settings,
        message_store=message_store,
        on_message=on_message,
    )


__all__ = ["NtfyPoller", "create_ntfy_poller"]
