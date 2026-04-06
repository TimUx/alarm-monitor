"""Views Blueprint – all HTML page route handlers."""

from __future__ import annotations

import logging

from flask import Blueprint, current_app, render_template, url_for

LOGGER = logging.getLogger(__name__)

views_bp = Blueprint("views", __name__)


def _get_config():
    return current_app.config["APP_CONFIG"]


def _get_effective_settings():
    from ..app import get_effective_settings
    settings_store = current_app.config["SETTINGS_STORE"]
    return get_effective_settings(settings_store, _get_config())


@views_bp.route("/")
def dashboard() -> str:
    config = _get_config()
    crest_url = url_for("static", filename="img/crest.png")
    effective_settings = _get_effective_settings()
    return render_template(
        "dashboard.html",
        crest_url=crest_url,
        department_name=effective_settings["fire_department_name"],
        display_duration_minutes=config.display_duration_minutes,
        app_version=config.app_version,
        app_version_url=config.app_version_url,
    )


@views_bp.route("/navigation")
def navigation_page() -> str:
    config = _get_config()
    crest_url = url_for("static", filename="img/crest.png")
    effective_settings = _get_effective_settings()
    return render_template(
        "navigation.html",
        crest_url=crest_url,
        department_name=effective_settings["fire_department_name"],
        default_latitude=effective_settings["default_latitude"],
        default_longitude=effective_settings["default_longitude"],
        default_location_name=effective_settings["default_location_name"],
        app_version=config.app_version,
        app_version_url=config.app_version_url,
    )


@views_bp.route("/history")
def history_page() -> str:
    config = _get_config()
    crest_url = url_for("static", filename="img/crest.png")
    effective_settings = _get_effective_settings()
    return render_template(
        "history.html",
        crest_url=crest_url,
        department_name=effective_settings["fire_department_name"],
        app_version=config.app_version,
        app_version_url=config.app_version_url,
    )


@views_bp.route("/mobile")
def mobile_dashboard() -> str:
    config = _get_config()
    crest_url = url_for("static", filename="img/crest.png")
    effective_settings = _get_effective_settings()
    return render_template(
        "mobile.html",
        crest_url=crest_url,
        department_name=effective_settings["fire_department_name"],
        app_version=config.app_version,
        app_version_url=config.app_version_url,
    )


@views_bp.route("/settings")
def settings_page() -> str:
    """Settings configuration page."""
    from ..app import generate_csrf_token
    config = _get_config()
    crest_url = url_for("static", filename="img/crest.png")
    effective_settings = _get_effective_settings()
    csrf_token = generate_csrf_token(config.settings_password) if config.settings_password else ""
    return render_template(
        "settings.html",
        crest_url=crest_url,
        department_name=effective_settings["fire_department_name"],
        app_version=config.app_version,
        app_version_url=config.app_version_url,
        api_key_configured=bool(config.api_key),
        csrf_token=csrf_token,
    )


@views_bp.route("/health")
def health():
    from flask import jsonify
    return jsonify({"status": "ok"}), 200
