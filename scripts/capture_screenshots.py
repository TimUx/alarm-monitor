#!/usr/bin/env python3
"""Capture documentation screenshots for all Alarm Monitor views (light & dark)."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "screenshots"
INSTANCE_DIR = ROOT / "instance"
BASE_URL = os.environ.get("SCREENSHOT_BASE_URL", "http://127.0.0.1:8002")
API_KEY = os.environ.get("SCREENSHOT_API_KEY", "screenshot-key")
SETTINGS_PASSWORD = os.environ.get("SCREENSHOT_SETTINGS_PASSWORD", "screenshot-pass")

DESKTOP = {"width": 1920, "height": 1080}
MOBILE = {"width": 390, "height": 844}

MOCK_PARTICIPANTS = {
    "participants": [
        {
            "id": "response-1",
            "deviceId": "device-1",
            "platform": "android",
            "respondedAt": "2026-06-05T14:00:00.000Z",
            "responder": {
                "firstName": "Max",
                "lastName": "Mustermann",
                "qualifications": {"machinist": True, "agt": True, "paramedic": False},
                "leadershipRole": "groupLeader",
            },
        },
        {
            "id": "response-2",
            "deviceId": "device-2",
            "platform": "ios",
            "respondedAt": "2026-06-05T14:01:00.000Z",
            "responder": {
                "firstName": "Anna",
                "lastName": "Schmidt",
                "qualifications": {"machinist": False, "agt": False, "paramedic": True},
                "leadershipRole": "none",
            },
        },
        {
            "id": "response-3",
            "deviceId": "device-3",
            "platform": "android",
            "respondedAt": "2026-06-05T14:02:00.000Z",
            "responder": {
                "firstName": "Tom",
                "lastName": "Bauer",
                "qualifications": {"machinist": True, "agt": False, "paramedic": False},
                "leadershipRole": "platoonLeader",
            },
        },
    ]
}

MOCK_CALENDAR = {
    "configured": True,
    "events": [
        {"start": "2026-06-10T19:00:00+00:00", "summary": "Übung Gelände"},
        {"start": "2026-06-12T19:30:00+00:00", "summary": "Dienstbesprechung"},
        {"start": "2026-06-15T09:00:00+00:00", "summary": "Gerätewartung TLF"},
    ],
}

SCREENSHOT_SETTINGS: dict[str, Any] = {
    "fire_department_name": "Musterstadt",
    "activation_groups": ["MST26", "MST41", "MST52"],
    "default_latitude": 51.0,
    "default_longitude": 9.0,
    "default_location_name": "Feuerwache Musterstadt",
    "show_last_alarm": True,
    "warnings_min_level": 3,
    "dwd_warnings_mock": True,
    "calendar_urls": [
        "https://calendar.google.com/calendar/ical/example%40group.calendar.google.com/private-abc123/basic.ics",
    ],
    "ntfy_topic_url": "https://ntfy.sh/musterstadt-fw",
    "ntfy_poll_interval": 60,
    "message_default_ttl_minutes": 60,
}

ALARM_PAYLOAD = {
    "incident_number": "2026-SCREEN-001",
    "keyword": "B3 - Wohnungsbrand",
    "keyword_secondary": "Menschenleben in Gefahr",
    "diagnosis": "Wohnungsbrand, 2. OG",
    "remark": "2 Personen gerettet",
    "location": "Musterstraße 42, 12345 Musterstadt",
    "latitude": 51.2345,
    "longitude": 9.8765,
    "groups": ["LF20-MST", "TLF4000-MST", "DLK23/12-MST"],
    "dispatch_group_codes": ["MST26"],
}

HISTORY_ALARMS = [
    {
        "incident_number": "2026-HIST-003",
        "keyword": "H1 - Hilfeleistung",
        "diagnosis": "Verkehrsunfall, eingeklemmte Person",
        "location": "Bundesstraße 1, 12345 Musterstadt",
        "latitude": 51.22,
        "longitude": 9.85,
        "groups": ["LF20-MST", "RW-MST"],
    },
    {
        "incident_number": "2026-HIST-002",
        "keyword": "B2 - Kleinbrand",
        "diagnosis": "Müllcontainerbrand",
        "location": "Gartenstraße 8, 12345 Musterstadt",
        "latitude": 51.21,
        "longitude": 9.84,
        "groups": ["LF20-MST"],
    },
    {
        "incident_number": "2026-HIST-001",
        "keyword": "R1 - Technische Hilfe",
        "diagnosis": "Baum auf Straße",
        "location": "Waldweg 3, 12345 Musterstadt",
        "latitude": 51.20,
        "longitude": 9.83,
        "groups": ["LF20-MST", "GW-MST"],
    },
]


def api_post(path: str, payload: dict | None = None) -> None:
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        method="POST",
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
    )
    urllib.request.urlopen(req)


def wait_for_server(timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{BASE_URL}/health", timeout=2) as resp:
                if resp.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.5)
    raise RuntimeError(f"Server not reachable at {BASE_URL}")


def reset_history() -> None:
    history_path = INSTANCE_DIR / "alarm_history.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text('{"alarm": null, "history": []}', encoding="utf-8")


def write_settings(overrides: dict[str, Any] | None = None) -> None:
    """Persist settings for screenshot scenarios."""
    settings = {**SCREENSHOT_SETTINGS, **(overrides or {})}
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
    (INSTANCE_DIR / "settings.json").write_text(
        json.dumps(settings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_idle_history() -> None:
    """Persist idle state with a last-alarm entry but no active alarm."""
    entry = {
        "alarm": {
            "incident_number": "2026-HIST-002",
            "keyword": "B2 - Kleinbrand",
            "diagnosis": "Müllcontainerbrand",
            "location": "Gartenstraße 8, 12345 Musterstadt",
            "groups": ["LF20-MST"],
        },
        "received_at": "2026-06-04T18:30:00+00:00",
        "coordinates": {"lat": 51.21, "lon": 9.84},
    }
    history_path = INSTANCE_DIR / "alarm_history.json"
    history_path.write_text(
        json.dumps({"alarm": None, "history": [entry]}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def seed_alarm_data() -> None:
    reset_history()
    for alarm in HISTORY_ALARMS:
        api_post("/api/alarm", alarm)
        time.sleep(0.2)
    api_post("/api/alarm", ALARM_PAYLOAD)
    api_post("/api/messages", {
        "text": "Dienstbesprechung morgen 19:00 Uhr!",
        "ttl_minutes": 1440,
    })


def seed_idle_messages() -> None:
    api_post("/api/messages", {
        "text": "Dienstbesprechung morgen 19:00 Uhr!",
        "ttl_minutes": 1440,
    })


async def setup_routes(page, *, include_calendar: bool = True) -> None:
    async def fulfill_json(route, payload):
        await route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(payload),
        )

    await page.route("**/api/alarm/participants/**", lambda r: fulfill_json(r, MOCK_PARTICIPANTS))
    if include_calendar:
        await page.route("**/api/calendar", lambda r: fulfill_json(r, MOCK_CALENDAR))


async def wait_dashboard_alarm(page) -> None:
    await page.wait_for_selector("#alarm-view:not(.hidden)", timeout=20000)


async def wait_dashboard_idle(page) -> None:
    await page.wait_for_selector("#idle-view:not(.hidden)", timeout=20000)


async def wait_mobile_alarm(page) -> None:
    await page.wait_for_selector("#mobile-alarm-view:not(.hidden)", timeout=20000)


async def wait_mobile_idle(page) -> None:
    await page.wait_for_selector("#mobile-idle-view:not(.hidden)", timeout=20000)


async def force_idle_side_panel(page, *, show_warnings: bool) -> None:
    """Force the right idle panel to warnings or calendar (default layout)."""
    await page.evaluate(
        """(showWarnings) => {
            if (typeof idleSidePanelShowWarnings !== 'undefined') {
                idleSidePanelShowWarnings = showWarnings;
            }
            if (typeof updateIdleSidePanelVisibility === 'function') {
                updateIdleSidePanelVisibility();
            }
        }""",
        show_warnings,
    )


async def capture(page, path: Path, *, full_page: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=str(path), full_page=full_page)
    print(f"  ✓ {path.relative_to(ROOT)}")


async def capture_settings(playwright) -> None:
    browser = await playwright.chromium.launch(args=["--no-sandbox"])

    for theme, suffix in (("light", "light"), ("dark", "dark")):
        ctx = await browser.new_context(viewport=DESKTOP, color_scheme=theme)
        page = await ctx.new_page()
        await setup_routes(page)
        await page.goto(f"{BASE_URL}/settings")
        await page.wait_for_selector("#settings-form", timeout=15000)
        await page.wait_for_timeout(2500)
        await capture(page, OUT_DIR / f"settings-{suffix}.png", full_page=True)
        await ctx.close()

    await browser.close()


async def capture_alarm_phase(playwright) -> None:
    browser = await playwright.chromium.launch(args=["--no-sandbox"])

    ctx = await browser.new_context(viewport=DESKTOP, color_scheme="light")
    page = await ctx.new_page()
    await setup_routes(page)

    await page.goto(f"{BASE_URL}/")
    await wait_dashboard_alarm(page)
    await page.wait_for_timeout(4000)
    await capture(page, OUT_DIR / "dashboard-alarm-light.png")

    await page.goto(f"{BASE_URL}/")
    await wait_dashboard_alarm(page)
    await page.evaluate(
        """() => {
            const col = document.getElementById('participants-column');
            const list = document.getElementById('participants-list');
            const layout = document.querySelector('.alarm-layout');
            if (!col || !list) return;
            col.classList.remove('hidden');
            layout?.classList.add('has-participants');
            list.innerHTML = `
                <div class="participant-item">
                    <div class="participant-name">M., M.</div>
                    <div class="participant-meta">
                        <div class="participant-qualifications">
                            <span class="qualification-badge qualification-badge--agt" title="AGT"></span>
                            <span class="qualification-badge qualification-badge--machinist" title="Maschinist"></span>
                        </div>
                        <div class="participant-leadership"><span class="leadership-bar"></span></div>
                    </div>
                </div>
                <div class="participant-item">
                    <div class="participant-name">S., A.</div>
                    <div class="participant-meta">
                        <div class="participant-qualifications">
                            <span class="qualification-badge qualification-badge--paramedic" title="Sanitäter"></span>
                        </div>
                    </div>
                </div>
                <div class="participant-item">
                    <div class="participant-name">B., T.</div>
                    <div class="participant-meta">
                        <div class="participant-qualifications">
                            <span class="qualification-badge qualification-badge--machinist" title="Maschinist"></span>
                        </div>
                        <div class="participant-leadership">
                            <span class="leadership-bar"></span><span class="leadership-bar"></span>
                        </div>
                    </div>
                </div>`;
        }"""
    )
    await page.wait_for_timeout(2000)
    await capture(page, OUT_DIR / "dashboard-messenger-light.png")

    await page.goto(f"{BASE_URL}/navigation")
    await page.wait_for_timeout(4000)
    await capture(page, OUT_DIR / "navigation-light.png")

    await page.goto(f"{BASE_URL}/history")
    await page.wait_for_selector("#history-tbody tr", timeout=15000)
    await page.wait_for_timeout(1500)
    await capture(page, OUT_DIR / "history-light.png")
    await ctx.close()

    ctx = await browser.new_context(viewport=DESKTOP, color_scheme="dark")
    page = await ctx.new_page()
    await setup_routes(page)

    await page.goto(f"{BASE_URL}/navigation")
    await page.wait_for_timeout(4000)
    await capture(page, OUT_DIR / "navigation-dark.png")

    await page.goto(f"{BASE_URL}/history")
    await page.wait_for_selector("#history-tbody tr", timeout=15000)
    await page.wait_for_timeout(1500)
    await capture(page, OUT_DIR / "history-dark.png")
    await ctx.close()

    ctx = await browser.new_context(
        viewport=MOBILE,
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True,
        color_scheme="light",
    )
    page = await ctx.new_page()
    await setup_routes(page)

    await page.goto(f"{BASE_URL}/mobile")
    await wait_mobile_alarm(page)
    await page.wait_for_timeout(4500)
    await capture(page, OUT_DIR / "mobile-alarm-light.png", full_page=True)
    await ctx.close()

    await browser.close()


async def capture_idle_default(playwright) -> None:
    """Idle with last alarm left; warnings or calendar on the right."""
    browser = await playwright.chromium.launch(args=["--no-sandbox"])

    ctx = await browser.new_context(viewport=DESKTOP, color_scheme="dark")
    page = await ctx.new_page()
    await setup_routes(page)

    await page.goto(f"{BASE_URL}/")
    await wait_dashboard_idle(page)
    await page.wait_for_timeout(3500)
    await force_idle_side_panel(page, show_warnings=True)
    await page.wait_for_timeout(1500)
    await capture(page, OUT_DIR / "dashboard-idle-dark.png")

    await force_idle_side_panel(page, show_warnings=False)
    await page.wait_for_timeout(1500)
    await capture(page, OUT_DIR / "dashboard-idle-calendar-dark.png")
    await ctx.close()

    ctx = await browser.new_context(
        viewport=MOBILE,
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True,
        color_scheme="dark",
    )
    page = await ctx.new_page()
    await setup_routes(page, include_calendar=False)

    await page.goto(f"{BASE_URL}/mobile")
    await wait_mobile_idle(page)
    await page.wait_for_timeout(3500)
    await capture(page, OUT_DIR / "mobile-idle-dark.png", full_page=True)
    await capture(page, OUT_DIR / "mobile-unwetter-dark.png", full_page=True)
    await ctx.close()

    await browser.close()


async def capture_idle_no_last_alarm(playwright) -> None:
    """Idle without last alarm: warnings left, calendar right."""
    browser = await playwright.chromium.launch(args=["--no-sandbox"])

    ctx = await browser.new_context(viewport=DESKTOP, color_scheme="dark")
    page = await ctx.new_page()
    await setup_routes(page)

    await page.goto(f"{BASE_URL}/")
    await wait_dashboard_idle(page)
    await page.wait_for_timeout(4000)
    await capture(page, OUT_DIR / "dashboard-idle-no-last-alarm-dark.png")
    await ctx.close()

    ctx = await browser.new_context(
        viewport=MOBILE,
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True,
        color_scheme="dark",
    )
    page = await ctx.new_page()
    await setup_routes(page)

    await page.goto(f"{BASE_URL}/mobile")
    await wait_mobile_idle(page)
    await page.wait_for_timeout(3500)
    await capture(page, OUT_DIR / "mobile-idle-no-last-alarm-dark.png", full_page=True)
    await ctx.close()

    await browser.close()


def start_server() -> subprocess.Popen:
    env = os.environ.copy()
    env.update({
        "ALARM_MONITOR_API_KEY": API_KEY,
        "ALARM_MONITOR_SETTINGS_PASSWORD": SETTINGS_PASSWORD,
        "ALARM_MONITOR_FIRE_DEPARTMENT_NAME": "Musterstadt",
        "ALARM_MONITOR_DEFAULT_LATITUDE": "51.0",
        "ALARM_MONITOR_DEFAULT_LONGITUDE": "9.0",
        "ALARM_MONITOR_DWD_WARNINGS_MOCK": "true",
        "FLASK_APP": "alarm_dashboard.app:create_app",
    })
    return subprocess.Popen(
        [sys.executable, "-m", "flask", "run", "--port", "8002", "--host", "127.0.0.1"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture Alarm Monitor documentation screenshots")
    parser.add_argument(
        "--no-server",
        action="store_true",
        help="Assume a server is already running at SCREENSHOT_BASE_URL",
    )
    args = parser.parse_args()

    async def full_run() -> None:
        if args.no_server:
            wait_for_server()
            write_settings()
            seed_alarm_data()
            async with async_playwright() as playwright:
                await capture_alarm_phase(playwright)
                await capture_settings(playwright)
                write_idle_history()
                await capture_idle_default(playwright)
            print("Note: idle variant screenshots need server restarts – run without --no-server")
            return

        async with async_playwright() as playwright:
            write_settings()
            server = start_server()
            try:
                wait_for_server()
                seed_alarm_data()
                await capture_alarm_phase(playwright)
                await capture_settings(playwright)
            finally:
                server.terminate()
                server.wait(timeout=5)

            write_idle_history()
            write_settings({"show_last_alarm": True})
            server = start_server()
            try:
                wait_for_server()
                seed_idle_messages()
                await capture_idle_default(playwright)
            finally:
                server.terminate()
                server.wait(timeout=5)

            write_idle_history()
            write_settings({"show_last_alarm": False})
            server = start_server()
            try:
                wait_for_server()
                seed_idle_messages()
                await capture_idle_no_last_alarm(playwright)
            finally:
                server.terminate()
                server.wait(timeout=5)

    asyncio.run(full_run())
    print(f"\nScreenshots saved to {OUT_DIR}")


if __name__ == "__main__":
    main()
