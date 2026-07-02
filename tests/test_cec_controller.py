"""Tests for HDMI-CEC display control."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alarm_monitor.cec_controller import (
    CecController,
    CecDisplayWatcher,
    get_hdmi_cec_settings,
    is_in_schedule_window,
    normalize_schedules,
    _alarm_display_mode,
)


def test_normalize_schedules_filters_invalid_entries() -> None:
    raw = [
        {
            "enabled": True,
            "weekday": 1,
            "start_time": "18:45",
            "end_time": "21:30",
            "label": "Übungsdienst",
        },
        {"weekday": 9, "start_time": "10:00", "end_time": "11:00"},
        {"weekday": 2, "start_time": "bad", "end_time": "21:00"},
    ]
    result = normalize_schedules(raw)
    assert len(result) == 1
    assert result[0]["weekday"] == 1
    assert result[0]["label"] == "Übungsdienst"


def test_is_in_schedule_window_matches_weekday_and_time() -> None:
    schedules = normalize_schedules(
        [
            {
                "enabled": True,
                "weekday": 1,
                "start_time": "18:45",
                "end_time": "21:30",
                "label": "Übungsdienst",
            }
        ]
    )
    tuesday_evening = datetime(2026, 7, 7, 19, 0)  # Tuesday
    tuesday_afternoon = datetime(2026, 7, 7, 17, 0)
    wednesday_evening = datetime(2026, 7, 8, 19, 0)

    assert is_in_schedule_window(schedules, tuesday_evening) is True
    assert is_in_schedule_window(schedules, tuesday_afternoon) is False
    assert is_in_schedule_window(schedules, wednesday_evening) is False


def test_is_in_schedule_window_supports_overnight_span() -> None:
    schedules = normalize_schedules(
        [
            {
                "enabled": True,
                "weekday": 4,
                "start_time": "22:00",
                "end_time": "02:00",
                "label": "Nachtdienst",
            }
        ]
    )
    friday_late = datetime(2026, 7, 10, 23, 30)  # Friday
    saturday_early = datetime(2026, 7, 11, 1, 0)  # Saturday (different weekday)

    assert is_in_schedule_window(schedules, friday_late) is True
    assert is_in_schedule_window(schedules, saturday_early) is False


def test_get_hdmi_cec_settings_uses_defaults() -> None:
    settings = get_hdmi_cec_settings({})
    assert settings["enabled"] is False
    assert settings["client_path"] == "/usr/bin/cec-client"
    assert settings["device_address"] == 0
    assert settings["idle_standby_minutes"] == 30
    assert settings["wake_on_alarm"] is True
    assert settings["standby_on_idle"] is True


@patch("alarm_monitor.cec_controller.subprocess.run")
@patch("alarm_monitor.cec_controller.is_cec_client_available", return_value=True)
def test_cec_controller_wake_sends_on_command(_mock_available, mock_run) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
    controller = CecController("/usr/bin/cec-client", device_address=0)

    assert controller.wake() is True
    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["input"] == "on 0\n"


@patch("alarm_monitor.cec_controller.subprocess.run")
@patch("alarm_monitor.cec_controller.is_cec_client_available", return_value=True)
def test_cec_controller_standby_sends_standby_command(_mock_available, mock_run) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
    controller = CecController("/usr/bin/cec-client", device_address=0)

    assert controller.standby() is True
    assert mock_run.call_args.kwargs["input"] == "standby 0\n"


def test_alarm_display_mode_idle_after_duration() -> None:
    from datetime import timedelta, timezone

    received_at = datetime.now(timezone.utc) - timedelta(minutes=45)
    payload = {"received_at": received_at.isoformat()}
    assert _alarm_display_mode(payload, 30) == "idle"


def test_cec_watcher_standby_after_idle_timeout() -> None:
    from datetime import timedelta, timezone

    controller = CecController("/usr/bin/cec-client")
    controller.wake = MagicMock(return_value=True)  # type: ignore[method-assign]
    controller.standby = MagicMock(return_value=True)  # type: ignore[method-assign]
    controller.configure = MagicMock()  # type: ignore[method-assign]
    controller.available = MagicMock(return_value=True)  # type: ignore[method-assign]

    received_at = datetime.now(timezone.utc) - timedelta(minutes=45)
    alarm_payload = {"received_at": received_at.isoformat()}

    settings = {
        "hdmi_cec_enabled": True,
        "hdmi_cec_client_path": "/usr/bin/cec-client",
        "hdmi_cec_device_address": 0,
        "hdmi_cec_idle_standby_minutes": 5,
        "hdmi_cec_wake_on_alarm": True,
        "hdmi_cec_standby_on_idle": True,
        "hdmi_cec_schedules": [],
    }

    watcher = CecDisplayWatcher(
        get_effective_settings=lambda: settings,
        get_alarm_payload=lambda: alarm_payload,
        get_display_duration_minutes=lambda: 30,
        get_timezone=lambda: "UTC",
        controller=controller,
    )
    watcher._display_mode = "alarm"
    watcher._tick()
    assert watcher._display_mode == "idle"
    assert watcher._idle_since is not None

    watcher._idle_since = datetime.now(timezone.utc) - timedelta(minutes=10)
    watcher._tick()
    controller.standby.assert_called_once()


def test_cec_watcher_standby_after_restart_in_idle_mode() -> None:
    """After reboot the idle dashboard may show immediately – standby still applies."""
    from datetime import timedelta, timezone

    controller = CecController("/usr/bin/cec-client")
    controller.wake = MagicMock(return_value=True)  # type: ignore[method-assign]
    controller.standby = MagicMock(return_value=True)  # type: ignore[method-assign]
    controller.configure = MagicMock()  # type: ignore[method-assign]
    controller.available = MagicMock(return_value=True)  # type: ignore[method-assign]

    received_at = datetime.now(timezone.utc) - timedelta(minutes=45)
    alarm_payload = {"received_at": received_at.isoformat()}

    settings = {
        "hdmi_cec_enabled": True,
        "hdmi_cec_client_path": "/usr/bin/cec-client",
        "hdmi_cec_device_address": 0,
        "hdmi_cec_idle_standby_minutes": 5,
        "hdmi_cec_wake_on_alarm": True,
        "hdmi_cec_standby_on_idle": True,
        "hdmi_cec_schedules": [],
    }

    watcher = CecDisplayWatcher(
        get_effective_settings=lambda: settings,
        get_alarm_payload=lambda: alarm_payload,
        get_display_duration_minutes=lambda: 30,
        get_timezone=lambda: "UTC",
        controller=controller,
    )
    # Simulate fresh start: watcher has no memory of prior alarm display
    watcher._display_mode = "idle"
    watcher._idle_since = None
    watcher._tick()
    assert watcher._idle_since is not None

    watcher._idle_since = datetime.now(timezone.utc) - timedelta(minutes=10)
    watcher._tick()
    controller.standby.assert_called_once()


def test_cec_watcher_keeps_display_on_during_schedule() -> None:
    from datetime import timedelta, timezone

    controller = CecController("/usr/bin/cec-client")
    controller.wake = MagicMock(return_value=True)  # type: ignore[method-assign]
    controller.standby = MagicMock(return_value=True)  # type: ignore[method-assign]
    controller.configure = MagicMock()  # type: ignore[method-assign]
    controller.available = MagicMock(return_value=True)  # type: ignore[method-assign]

    received_at = datetime.now(timezone.utc) - timedelta(minutes=45)
    alarm_payload = {"received_at": received_at.isoformat()}
    tuesday_evening = datetime(2026, 7, 7, 19, 0)

    settings = {
        "hdmi_cec_enabled": True,
        "hdmi_cec_client_path": "/usr/bin/cec-client",
        "hdmi_cec_device_address": 0,
        "hdmi_cec_idle_standby_minutes": 5,
        "hdmi_cec_wake_on_alarm": True,
        "hdmi_cec_standby_on_idle": True,
        "hdmi_cec_schedules": [
            {
                "enabled": True,
                "weekday": 1,
                "start_time": "18:45",
                "end_time": "21:30",
                "label": "Übungsdienst",
            }
        ],
    }

    watcher = CecDisplayWatcher(
        get_effective_settings=lambda: settings,
        get_alarm_payload=lambda: alarm_payload,
        get_display_duration_minutes=lambda: 30,
        get_timezone=lambda: "Europe/Berlin",
        controller=controller,
    )
    watcher._display_mode = "alarm"
    watcher._local_now = MagicMock(return_value=tuesday_evening)  # type: ignore[method-assign]
    watcher._tick()
    watcher._idle_since = datetime.now(timezone.utc) - timedelta(minutes=10)
    watcher._tick()

    controller.standby.assert_not_called()
    assert controller.wake.call_count >= 1
