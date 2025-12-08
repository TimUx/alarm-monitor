import importlib
import os
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alarm_dashboard import config


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
        if name.startswith(config.ENV_PREFIX):
            del os.environ[name]


def test_load_config_without_imap_settings_disables_mail_fetching():
    _clear_alarm_env()
    importlib.reload(config)

    app_config = config.load_config()

    assert app_config.mail is None


def test_load_config_with_complete_imap_settings():
    _clear_alarm_env()
    importlib.reload(config)

    with _temp_env(
        ALARM_DASHBOARD_IMAP_HOST="imap.example.com",
        ALARM_DASHBOARD_IMAP_USERNAME="user",
        ALARM_DASHBOARD_IMAP_PASSWORD="secret",
    ):
        app_config = config.load_config()

    assert app_config.mail is not None
    assert app_config.mail.host == "imap.example.com"
    assert app_config.mail.username == "user"
    assert app_config.mail.password == "secret"


def test_load_config_with_history_file(tmp_path):
    _clear_alarm_env()
    importlib.reload(config)

    history_file = tmp_path / "history.json"

    with _temp_env(ALARM_DASHBOARD_HISTORY_FILE=str(history_file)):
        app_config = config.load_config()

    assert app_config.history_file == str(history_file)


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

    with _temp_env(ALARM_DASHBOARD_APP_VERSION="v1.2.3"):
        app_config = config.load_config()

    assert app_config.app_version == "v1.2.3"
    assert app_config.app_version_url.endswith("/releases/tag/v1.2.3")


def test_load_config_respects_explicit_version_url():
    _clear_alarm_env()
    importlib.reload(config)

    with _temp_env(
        ALARM_DASHBOARD_APP_VERSION="v2.0.0",
        ALARM_DASHBOARD_APP_VERSION_URL="https://example.invalid/releases/v2.0.0",
    ):
        app_config = config.load_config()

    assert app_config.app_version == "v2.0.0"
    assert app_config.app_version_url == "https://example.invalid/releases/v2.0.0"


def test_load_config_reads_ors_api_key():
    _clear_alarm_env()
    importlib.reload(config)

    with _temp_env(ALARM_DASHBOARD_ORS_API_KEY="secret-key"):
        app_config = config.load_config()

    assert app_config.ors_api_key == "secret-key"


def test_load_config_reads_messenger_settings():
    _clear_alarm_env()
    importlib.reload(config)

    with _temp_env(
        ALARM_DASHBOARD_MESSENGER_SERVER_URL="https://messenger.example.com",
        ALARM_DASHBOARD_MESSENGER_API_KEY="test-api-key-123",
    ):
        app_config = config.load_config()

    assert app_config.messenger_server_url == "https://messenger.example.com"
    assert app_config.messenger_api_key == "test-api-key-123"


def test_load_config_disables_messenger_without_api_key():
    _clear_alarm_env()
    importlib.reload(config)

    with _temp_env(
        ALARM_DASHBOARD_MESSENGER_SERVER_URL="https://messenger.example.com",
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

