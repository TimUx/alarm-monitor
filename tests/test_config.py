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
