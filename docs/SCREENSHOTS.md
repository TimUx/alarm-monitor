# 📸 Screenshot-Dokumentation

Dieser Guide beschreibt alle Screenshots und Ansichten des Alarm Monitor Systems.

**Auflösungen:**
- Desktop: **1920×1080** (Full HD)
- Mobile: **390×844** (iPhone 14)

**Farbmodi:**
- **Light** – Helles Theme (Alarmansichten, Verwaltungsseiten bei hellem System-Theme)
- **Dark** – Dunkles Theme (Ruhezustand Dashboard/Mobile, Verwaltungsseiten bei dunklem System-Theme)

> Dashboard und Mobile wechseln den Modus automatisch: **Alarm = Light**, **Idle/Unwetter = Dark**.
> Historie, Navigation und Einstellungen folgen dem System-Theme (`prefers-color-scheme`).

---

## Inhaltsverzeichnis

- [Übersicht](#übersicht)
- [Dashboard-Ansichten](#dashboard-ansichten)
- [Mobile-Ansichten](#mobile-ansichten)
- [Historie-Ansicht](#historie-ansicht)
- [Navigations-Ansicht](#navigations-ansicht)
- [Einstellungs-Ansicht](#einstellungs-ansicht)
- [Screenshots erstellen](#screenshots-erstellen)

---

## Übersicht

| Datei | Modus | Auflösung | Beschreibung |
|-------|-------|-----------|--------------|
| `dashboard-alarm-light.png` | Light | 1920×1080 | Dashboard – Alarmansicht |
| `dashboard-messenger-light.png` | Light | 1920×1080 | Dashboard – Teilnehmerrückmeldungen |
| `dashboard-idle-dark.png` | Dark | 1920×1080 | Dashboard – Ruhezustand |
| `mobile-alarm-light.png` | Light | 390×844 | Mobile – Alarmansicht |
| `mobile-idle-dark.png` | Dark | 390×844 | Mobile – Ruhezustand |
| `mobile-unwetter-dark.png` | Dark | 390×844 | Mobile – Unwetterwarnung |
| `history-light.png` | Light | 1920×1080 | Einsatzhistorie |
| `history-dark.png` | Dark | 1920×1080 | Einsatzhistorie |
| `navigation-light.png` | Light | 1920×1080 | Navigationsseite |
| `navigation-dark.png` | Dark | 1920×1080 | Navigationsseite |
| `settings-light.png` | Light | 1920×1080 | Einstellungen |
| `settings-dark.png` | Dark | 1920×1080 | Einstellungen |

---

## Dashboard-Ansichten

### Dashboard – Alarmansicht (Light)

**Datei**: `docs/screenshots/dashboard-alarm-light.png`

**Angezeigte Elemente**:
- Alarm-Header mit Stichwort, Unterstichwort und Zeitstempel
- Diagnose und Bemerkungen
- Vollständige Adressinformationen und alarmierte Fahrzeuge
- Interaktive Karte mit Einsatzort-Marker
- Wetterdaten am Einsatzort
- Bottom-Navigation

![Dashboard Alarmansicht (Light)](screenshots/dashboard-alarm-light.png)

---

### Dashboard – Teilnehmerrückmeldungen (Light)

**Datei**: `docs/screenshots/dashboard-messenger-light.png`

**Angezeigte Elemente**:
- Alle Elemente der Standard-Alarmansicht
- Teilnehmerrückmeldungs-Panel mit Qualifikationen und Führungsrollen

![Dashboard mit Teilnehmerrückmeldungen (Light)](screenshots/dashboard-messenger-light.png)

---

### Dashboard – Ruhezustand (Dark)

**Datei**: `docs/screenshots/dashboard-idle-dark.png`

**Angezeigte Elemente**:
- Digitale Uhr und Datum
- Aktuelles Wetter am Standort
- Letzter Einsatz
- Nächste Termine (Kalender)
- DWD-Unwetterwarnungen (Testmodus)
- Dashboard-Nachrichten

![Dashboard Ruhezustand (Dark)](screenshots/dashboard-idle-dark.png)

---

## Mobile-Ansichten

### Mobile – Ruhezustand (Dark)

**Datei**: `docs/screenshots/mobile-idle-dark.png`

**Angezeigte Elemente**:
- Responsive Header mit Feuerwehr-Name und Wappen
- Digitale Uhr und Datum
- Aktuelles Wetter und letzter Einsatz
- DWD-Unwetterwarnungen
- Nachrichten / Meldungen
- Feste Bottom-Navigation mit Safe-Area

![Mobile Ruhezustand (Dark)](screenshots/mobile-idle-dark.png)

---

### Mobile – Unwetterwarnung (Dark)

**Datei**: `docs/screenshots/mobile-unwetter-dark.png`

**Angezeigte Elemente**:
- Unwetter-Überschrift mit Bundesland
- Warnstufe, Headline und Beschreibung
- Gültigkeitszeitraum und DWD-Warnkarte
- Testmodus-Badge bei simulierter Warnung

**Voraussetzung**: `ALARM_DASHBOARD_DWD_WARNINGS_MOCK=true` oder Einstellungen → „Unwetterwarnung simulieren (Test)"

![Mobile Unwetterwarnung (Dark)](screenshots/mobile-unwetter-dark.png)

---

### Mobile – Alarmansicht (Light)

**Datei**: `docs/screenshots/mobile-alarm-light.png`

**Angezeigte Elemente**:
- Kompakter Alarm-Header mit Stichwort und Diagnose
- Vollständige Adressinformationen und alarmierte Fahrzeuge
- „Navigation starten"-Button
- Interaktive Karte und Wetterdaten am Einsatzort

![Mobile Alarmansicht (Light)](screenshots/mobile-alarm-light.png)

---

## Historie-Ansicht

### Einsatzhistorie (Light / Dark)

**Dateien**:
- `docs/screenshots/history-light.png`
- `docs/screenshots/history-dark.png`

**Angezeigte Elemente**:
- Tabellarische Übersicht vergangener Einsätze
- Datum, Stichwort, Ort, Diagnose, alarmierte Fahrzeuge
- Bottom-Navigation

| Light | Dark |
|-------|------|
| ![Historie Light](screenshots/history-light.png) | ![Historie Dark](screenshots/history-dark.png) |

---

## Navigations-Ansicht

### Navigation – Routenplanung (Light / Dark)

**Dateien**:
- `docs/screenshots/navigation-light.png`
- `docs/screenshots/navigation-dark.png`

**Angezeigte Elemente**:
- Interaktive Karte mit Einsatzort-Marker
- Automatische Übernahme des aktiven Alarms
- Links zur externen Navigation

| Light | Dark |
|-------|------|
| ![Navigation Light](screenshots/navigation-light.png) | ![Navigation Dark](screenshots/navigation-dark.png) |

---

## Einstellungs-Ansicht

### Einstellungen (Light / Dark)

**Dateien**:
- `docs/screenshots/settings-light.png`
- `docs/screenshots/settings-dark.png`

**Angezeigte Elemente**:
- Feuerwehr-Name und Standortkoordinaten
- Gruppen-Filter, Kalender-URLs, ntfy.sh-Integration
- Unwetter-Simulation (Testmodus)
- Logo-Verwaltung

| Light | Dark |
|-------|------|
| ![Einstellungen Light](screenshots/settings-light.png) | ![Einstellungen Dark](screenshots/settings-dark.png) |

---

## Screenshots erstellen

### Automatisch (empfohlen)

```bash
# Aus dem Projektverzeichnis, mit aktivierter venv:
pip install playwright
playwright install chromium
python scripts/capture_screenshots.py
```

Das Skript startet einen Testserver, befüllt Beispieldaten und erstellt alle Screenshots in `docs/screenshots/`.

### Manuell

1. **App starten** mit Testdaten und Mock-Warnungen:
```bash
ALARM_DASHBOARD_API_KEY=test-key \
ALARM_DASHBOARD_SETTINGS_PASSWORD=test-pass \
ALARM_DASHBOARD_FIRE_DEPARTMENT_NAME=Musterstadt \
ALARM_DASHBOARD_DWD_WARNINGS_MOCK=true \
python -m flask --app alarm_dashboard.app:create_app run --port 8000
```

2. **Testalarm senden** (siehe README oder `scripts/capture_screenshots.py` für Beispiel-Payloads)

3. **Auflösung einstellen**:
   - Desktop: 1920×1080
   - Mobile: 390×844

4. **Farbmodus**:
   - Light: Alarmansichten oder helles System-Theme
   - Dark: Ruhezustand oder dunkles System-Theme (DevTools → Rendering → `prefers-color-scheme: dark`)

### Benennung

Format: `<ansicht>-<light|dark>.png`

Beispiele: `dashboard-alarm-light.png`, `history-dark.png`, `mobile-unwetter-dark.png`

### Checkliste bei UI-Änderungen

- [ ] `python scripts/capture_screenshots.py` ausgeführt
- [ ] Beispieldaten verwendet (keine echten Einsatzdaten)
- [ ] Light- und Dark-Varianten aktualisiert (wo zutreffend)
- [ ] Referenzen in README.md und diesem Guide angepasst

---

<div align="center">

[⬆ Zurück nach oben](#-screenshot-dokumentation)

</div>
