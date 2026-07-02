import importlib
import os
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alarm_monitor import config


@contextmanager
def _temp_env(**values):
    original = {key: os.environ.get(key) for key in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _clear_alarm_env():
    for name in list(os.environ):
        if name.startswith(config.ENV_PREFIX) or name.startswith(config.LEGACY_ENV_PREFIX):
            del os.environ[name]


def test_load_config_without_api_key():
    _clear_alarm_env()
    importlib.reload(config)

    app_config = config.load_config()

    assert app_config.api_key is None


def test_load_config_with_api_key():
    _clear_alarm_env()
    importlib.reload(config)

    with _temp_env(
        ALARM_MONITOR_API_KEY="test-api-key-123",
    ):
        app_config = config.load_config()

    assert app_config.api_key == "test-api-key-123"


def test_load_config_with_history_file(tmp_path):
    _clear_alarm_env()
    importlib.reload(config)

    history_file = "/app/instance/alarm_history.json"

    with _temp_env(ALARM_MONITOR_HISTORY_FILE=history_file):
        app_config = config.load_config()

    assert app_config.history_file == history_file


def test_load_config_sets_defaults_for_branding_and_version():
    _clear_alarm_env()
    importlib.reload(config)

    app_config = config.load_config()

    assert app_config.fire_department_name == "Alarm-Monitor"
    assert app_config.app_version == "dev-main"
    assert app_config.app_version_url.endswith("/releases")


def test_load_config_builds_release_url_from_version():
    _clear_alarm_env()
    importlib.reload(config)

    with _temp_env(ALARM_MONITOR_APP_VERSION="v1.2.3"):
        app_config = config.load_config()

    assert app_config.app_version == "v1.2.3"
    assert app_config.app_version_url.endswith("/releases/tag/v1.2.3")


def test_load_config_respects_explicit_version_url():
    _clear_alarm_env()
    importlib.reload(config)

    with _temp_env(
        ALARM_MONITOR_APP_VERSION="v2.0.0",
        ALARM_MONITOR_APP_VERSION_URL="https://example.invalid/releases/v2.0.0",
    ):
        app_config = config.load_config()

    assert app_config.app_version == "v2.0.0"
    assert app_config.app_version_url == "https://example.invalid/releases/v2.0.0"


def test_load_config_reads_ors_api_key():
    _clear_alarm_env()
    importlib.reload(config)

    with _temp_env(ALARM_MONITOR_ORS_API_KEY="secret-key"):
        app_config = config.load_config()

    assert app_config.ors_api_key == "secret-key"


def test_load_config_reads_messenger_settings():
    _clear_alarm_env()
    importlib.reload(config)

    with _temp_env(
        ALARM_MONITOR_MESSENGER_SERVER_URL="https://messenger.example.com",
        ALARM_MONITOR_MESSENGER_API_KEY="test-api-key-123",
    ):
        app_config = config.load_config()

    assert app_config.messenger_server_url == "https://messenger.example.com"
    assert app_config.messenger_api_key == "test-api-key-123"


def test_load_config_disables_messenger_without_api_key():
    _clear_alarm_env()
    importlib.reload(config)

    with _temp_env(
        ALARM_MONITOR_MESSENGER_SERVER_URL="https://messenger.example.com",
    ):
        app_config = config.load_config()

    # The system should disable messenger if URL is set but API key is missing
    assert app_config.messenger_server_url is None
    assert app_config.messenger_api_key is None


def test_load_config_messenger_defaults_to_none():
    _clear_alarm_env()
    importlib.reload(config)

    app_config = config.load_config()

    assert app_config.messenger_server_url is None
    assert app_config.messenger_api_key is None


def test_load_config_show_last_alarm_defaults_to_true():
    _clear_alarm_env()
    importlib.reload(config)

    app_config = config.load_config()

    assert app_config.show_last_alarm is True


def test_load_config_show_last_alarm_can_be_disabled():
    _clear_alarm_env()
    importlib.reload(config)

    with _temp_env(ALARM_MONITOR_SHOW_LAST_ALARM="false"):
        app_config = config.load_config()

    assert app_config.show_last_alarm is False


def test_load_config_reads_legacy_env_prefix():
    _clear_alarm_env()
    importlib.reload(config)

    with _temp_env(ALARM_DASHBOARD_API_KEY="legacy-api-key"):
        app_config = config.load_config()

    assert app_config.api_key == "legacy-api-key"


def test_load_config_warnings_min_level_defaults_to_three():
    _clear_alarm_env()
    importlib.reload(config)

    app_config = config.load_config()

    assert app_config.warnings_min_level == 3


def test_load_config_warnings_min_level_can_be_set():
    _clear_alarm_env()
    importlib.reload(config)

    with _temp_env(ALARM_MONITOR_WARNINGS_MIN_LEVEL="2"):
        app_config = config.load_config()

    assert app_config.warnings_min_level == 2


# ---------------------------------------------------------------------------
# Part 2c – Path traversal validation
# ---------------------------------------------------------------------------


def test_load_config_rejects_relative_history_file_path():
    """A relative path for HISTORY_FILE should raise MissingConfiguration."""
    import pytest
    _clear_alarm_env()
    importlib.reload(config)

    with _temp_env(ALARM_MONITOR_HISTORY_FILE="relative/path/alarm.json"):
        with pytest.raises(config.MissingConfiguration, match="absolute"):
            config.load_config()


def test_load_config_rejects_path_traversal_in_history_file():
    """A path with '..' components for HISTORY_FILE should raise MissingConfiguration."""
    import pytest
    _clear_alarm_env()
    importlib.reload(config)

    with _temp_env(ALARM_MONITOR_HISTORY_FILE="/data/../etc/alarm.json"):
        with pytest.raises(config.MissingConfiguration):
            config.load_config()


def test_load_config_rejects_history_file_outside_allowed_base():
    """A path outside /app/instance for HISTORY_FILE should raise MissingConfiguration."""
    import pytest
    _clear_alarm_env()
    importlib.reload(config)

    with _temp_env(ALARM_MONITOR_HISTORY_FILE="/etc/passwd"):
        with pytest.raises(config.MissingConfiguration, match="escapes allowed directory"):
            config.load_config()


def test_load_config_reads_hdmi_cec_env_vars():
    _clear_alarm_env()
    importlib.reload(config)

    with _temp_env(
        ALARM_MONITOR_CEC_ENABLED="true",
        ALARM_MONITOR_CEC_CLIENT_PATH="/opt/bin/cec-client",
        ALARM_MONITOR_CEC_DEVICE_ADDRESS="0",
        ALARM_MONITOR_CEC_IDLE_STANDBY_MINUTES="15",
        ALARM_MONITOR_CEC_WAKE_ON_ALARM="false",
        ALARM_MONITOR_CEC_STANDBY_ON_IDLE="true",
    ):
        app_config = config.load_config()

    assert app_config.cec_enabled is True
    assert app_config.cec_client_path == "/opt/bin/cec-client"
    assert app_config.cec_device_address == 0
    assert app_config.cec_idle_standby_minutes == 15
    assert app_config.cec_wake_on_alarm is False
    assert app_config.cec_standby_on_idle is True
