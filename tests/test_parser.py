"""Tests for the alarm e-mail parser."""

from __future__ import annotations

import textwrap

from alarm_dashboard.parser import parse_alarm


def test_parse_alarm_returns_none_without_incident_xml() -> None:
    """Plain text messages without INCIDENT XML should be ignored."""

    raw_email = textwrap.dedent(
        """
        Subject: Plain Message

        This is a plain text notification without the expected payload.
        """
    ).lstrip().encode("utf-8")

    assert parse_alarm(raw_email) is None
