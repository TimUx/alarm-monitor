"""HDMI-CEC display control for connected monitors and TVs.

Uses ``cec-client`` (from cec-utils / libcec) to wake displays on alarm and
send them to standby after a configurable idle period.  Fixed weekly schedules
keep the display powered on during defined windows (e.g. training nights).
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

LOGGER = logging.getLogger(__name__)

_DEFAULT_CLIENT_PATH = "/usr/bin/cec-client"
_DEFAULT_IDLE_STANDBY_MINUTES = 30
_DEFAULT_DEVICE_ADDRESS = 0
_POLL_INTERVAL_SECONDS = 30

_WEEKDAY_LABELS = (
    "Montag",
    "Dienstag",
    "Mittwoch",
    "Donnerstag",
    "Freitag",
    "Samstag",
    "Sonntag",
)


def _time_to_minutes(value: str) -> Optional[int]:
    """Parse ``HH:MM`` into minutes since midnight."""
    if not value or ":" not in value:
        return None
    parts = value.strip().split(":", 1)
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
    except (TypeError, ValueError):
        return None
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        return None
    return hours * 60 + minutes


def is_in_schedule_window(schedules: List[Dict[str, Any]], now_local: datetime) -> bool:
    """Return True when *now_local* falls inside any enabled schedule window."""
    if not schedules:
        return False

    weekday = now_local.weekday()
    now_minutes = now_local.hour * 60 + now_local.minute

    for entry in schedules:
        if not entry.get("enabled", True):
            continue
        try:
            entry_weekday = int(entry.get("weekday", -1))
        except (TypeError, ValueError):
            continue
        if entry_weekday != weekday:
            continue

        start = _time_to_minutes(str(entry.get("start_time") or ""))
        end = _time_to_minutes(str(entry.get("end_time") or ""))
        if start is None or end is None:
            continue

        if start <= end:
            if start <= now_minutes <= end:
                return True
        elif now_minutes >= start or now_minutes <= end:
            return True

    return False


def normalize_schedules(raw: Any) -> List[Dict[str, Any]]:
    """Validate and normalise schedule entries from settings storage."""
    if not isinstance(raw, list):
        return []

    normalised: List[Dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            weekday = int(entry.get("weekday", -1))
        except (TypeError, ValueError):
            continue
        if weekday not in range(7):
            continue

        start_time = str(entry.get("start_time") or "").strip()
        end_time = str(entry.get("end_time") or "").strip()
        if _time_to_minutes(start_time) is None or _time_to_minutes(end_time) is None:
            continue

        label = str(entry.get("label") or "").strip()
        normalised.append(
            {
                "enabled": bool(entry.get("enabled", True)),
                "weekday": weekday,
                "start_time": start_time,
                "end_time": end_time,
                "label": label,
            }
        )
    return normalised


def get_hdmi_cec_settings(effective_settings: Dict[str, Any]) -> Dict[str, Any]:
    """Extract normalised HDMI-CEC settings from the effective settings dict."""
    client_path = (
        str(effective_settings.get("hdmi_cec_client_path") or _DEFAULT_CLIENT_PATH).strip()
        or _DEFAULT_CLIENT_PATH
    )
    try:
        device_address = int(effective_settings.get("hdmi_cec_device_address", _DEFAULT_DEVICE_ADDRESS))
    except (TypeError, ValueError):
        device_address = _DEFAULT_DEVICE_ADDRESS
    device_address = max(0, min(15, device_address))

    try:
        idle_minutes = int(
            effective_settings.get("hdmi_cec_idle_standby_minutes", _DEFAULT_IDLE_STANDBY_MINUTES)
        )
    except (TypeError, ValueError):
        idle_minutes = _DEFAULT_IDLE_STANDBY_MINUTES
    idle_minutes = max(1, idle_minutes)

    return {
        "enabled": bool(effective_settings.get("hdmi_cec_enabled")),
        "client_path": client_path,
        "device_address": device_address,
        "idle_standby_minutes": idle_minutes,
        "wake_on_alarm": bool(effective_settings.get("hdmi_cec_wake_on_alarm", True)),
        "standby_on_idle": bool(effective_settings.get("hdmi_cec_standby_on_idle", True)),
        "schedules": normalize_schedules(effective_settings.get("hdmi_cec_schedules")),
    }


def is_cec_client_available(client_path: str) -> bool:
    """Return True when *client_path* exists and is executable."""
    return bool(client_path) and os.path.isfile(client_path) and os.access(client_path, os.X_OK)


class CecController:
    """Thin wrapper around ``cec-client`` for power on / standby commands."""

    def __init__(self, client_path: str, device_address: int = _DEFAULT_DEVICE_ADDRESS) -> None:
        self._client_path = client_path
        self._device_address = max(0, min(15, device_address))
        self._lock = threading.Lock()
        self.last_action: Optional[str] = None
        self.last_output: Optional[str] = None
        self.last_success: Optional[bool] = None

    @property
    def client_path(self) -> str:
        return self._client_path

    @property
    def device_address(self) -> int:
        return self._device_address

    def configure(self, client_path: str, device_address: int) -> None:
        self._client_path = client_path or _DEFAULT_CLIENT_PATH
        self._device_address = max(0, min(15, device_address))

    def available(self) -> bool:
        return is_cec_client_available(self._client_path)

    def wake(self) -> bool:
        return self._send_command(f"on {self._device_address}")

    def standby(self) -> bool:
        return self._send_command(f"standby {self._device_address}")

    def _send_command(self, command: str) -> bool:
        if not self.available():
            LOGGER.warning("cec-client not available at %s", self._client_path)
            self.last_action = command
            self.last_output = "cec-client not available"
            self.last_success = False
            return False

        with self._lock:
            try:
                result = subprocess.run(
                    [self._client_path, "-s", "-d", "1"],
                    input=f"{command}\n",
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                output = ((result.stdout or "") + (result.stderr or "")).strip()
                success = result.returncode == 0
            except (subprocess.TimeoutExpired, OSError) as exc:
                output = str(exc)
                success = False

            self.last_action = command
            self.last_output = output
            self.last_success = success
            if success:
                LOGGER.info("CEC command succeeded: %s", command)
            else:
                LOGGER.warning("CEC command failed (%s): %s", command, output)
            return success


def _alarm_display_mode(
    alarm_payload: Optional[Dict[str, Any]],
    display_duration_minutes: int,
) -> str:
    """Return ``alarm`` or ``idle`` using the same rules as ``GET /api/alarm``."""
    if alarm_payload is None:
        return "idle"

    received_at = alarm_payload.get("received_at")
    if isinstance(received_at, str):
        try:
            received_at = datetime.fromisoformat(received_at)
        except ValueError:
            received_at = None

    if not isinstance(received_at, datetime):
        return "idle"

    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)

    duration = max(1, display_duration_minutes)
    if received_at + timedelta(minutes=duration) < datetime.now(timezone.utc):
        return "idle"
    return "alarm"


class CecDisplayWatcher:
    """Background thread that applies standby / schedule rules for HDMI-CEC."""

    def __init__(
        self,
        get_effective_settings: Callable[[], Dict[str, Any]],
        get_alarm_payload: Callable[[], Optional[Dict[str, Any]]],
        get_display_duration_minutes: Callable[[], int],
        get_timezone: Callable[[], str],
        controller: CecController,
    ) -> None:
        self._get_effective_settings = get_effective_settings
        self._get_alarm_payload = get_alarm_payload
        self._get_display_duration_minutes = get_display_duration_minutes
        self._get_timezone = get_timezone
        self._controller = controller
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._display_mode = "idle"
        self._idle_since: Optional[datetime] = None
        self._was_in_schedule = False
        self._standby_sent_for_idle = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="cec-display-watcher",
        )
        self._thread.start()
        LOGGER.info("CEC display watcher thread started")

    def stop(self) -> None:
        self._stop_event.set()

    def handle_alarm_stored(self) -> None:
        """Wake the display immediately when a new alarm is stored."""
        settings = get_hdmi_cec_settings(self._get_effective_settings())
        if not settings["enabled"] or not settings["wake_on_alarm"]:
            return
        self._controller.configure(settings["client_path"], settings["device_address"])
        if self._controller.wake():
            self._standby_sent_for_idle = False
            self._display_mode = "alarm"
            self._idle_since = None

    def _local_now(self) -> datetime:
        tz_name = self._get_timezone() or "UTC"
        try:
            return datetime.now(ZoneInfo(tz_name))
        except Exception:
            return datetime.now()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                LOGGER.error("Unexpected error in CEC display watcher", exc_info=True)
            self._stop_event.wait(_POLL_INTERVAL_SECONDS)

    def _tick(self) -> None:
        settings = get_hdmi_cec_settings(self._get_effective_settings())
        if not settings["enabled"]:
            self._display_mode = "idle"
            self._idle_since = None
            self._was_in_schedule = False
            self._standby_sent_for_idle = False
            return

        self._controller.configure(settings["client_path"], settings["device_address"])
        if not self._controller.available():
            return

        now_utc = datetime.now(timezone.utc)
        now_local = self._local_now()
        in_schedule = is_in_schedule_window(settings["schedules"], now_local)

        alarm_payload = self._get_alarm_payload()
        current_mode = _alarm_display_mode(
            alarm_payload,
            self._get_display_duration_minutes(),
        )
        previous_mode = self._display_mode

        if in_schedule and not self._was_in_schedule:
            if self._controller.wake():
                self._standby_sent_for_idle = False

        if self._was_in_schedule and not in_schedule and current_mode == "idle":
            self._idle_since = now_utc
            self._standby_sent_for_idle = False

        if current_mode == "alarm":
            self._idle_since = None
            self._standby_sent_for_idle = False
        elif current_mode == "idle":
            if in_schedule:
                if self._controller.wake():
                    self._standby_sent_for_idle = False
            else:
                if self._idle_since is None or previous_mode == "alarm":
                    self._idle_since = now_utc
                    self._standby_sent_for_idle = False

                if (
                    settings["standby_on_idle"]
                    and self._idle_since is not None
                    and not self._standby_sent_for_idle
                ):
                    idle_deadline = self._idle_since + timedelta(
                        minutes=settings["idle_standby_minutes"]
                    )
                    if now_utc >= idle_deadline:
                        if self._controller.standby():
                            self._standby_sent_for_idle = True

        self._display_mode = current_mode
        self._was_in_schedule = in_schedule


def create_cec_display_watcher(
    get_effective_settings: Callable[[], Dict[str, Any]],
    get_alarm_payload: Callable[[], Optional[Dict[str, Any]]],
    get_display_duration_minutes: Callable[[], int],
    get_timezone: Callable[[], str],
) -> CecDisplayWatcher:
    """Create a configured :class:`CecDisplayWatcher` (always started in ``create_app``)."""
    controller = CecController(_DEFAULT_CLIENT_PATH)
    return CecDisplayWatcher(
        get_effective_settings=get_effective_settings,
        get_alarm_payload=get_alarm_payload,
        get_display_duration_minutes=get_display_duration_minutes,
        get_timezone=get_timezone,
        controller=controller,
    )


__all__ = [
    "CecController",
    "CecDisplayWatcher",
    "create_cec_display_watcher",
    "get_hdmi_cec_settings",
    "is_cec_client_available",
    "is_in_schedule_window",
    "normalize_schedules",
    "_WEEKDAY_LABELS",
]
