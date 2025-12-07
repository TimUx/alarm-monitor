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


def test_parse_alarm_extracts_incident_number() -> None:
    """The ENR field should be parsed as incident_number."""

    raw_email = textwrap.dedent(
        """
        Subject: Alarm

        <INCIDENT>
          <ENR>7850001123</ENR>
          <STICHWORT>F3Y</STICHWORT>
          <EBEGINN>24.07.2026 18:42:11</EBEGINN>
        </INCIDENT>
        """
    ).lstrip().encode("utf-8")

    alarm = parse_alarm(raw_email)
    assert alarm is not None
    assert alarm["incident_number"] == "7850001123"


def test_parse_alarm_without_enr() -> None:
    """Alarms without ENR should have incident_number set to None."""

    raw_email = textwrap.dedent(
        """
        Subject: Alarm

        <INCIDENT>
          <STICHWORT>F3Y</STICHWORT>
          <EBEGINN>24.07.2026 18:42:11</EBEGINN>
        </INCIDENT>
        """
    ).lstrip().encode("utf-8")

    alarm = parse_alarm(raw_email)
    assert alarm is not None
    assert alarm["incident_number"] is None


def test_parse_alarm_with_empty_enr() -> None:
    """Alarms with empty ENR should have incident_number set to None."""

    raw_email = textwrap.dedent(
        """
        Subject: Alarm

        <INCIDENT>
          <ENR></ENR>
          <STICHWORT>F3Y</STICHWORT>
          <EBEGINN>24.07.2026 18:42:11</EBEGINN>
        </INCIDENT>
        """
    ).lstrip().encode("utf-8")

    alarm = parse_alarm(raw_email)
    assert alarm is not None
    assert alarm["incident_number"] is None

