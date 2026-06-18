# 🤝 Contributing to Alarm Monitor

Vielen Dank für Ihr Interesse, zum Alarm Monitor Projekt beizutragen! Dieses Dokument enthält Richtlinien und Best Practices für Beiträge.

---

## Inhaltsverzeichnis

- [Code of Conduct](#code-of-conduct)
- [Wie kann ich beitragen?](#wie-kann-ich-beitragen)
- [Entwicklungsumgebung einrichten](#entwicklungsumgebung-einrichten)
- [Entwicklungs-Workflow](#entwicklungs-workflow)
- [Coding-Standards](#coding-standards)
- [Tests](#tests)
- [Dokumentation](#dokumentation)
- [Pull Requests](#pull-requests)
- [Issue-Richtlinien](#issue-richtlinien)

---

## Verhaltenskodex

**Grundprinzipien** für Beiträge:
- Respektvoller und konstruktiver Umgang
- Offenheit für unterschiedliche Meinungen und Erfahrungen
- Fokus auf das Beste für die Community
- Empathie gegenüber anderen Community-Mitgliedern

---

## Wie kann ich beitragen?

Es gibt viele Wege, zum Projekt beizutragen:

### 🐛 Bugs melden
- Prüfen Sie, ob der Bug bereits als Issue gemeldet wurde
- Erstellen Sie ein neues Issue mit detaillierter Beschreibung
- Nutzen Sie die [Bug-Report-Vorlage](.github/ISSUE_TEMPLATE/bug_report.md)

### ✨ Features vorschlagen
- Prüfen Sie, ob das Feature bereits vorgeschlagen wurde
- Erstellen Sie ein Issue mit Ihrer Idee
- Nutzen Sie die [Feature-Request-Vorlage](.github/ISSUE_TEMPLATE/feature_request.md)
- Diskutieren Sie den Nutzen und die Implementierung

### 📝 Dokumentation verbessern
- Tippfehler korrigieren
- Klarheit verbessern
- Fehlende Informationen ergänzen
- Übersetzungen hinzufügen

### 💻 Code beitragen
- Bugs beheben
- Features implementieren
- Tests hinzufügen
- Performance verbessern

### 🎨 Design-Beiträge
- UI/UX-Verbesserungen
- Responsive Design
- Barrierefreiheit
- Farbschemata

---

## Entwicklungsumgebung einrichten

### Voraussetzungen

- **Python 3.9+**
- **Git**
- **Docker** (optional, empfohlen)
- **Code-Editor** (VS Code, PyCharm, etc.)

### Setup-Schritte

```bash
# 1. Repository forken
# Klicken Sie auf "Fork" auf GitHub

# 2. Repository klonen
git clone https://github.com/IHR-USERNAME/alarm-monitor.git
cd alarm-monitor

# 3. Upstream-Remote hinzufügen
git remote add upstream https://github.com/TimUx/alarm-monitor.git

# 4. Virtuelle Umgebung erstellen
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ODER
.venv\Scripts\activate  # Windows

# 5. Development-Dependencies installieren
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Wenn vorhanden

# 6. .env-Datei erstellen
cp .env.example .env
# API-Key generieren und eintragen
```

### Development-Server starten

```bash
# Flask Development Server
export FLASK_APP=alarm_dashboard.app
export FLASK_ENV=development
flask run --debug --host 0.0.0.0 --port 8000

# Oder mit Docker
docker compose up --build
```

---

## Entwicklungs-Workflow

### Branch-Strategie

- **`main`** – Stabile Produktion (einziger Dauerbranch)
- **Feature-Branches** – `feature/<name>` für neue Features
- **Bugfix-Branches** – `bugfix/<issue-number>` für Bug-Fixes
- **Hotfix-Branches** – `hotfix/<name>` für dringende Fixes

### Workflow-Schritte

```bash
# 1. Upstream synchronisieren
git checkout main
git fetch upstream
git merge upstream/main

# 2. Feature-Branch erstellen
git checkout -b feature/mein-feature

# 3. Änderungen vornehmen
# ... Code bearbeiten ...

# 4. Testen
pytest
black alarm_dashboard/  # Code formatieren
flake8 alarm_dashboard/  # Linting

# 5. Committen
git add .
git commit -m "Add: Mein neues Feature"

# 6. Pushen
git push origin feature/mein-feature

# 7. Pull Request erstellen
# Auf GitHub: "Create Pull Request"
```

---

## Coding-Standards

### Python-Code

**Style-Guide**: Wir folgen [PEP 8](https://pep8.org/)

**Formatierung**: Verwenden Sie `black`:
```bash
black alarm_dashboard/
```

**Linting**: Verwenden Sie `flake8`:
```bash
flake8 alarm_dashboard/ --max-line-length=100
```

**Type-Hints**: Verwenden Sie Type-Hints wo sinnvoll:
```python
def geocode_address(address: str, nominatim_url: str) -> Optional[tuple[float, float]]:
    """
    Geocodes an address using Nominatim.
    
    Args:
        address: The address to geocode
        nominatim_url: Base URL of Nominatim service
    
    Returns:
        Tuple of (latitude, longitude) or None if not found
    """
    ...
```

**Docstrings**: Verwenden Sie Google-Style Docstrings:
```python
def fetch_weather(latitude: float, longitude: float) -> dict:
    """Fetches weather data from Open-Meteo API.

    Args:
        latitude: Latitude in decimal degrees
        longitude: Longitude in decimal degrees

    Returns:
        Dictionary containing weather data with keys:
        - temperature: Current temperature in °C
        - precipitation: Precipitation in mm
        - wind_speed: Wind speed in km/h

    Raises:
        RequestException: If API request fails
    """
    ...
```

### Code-Organisation

**Dateistruktur**:
```
alarm_dashboard/
├── app.py              # Flask-App-Factory
├── routes/             # HTTP-Routen (views.py, api.py)
├── config.py           # Konfigurationsmanagement
├── storage.py          # Datenpersistenz
├── geocode.py          # Geokodierungs-Logik
├── weather.py          # Wetter-API-Integration
├── messenger.py        # Messenger-Integration
├── static/             # Statische Assets
│   ├── css/
│   ├── js/
│   └── img/
└── templates/          # HTML-Templates
    ├── dashboard.html
    ├── mobile.html
    ├── history.html
    └── navigation.html
```

**Module**: Halten Sie Module klein und fokussiert (Single Responsibility)

**Funktionen**: Max. 50 Zeilen pro Funktion (Richtlinie)

### JavaScript-Code

**Style-Guide**: Verwenden Sie ES6+ Features

**Formatierung**: Konsistente Einrückung (2 Spaces)

**Kommentare**: Dokumentieren Sie komplexe Logik

```javascript
/**
 * Fetches current alarm data from API
 * @returns {Promise<Object>} Alarm data object
 */
async function fetchAlarmData() {
  const response = await fetch('/api/alarm');
  return await response.json();
}
```

### CSS-Code

**Verwendung von CSS-Variablen**:
```css
:root {
  --accent: #e74c3c;
  --background: #1a1a1a;
}

.alarm-header {
  background-color: var(--accent);
}
```

**Mobile-First**: Beginnen Sie mit mobilen Styles, dann Desktop:
```css
.container {
  width: 100%;
}

@media (min-width: 768px) {
  .container {
    width: 750px;
  }
}
```

---

## Tests

### Test-Framework

Wir verwenden **pytest** für Unit-Tests.

### Tests ausführen

```bash
# Alle Tests
pytest

# Mit Coverage
pytest --cov=alarm_dashboard

# Spezifischer Test
pytest tests/test_storage.py

# Mit Output
pytest -v
```

### Tests schreiben

**Datei-Benennung**: `test_<module>.py`

**Funktion-Benennung**: `test_<function>_<scenario>()`

**Beispiel**:
```python
# tests/test_storage.py
import pytest
from alarm_dashboard.storage import AlarmStore

def test_store_alarm_success():
    """Test successful alarm storage"""
    store = AlarmStore(history_file='/tmp/test_history.json')
    alarm = {
        'incident_number': 'TEST-001',
        'keyword': 'F3Y'
    }
    result = store.store_alarm(alarm)
    assert result is True

def test_store_alarm_duplicate():
    """Test duplicate alarm rejection"""
    store = AlarmStore(history_file='/tmp/test_history.json')
    alarm = {'incident_number': 'TEST-001'}
    
    store.store_alarm(alarm)
    result = store.store_alarm(alarm)  # Duplicate
    
    assert result is False
```

### Test-Coverage

Streben Sie **80%+ Coverage** an für neue Features.

```bash
# Coverage-Report generieren
pytest --cov=alarm_dashboard --cov-report=html

# Report öffnen
open htmlcov/index.html
```

---

## Dokumentation

### Dokumentations-Typen

1. **Code-Kommentare**: Für komplexe Logik
2. **Docstrings**: Für alle öffentlichen Funktionen/Klassen
3. **README.md**: Projekt-Überblick und Schnellstart
4. **Guides**: Ausführliche Anleitungen (docs/)
5. **API-Dokumentation**: Endpunkt-Beschreibungen

### Markdown-Richtlinien

**Headings**: Verwenden Sie ATX-Style (`#` statt Unterstriche)

**Links**: Verwenden Sie relative Links für interne Dokumente:
```markdown
Siehe [Installation](docs/QUICK_START.md#installation)
```

**Code-Blöcke**: Immer mit Sprache:
````markdown
```python
def example():
    pass
```
````

**Listen**: Konsistente Marker (`-` oder `*`)

### Screenshot-Dokumentation

Wenn Sie UI-Änderungen vornehmen:
1. Screenshots automatisch erstellen: `python scripts/capture_screenshots.py`
2. Oder manuell speichern in `docs/screenshots/`
3. Benennung: `<ansicht>-<light|dark>.png` (z.B. `dashboard-idle-no-last-alarm-dark.png`, `settings-light.png`)
4. Referenzen in `README.md` und `docs/SCREENSHOTS.md` aktualisieren
5. Bei Idle-Layout-Änderungen alle Varianten erfassen (Standard, Kalender, ohne letzten Einsatz)

**Farbmodi:**
- Dashboard/Mobile Alarm = Light, Idle/Unwetter = Dark
- Historie, Navigation, Einstellungen = Light und Dark (System-Theme)

---

## Pull Requests

### Vor dem Erstellen

- ✅ Tests laufen durch
- ✅ Code ist formatiert (`black`)
- ✅ Linting zeigt keine Fehler (`flake8`)
- ✅ Dokumentation ist aktualisiert
- ✅ CHANGELOG.md ist aktualisiert (wenn vorhanden)

### PR-Titel

Verwenden Sie aussagekräftige Titel:

**Gut**:
- `Add: Webhook support for external systems`
- `Fix: Geocoding fails for addresses with umlauts`
- `Docs: Update installation guide for Docker`

**Schlecht**:
- `Update`
- `Fix bug`
- `Changes`

### PR-Beschreibung

Verwenden Sie diese Vorlage:

```markdown
## Beschreibung
<!-- Was macht dieser PR? -->

## Motivation
<!-- Warum ist diese Änderung notwendig? -->

## Änderungen
- [ ] Feature X hinzugefügt
- [ ] Bug Y behoben
- [ ] Dokumentation aktualisiert

## Tests
<!-- Wie wurde getestet? -->

## Screenshots
<!-- Bei UI-Änderungen -->

## Checklist
- [ ] Tests hinzugefügt/aktualisiert
- [ ] Dokumentation aktualisiert
- [ ] Code formatiert und gelintet
- [ ] Breaking Changes dokumentiert

## Related Issues
Closes #123
```

### Review-Prozess

1. **Automatische Checks**: CI/CD läuft automatisch
2. **Code Review**: Maintainer prüfen den Code
3. **Feedback**: Änderungen werden diskutiert
4. **Approval**: Mindestens 1 Approval erforderlich
5. **Merge**: Wird von Maintainer durchgeführt

### Nach dem Merge

- Branch wird automatisch gelöscht
- Issue wird geschlossen (wenn mit `Closes #` verknüpft)
- Sie werden im CHANGELOG erwähnt (falls vorhanden)

---

## Issue-Richtlinien

### Bug-Reports

Verwenden Sie die [Bug-Report-Vorlage](.github/ISSUE_TEMPLATE/bug_report.md):

**Erforderliche Informationen**:
- ✅ Beschreibung des Bugs
- ✅ Schritte zur Reproduktion
- ✅ Erwartetes Verhalten
- ✅ Aktuelles Verhalten
- ✅ System-Informationen (OS, Python-Version, etc.)
- ✅ Logs/Screenshots

**Titel-Format**: `Bug: <Kurzbeschreibung>`

### Feature-Requests

Verwenden Sie die [Feature-Request-Vorlage](.github/ISSUE_TEMPLATE/feature_request.md):

**Erforderliche Informationen**:
- ✅ Problem-Beschreibung
- ✅ Vorgeschlagene Lösung
- ✅ Alternativen
- ✅ Nutzen für die Community

**Titel-Format**: `Feature: <Kurzbeschreibung>`

### Fragen

Für Fragen nutzen Sie:
- **GitHub Discussions** (bevorzugt)
- **Issues** mit Label `question`

**Titel-Format**: `Question: <Ihre Frage>`

---

## Versioning

Wir folgen [Semantic Versioning](https://semver.org/) (SemVer):

- **MAJOR**: Breaking Changes
- **MINOR**: Neue Features (backward-compatible)
- **PATCH**: Bug-Fixes (backward-compatible)

Beispiel: `v1.2.3`

---

## Lizenz

Durch Beitragen zum Projekt stimmen Sie zu, dass Ihre Beiträge unter der [MIT-Lizenz](LICENSE) lizenziert werden.

---

## Kommunikation

### Sprache

- **Deutsch** für User-facing Dokumentation
- **Englisch** für Code-Kommentare und technische Docs (beides akzeptiert)

### Kanäle

- **GitHub Issues**: Bug-Reports, Feature-Requests
- **GitHub Discussions**: Allgemeine Fragen, Diskussionen
- **Pull Requests**: Code-Beiträge
- **E-Mail**: t.braun@feuerwehr-willingshausen.de (für private Angelegenheiten)

---

## Hilfe bekommen

**Für Contributors**:
- Lesen Sie die [Dokumentation](README.md)
- Durchsuchen Sie [existierende Issues](https://github.com/TimUx/alarm-monitor/issues)
- Fragen Sie in [GitHub Discussions](https://github.com/TimUx/alarm-monitor/discussions)
- Kontaktieren Sie die Maintainer

**Für Maintainer**:
- Reagieren Sie zeitnah auf Issues/PRs (Ziel: 48h)
- Seien Sie konstruktiv im Feedback
- Dokumentieren Sie Entscheidungen
- Danken Sie Contributors für ihre Arbeit

---

## Vielen Dank!

Jeder Beitrag, ob groß oder klein, wird geschätzt. Gemeinsam machen wir den Alarm Monitor besser! 🚒

---

<div align="center">

**Fragen? Öffnen Sie ein [Issue](https://github.com/TimUx/alarm-monitor/issues/new) oder [Discussion](https://github.com/TimUx/alarm-monitor/discussions)**

[⬆ Zurück nach oben](#-contributing-to-alarm-monitor)

</div>
