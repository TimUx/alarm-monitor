# 🏗️ Systemarchitektur – Alarm Monitor

Dieses Dokument beschreibt die technische Architektur des Feuerwehr Alarm Monitor Systems und erklärt das Zusammenspiel der einzelnen Komponenten.

---

## Inhaltsverzeichnis

- [Überblick](#überblick)
- [Komponentendiagramm](#komponentendiagramm)
- [Datenfluss](#datenfluss)
- [Komponenten-Details](#komponenten-details)
- [Schnittstellen](#schnittstellen)
- [Datenmodell](#datenmodell)
- [Sicherheitsarchitektur](#sicherheitsarchitektur)
- [Skalierung & Performance](#skalierung--performance)

---

## Überblick

Das Alarm Monitor System folgt einer **Microservice-Architektur** mit lose gekoppelten Komponenten:

1. **alarm-mail** – E-Mail-Überwachung und Parsing (externes Repository)
2. **alarm-monitor** – Dashboard und Datenverarbeitung (dieses Repository)
3. **alarm-messenger** – Push-Benachrichtigungen und Rückmeldungen (optional, externes Repository)

Jede Komponente kann unabhängig betrieben, skaliert und aktualisiert werden.

### Design-Prinzipien

- **Separation of Concerns**: Jede Komponente hat eine klar definierte Verantwortlichkeit
- **Fail-Safe**: Ausfall einer Komponente beeinträchtigt nicht die Kernfunktion
- **API-First**: Alle Komponenten kommunizieren über REST-APIs
- **Single-Worker**: Der alarm-monitor nutzt In-Process-State (AlarmStore, SSE-Subscriber-Liste, WeatherCache, WarningsCache) und muss mit einem einzigen Gunicorn-Worker betrieben werden
- **Observable**: Ausführliches Logging für Monitoring und Debugging

---

## Komponentendiagramm

```
┌────────────────────────────────────────────────────────────────────┐
│                         EXTERNE SYSTEME                             │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │ IMAP-Server     │    │ Nominatim    │    │ Open-Meteo   │     │
│  │ (Leitstelle)    │    │ (OSM)        │    │ (Wetter)     │     │
│  └────────┬────────┘    └──────┬───────┘    └──────┬───────┘     │
│           │                    │                    │              │
│  ┌────────▼────────┐    ┌────────▼───────┐                          │
│  │ DWD WarnWetter  │    │ DWD Warnkarten │                          │
│  │ (Unwetter)      │    │ (Bundesland)   │                          │
│  └─────────────────┘    └────────────────┘                          │
│           │                    │                    │              │
└───────────┼────────────────────┼────────────────────┼──────────────┘
            │                    │                    │
            │ IMAP               │ HTTPS              │ HTTPS
            │                    │                    │
┌───────────▼────────────────────────────────────────────────────────┐
│                      BACKEND-KOMPONENTEN                            │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │  alarm-mail Service (Microservice 1)                     │     │
│  │  ┌────────────────────────────────────────────────────┐  │     │
│  │  │ IMAP Client  →  XML Parser  →  Validator          │  │     │
│  │  └────────────────────────────────────────────────────┘  │     │
│  │         │                                                 │     │
│  │         │ REST API Calls                                 │     │
│  │         ├──────────────┬──────────────────────────┐      │     │
│  └─────────┼──────────────┼──────────────────────────┼──────┘     │
│            │              │                          │             │
│            │              │                          │             │
│  ┌─────────▼──────────────▼─────────────┐   ┌───────▼─────────┐  │
│  │  alarm-monitor (Microservice 2)      │   │ alarm-messenger │  │
│  │  ┌─────────────────────────────────┐ │   │  (Optional)     │  │
│  │  │ REST API  (/api/alarm)          │ │   │                 │  │
│  │  │   │                              │ │   │ - Push Service  │  │
│  │  │   ├─▶ Duplicate Check            │ │   │ - Device Mgmt  │  │
│  │  │   ├─▶ Group Filter               │ │   │ - Participant  │  │
│  │  │   ├─▶ Geocoding (if needed)      │ │   │   Responses    │  │
│  │  │   ├─▶ Weather Fetch               │ │   │                 │  │
│  │  │   ├─▶ DWD Warnings Fetch (Idle)   │ │   │                 │  │
│  │  │   ├─▶ Storage (JSON)              │ │   └─────────────────┘  │
│  │  │   └─▶ Messenger Notification     │ │            │            │
│  │  │                                   │ │            │            │
│  │  │ Flask Application                 │ │◀───────────┘            │
│  │  │   ├─▶ Dashboard Views             │ │  Participant           │
│  │  │   ├─▶ Mobile Views                │ │  Responses             │
│  │  │   ├─▶ History Views               │ │  (Polling)             │
│  │  │   └─▶ Navigation Views            │ │                        │
│  │  └─────────────────────────────────┘ │                        │
│  └────────────────┬───────────────────────┘                        │
│                   │  ▲ ntfy.sh Polling (optional)                  │
└───────────────────┼──┼──────────────────────────────────────────────┘
                    │  │
                    │  └───── ntfy.sh Topic (https://ntfy.sh/...)
                    │
                    │ HTTP/HTTPS (Web Interface)
                    │
┌───────────────────▼─────────────────────────────────────────────────┐
│                       CLIENT-KOMPONENTEN                             │
├────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │ Desktop     │  │ Mobile      │  │ Tablet      │  │ Kiosk    │ │
│  │ Browser     │  │ Browser     │  │ Browser     │  │ Display  │ │
│  │             │  │             │  │             │  │          │ │
│  │ - Dashboard │  │ - Mobile    │  │ - Dashboard │  │ - Kiosk  │ │
│  │ - History   │  │   View      │  │ - Mobile    │  │   Mode   │ │
│  │ - Navi      │  │ - Quick     │  │   View      │  │ - Auto   │ │
│  │             │  │   Navi      │  │             │  │   Reload │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └──────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Datenfluss

### 1. Alarm-Empfang und Verarbeitung

```
┌──────────────────────────────────────────────────────────────────┐
│ PHASE 1: E-Mail-Empfang                                          │
└──────────────────────────────────────────────────────────────────┘

1. Leitstelle sendet Alarm-E-Mail mit XML-Anhang
       ↓
2. E-Mail landet im IMAP-Postfach
       ↓
3. alarm-mail prüft Postfach (alle 60s)
       ↓
4. Neue E-Mail wird erkannt

┌──────────────────────────────────────────────────────────────────┐
│ PHASE 2: Parsing und Validierung                                 │
└──────────────────────────────────────────────────────────────────┘

5. XML-Inhalt wird extrahiert
       ↓
6. XML wird geparst und validiert
       ↓
7. Felder werden gemapped:
   - ENR → incident_number
   - ESTICHWORT_1 → keyword
   - KOORDINATE_LAT/LON → latitude/longitude
   - etc.
       ↓
8. JSON-Payload wird erstellt

┌──────────────────────────────────────────────────────────────────┐
│ PHASE 3: Verteilung                                              │
└──────────────────────────────────────────────────────────────────┘

9. alarm-mail sendet parallel an:
   ├─▶ alarm-monitor (POST /api/alarm)
   └─▶ alarm-messenger (POST /api/emergencies) [optional]

┌──────────────────────────────────────────────────────────────────┐
│ PHASE 4: Verarbeitung in alarm-monitor                          │
└──────────────────────────────────────────────────────────────────┘

10. Empfang und Validierung
        ├─▶ API-Key prüfen
        ├─▶ JSON-Schema validieren
        └─▶ Incident-Number prüfen

11. Duplikatsprüfung
        ├─▶ ENR bereits in Historie?
        ├─▶ Ja → Alarm verwerfen
        └─▶ Nein → Weiter zu 12

12. Gruppenfilter (optional)
        ├─▶ GRUPPEN konfiguriert?
        ├─▶ TME-Codes vorhanden?
        ├─▶ Übereinstimmung?
        └─▶ Nein → Alarm verwerfen

13. Datenanreicherung
        ├─▶ Koordinaten fehlen? → Nominatim Geocoding
        ├─▶ Wetterdaten abrufen → Open-Meteo API
        └─▶ Zeitstempel hinzufügen

14. Speicherung
        ├─▶ In Speicher (aktueller Alarm)
        ├─▶ In Historie (JSON-Datei)
        └─▶ Timestamp aktualisieren

15. Messenger-Benachrichtigung (optional)
        └─▶ emergency_id cachen für spätere Rückmeldungsabfrage

┌──────────────────────────────────────────────────────────────────┐
│ PHASE 5: Darstellung                                             │
└──────────────────────────────────────────────────────────────────┘

16. Client-Browser ruft Dashboard ab
        ├─▶ JavaScript lädt /api/alarm
        ├─▶ Server prüft: Alarm aktiv?
        ├─▶ Alarm-Ansicht ODER Idle-Ansicht
        ├─▶ Idle: letzter Einsatz links, Termine/Unwetter rechts
        └─▶ Rendering im Browser

19. Idle-Seitenpanel (nur Ruhezustand)
        ├─▶ Koordinaten aus Settings → DWD-Warnungen abrufen (Level ≥ 3)
        ├─▶ Bundesland aus Koordinaten → DWD-Warnkarten-URL
        ├─▶ Kalender konfiguriert? → 30s-Wechsel Termine ↔ Unwetter
        └─▶ Mock-Modus: simulierte Testwarnung aus Settings/ENV

17. Teilnehmerrückmeldungen (optional)
        ├─▶ JavaScript startet Polling
        ├─▶ Alle 10s: GET /api/alarm/participants/{incident_number}
        ├─▶ alarm-monitor ruft Teilnehmerliste vom Messenger ab
        └─▶ Dashboard aktualisiert Anzeige

18. Auto-Timeout
        ├─▶ Alarm älter als DISPLAY_DURATION?
        ├─▶ Ja → Wechsel zu Idle-Ansicht
        └─▶ Zeige letzten Alarm kompakt
```

### 2. Rückmeldungs-Polling (bei alarm-messenger Integration)

```
Dashboard (Browser)
    │
    │ JavaScript Timer (10s Interval)
    │
    ├──▶ GET /api/alarm
    │    └──▶ alarm-monitor prüft: Alarm aktiv?
    │         ├──▶ Ja: incident_number vorhanden
    │         │    └──▶ Messenger-URL konfiguriert?
    │         │         └──▶ Ja: Polling starten
    │         └──▶ Nein: Polling stoppen
    │
    └──▶ GET /api/alarm/participants/{incident_number}
         │
         └──▶ alarm-monitor → alarm-messenger
                   ├─▶ deviceName
                   ├─▶ response (accepted/declined)
                   ├─▶ respondedAt
                   └─▶ note
```

---

## Komponenten-Details

### alarm-mail Service

**Verantwortlichkeit**: E-Mail-Überwachung und -Verarbeitung

**Technologie**:
- Python 3.9+
- `imaplib` für IMAP-Verbindung
- `defusedxml` für sicheres XML-Parsing
- `requests` für REST-API-Calls

**Hauptfunktionen**:
- Periodisches Polling des IMAP-Postfachs
- XML-Parsing und Validierung
- Feld-Mapping zu JSON-Schema
- Parallele Benachrichtigung von alarm-monitor und alarm-messenger

**Konfiguration**:
```python
IMAP_HOST = "imap.example.com"
IMAP_PORT = 993
IMAP_USE_SSL = True
POLL_INTERVAL = 60  # Sekunden

MONITOR_URL = "http://alarm-monitor:8000"
MONITOR_API_KEY = "..."

MESSENGER_URL = "http://alarm-messenger:3000"  # Optional
MESSENGER_API_KEY = "..."  # Optional
```

**Fehlerbehandlung**:
- IMAP-Verbindungsfehler → Retry mit Backoff
- XML-Parse-Fehler → Logging, E-Mail markieren
- API-Call-Fehler → Logging, aber nicht blockierend

---

### alarm-monitor Service

**Verantwortlichkeit**: Dashboard-Anwendung und Datenhaltung

**Technologie**:
- Python 3.9+
- Flask (Web-Framework)
- Gunicorn (WSGI Server)
- JSON (Datenspeicherung)
- Leaflet.js (Kartendarstellung)

**Module**:

#### `app.py` – Flask-Anwendung
- Application Factory (`create_app()`)
- Initialisierung von AlarmStore, SettingsStore, WeatherCache, WarningsCache
- SSE-Subscriber-Verwaltung
- Rate-Limiter-Initialisierung
- CSRF-Token-Generierung für Einstellungs-Seite
- Blueprint-Registrierung (`routes/api.py` und `routes/views.py`)

#### `routes/api.py` – REST API
- `POST /api/alarm` – Alarm empfangen
- `GET /api/alarm` – Aktuellen Alarm/Idle-Status abrufen
- `GET /api/stream` – Server-Sent Events für Echtzeit-Updates
- `GET /api/alarm/participants/<nr>` – Teilnehmerrückmeldungen
- `GET /api/history` – Alarm-Historie
- `GET /api/calendar` – iCal-Termine abrufen
- `GET|POST|DELETE /api/messages` – Dashboard-Nachrichten verwalten
- `GET /api/route` – Routing-Proxy (OpenRouteService)
- `GET|POST /api/settings` – Einstellungen lesen und speichern
- `POST|DELETE /api/settings/logo` – Feuerwehr-Logo hochladen/zurücksetzen
- `GET /api/metrics` – Prometheus-Metriken

#### `routes/views.py` – HTML-Seiten
- `/` – Haupt-Dashboard (Alarm/Idle)
- `/mobile` – Mobile Ansicht
- `/history` – Einsatzhistorie
- `/navigation` – Navigationsansicht
- `/settings` – Einstellungs-Oberfläche mit Logo-Upload
- `/health` – Health-Check

#### `config.py` – Konfiguration
- Environment-Variable-Parsing
- Default-Werte
- Validation

#### `storage.py` – Datenhaltung
```python
class AlarmStore:
    def __init__(self, persistence_path: Optional[Path] = None):
        # Lädt persistierten Zustand beim Start
    
    def update(self, payload: dict) -> None:
        """Speichert neuen Alarm und fügt ihn zur Historie hinzu"""
    
    def update_enrichment(self, incident_number, coordinates, weather) -> None:
        """Aktualisiert Koordinaten und Wetterdaten eines vorhandenen Alarms"""

    def latest(self) -> Optional[dict]:
        """Gibt den zuletzt gespeicherten Alarm zurück"""
    
    def has_incident_number(self, incident_number: str) -> bool:
        """Prüft, ob Alarm mit dieser Einsatznummer bereits vorhanden ist"""
    
    def history(self, limit: int = None, offset: int = 0) -> list:
        """Gibt die Historie zurück (neueste zuerst, mit Pagination)"""
    
    def history_count(self) -> int:
        """Gibt die Gesamtzahl der gespeicherten Alarme zurück"""

class SettingsStore:
    """Persistente Speicherung von Web-UI-Einstellungen in instance/settings.json"""
    
    def get_all(self) -> dict:
        """Gibt alle gespeicherten Einstellungen zurück"""
    
    def update(self, updates: dict) -> None:
        """Speichert neue Einstellungen (überschreibt Teilmengen)"""
```

#### `geocode.py` – Geokodierung
```python
def geocode_address(
    address: str,
    nominatim_url: str
) -> Optional[tuple[float, float]]:
    """
    Sucht Koordinaten für Adresse via Nominatim
    Rückgabe: (latitude, longitude) oder None
    """
```

#### `weather.py` – Wetterabfrage
```python
def fetch_weather(
    latitude: float,
    longitude: float,
    weather_url: str,
    params: str
) -> dict:
    """
    Ruft Wetterdaten von Open-Meteo ab
    Rückgabe: { temperature, precipitation, ... }
    """
```

#### `dwd_warnings.py` – DWD-Unwetterwarnungen
```python
def fetch_severe_warnings(
    latitude: float,
    longitude: float,
    warnings_url: str
) -> dict:
    """
    Ruft amtliche Unwetterwarnungen (Stufe 3/4) vom DWD ab.
    Filtert per Point-in-Polygon auf die konfigurierten Koordinaten.
    Rückgabe: { active, items, bundesland, map_url, mock }
    """
```

#### `bundesland.py` – Bundesland-Erkennung
```python
def resolve_dwd_region(latitude: float, longitude: float) -> Optional[dict]:
    """
    Ermittelt das Bundesland für die DWD-Warnkarten-URL.
    Rückgabe: { code, name } oder None
    """
```

#### `warnings_cache.py` – DWD-Warnungs-Cache
```python
class WarningsCache:
    """
    In-Memory-Cache für DWD-Warnungen (TTL: 10 Minuten).
    Analog zu WeatherCache.
    """
```

#### `messenger.py` – Messenger-Integration
```python
class AlarmMessenger:
    def get_participants(self, incident_number: str) -> Optional[list]:
        """
        Sucht Emergency-UUID via GET /api/emergencies?emergencyNumber=...
        und ruft Teilnehmer via GET /api/emergencies/{uuid}/participants ab.
        """
```

#### `calendar_service.py` – Kalender-Integration
```python
def fetch_calendar_events(
    calendar_urls: list[str],
    max_events: int = 5
) -> list[dict]:
    """
    Ruft bevorstehende Termine aus iCal-URLs ab
    Rückgabe: Liste mit {summary, start, end, location, ...}
    """
```

#### `message_store.py` – Nachrichten-Verwaltung
```python
class MessageStore:
    def __init__(self, max_ttl_hours: int = 72, persistence_path: Optional[Path] = None):
        """In-Memory + optionale Persistenz für Dashboard-Nachrichten"""

    def add(self, text: str, ttl_minutes: int = 60) -> dict:
        """Neue Nachricht erstellen mit UUID und Ablaufzeit"""
    
    def get_active(self) -> list[dict]:
        """Alle noch aktiven (nicht abgelaufenen) Nachrichten abrufen"""
    
    def delete(self, message_id: str) -> bool:
        """Nachricht nach ID löschen"""
    
    def cleanup_expired(self) -> int:
        """Abgelaufene Nachrichten entfernen und Anzahl zurückgeben"""
```

#### `ntfy_client.py` – ntfy.sh Polling
```python
def create_ntfy_poller(
    topic_url: str,
    poll_interval: int,
    message_store: MessageStore,
    default_ttl_minutes: int
) -> threading.Thread:
    """
    Erstellt und startet einen Hintergrund-Thread der das ntfy-Topic
    regelmäßig abfragt und neue Nachrichten in den MessageStore speichert
    """
```

**Datenpersistenz**:
```json
// instance/alarm_history.json
{
  "alarm": {
    "alarm": {
      "incident_number": "2024-001",
      "keyword": "B3 - Wohnungsbrand",
      "location": "Musterstraße 1",
      ...
    },
    "coordinates": {"lat": 51.2345, "lon": 9.8765},
    "weather": {...},
    "received_at": "2024-01-01T12:00:00+00:00"
  },
  "history": [
    { ... }
  ]
}

// instance/settings.json
{
  "fire_department_name": "Feuerwehr Willingshausen",
  "default_latitude": 50.9333,
  "default_longitude": 9.3167,
  "activation_groups": ["WIL26", "WIL41"],
  "calendar_urls": ["https://..."],
  "dwd_warnings_mock": false,
  "ntfy_topic_url": "https://ntfy.sh/...",
  "ntfy_poll_interval": 60,
  "message_default_ttl_minutes": 60
}

// instance/messages.json
{
  "messages": [
    {
      "id": "uuid-...",
      "text": "Dienstbesprechung heute 19:00 Uhr!",
      "created_at": "2024-01-01T10:00:00+00:00",
      "expires_at": "2024-01-01T11:00:00+00:00"
    }
  ]
}
```

---

### alarm-messenger Service (Optional)

**Verantwortlichkeit**: Push-Benachrichtigungen und Rückmeldungen

**Technologie**:
- Node.js + Express
- Firebase Cloud Messaging (FCM)
- SQLite/PostgreSQL

**API-Endpunkte**:
```
POST /api/emergencies
  → Empfängt neuen Alarm, sendet Push-Notifications

GET /api/emergencies/{id}/participants
  → Gibt Teilnehmerrückmeldungen zurück

POST /api/devices/register
  → Registriert neues Gerät

PUT /api/emergencies/{id}/respond
  → Teilnehmer gibt Rückmeldung ab
```

Siehe [alarm-messenger Repository](https://github.com/TimUx/alarm-messenger) für Details.

---

## Schnittstellen

### API: alarm-mail → alarm-monitor

**Endpunkt**: `POST /api/alarm`

**Authentifizierung**: `X-API-Key` Header

**Request**:
```json
{
  "incident_number": "2024-001",
  "keyword": "B3 - Wohnungsbrand",
  "keyword_secondary": "Menschenleben in Gefahr",
  "subject": "Vollbrand EFH",
  "diagnosis": "Wohnungsbrand mit Menschengefährdung",
  "remark": "2 Personen im Gebäude",
  "location": "Musterstraße 1, 12345 Musterstadt",
  "latitude": 51.2345,
  "longitude": 9.8765,
  "timestamp": "2024-01-01T12:00:00+00:00",
  "timestamp_display": "01.01.2024 12:00",
  "groups": ["LF20-MST", "TLF4000-MST"],
  "dispatch_group_codes": ["MST26", "MST41"],
  "location_details": {
    "town": "Musterstadt",
    "village": "Nordviertel",
    "street": "Musterstraße 1",
    "additional": "EG links"
  }
}
```

**Response**:
```json
{"status": "ok"}
```

**Fehlercodes**:
- `400` – Validation Error (z.B. fehlende Pflichtfelder)
- `401` – Invalid API Key
- `500` – Internal Server Error

**Hinweis**: Doppelt eingehende Alarme (gleiche Einsatznummer) werden still ignoriert und geben ebenfalls `200 {"status": "ok"}` zurück.

---

### API: alarm-monitor → alarm-messenger

**Endpunkt**: `GET /api/emergencies/{emergency_id}/participants`

**Authentifizierung**: `X-API-Key` Header

**Response**:
```json
{
  "emergency_id": "abc123",
  "participants": [
    {
      "deviceId": "device-uuid-1",
      "deviceName": "Max Mustermann - iPhone",
      "response": "accepted",
      "respondedAt": "2024-01-01T12:05:30Z",
      "qualifications": ["Atemschutz", "Maschinist"],
      "roles": ["Zugführer"],
      "note": ""
    },
    {
      "deviceId": "device-uuid-2",
      "deviceName": "Erika Musterfrau - Android",
      "response": "declined",
      "respondedAt": "2024-01-01T12:06:15Z",
      "qualifications": [],
      "roles": [],
      "note": "Im Urlaub"
    }
  ]
}
```

---

## Datenmodell

### Alarm-Objekt (internes Format)

```python
{
  # Identifikation
  "incident_number": str,      # ENR aus XML
  "incident_number_full": str, # FENR aus XML
  "timestamp": str,            # ISO 8601 Zeitstempel
  "received_at": str,          # Empfangszeitpunkt

  # Stichwort
  "keyword": str,              # ESTICHWORT_1
  "keyword_secondary": str,   # ESTICHWORT_2

  # Beschreibung
  "description": str,          # DIAGNOSE
  "remarks": str,              # EO_BEMERKUNG
  "info_text": str,           # INFOTEXT
  "location_note": str,        # EOZUSATZ

  # Standort
  "location": str,             # STRASSE + HAUSNUMMER
  "city": str,                 # ORT
  "district": str,             # ORTSTEIL
  "object": str,               # OBJEKT
  "sub_object": str,           # UNTEROBJEKT
  "location_additional": str,  # ORTSZUSATZ

  # Koordinaten
  "latitude": float,           # KOORDINATE_LAT oder geocodiert
  "longitude": float,          # KOORDINATE_LON oder geocodiert
  "geocoded": bool,            # True wenn nachträglich geocodiert

  # Wetter
  "weather": {
    "temperature": float,
    "precipitation": float,
    "wind_speed": float,
    "weather_code": int,
    ...
  },

  # Ressourcen
  "resources": [               # AAO
    {
      "name": str,
      "dispatched_at": str
    }
  ],
  "fme_resources": [...],      # FME
  "tme_resources": [...],      # TME

  # Gruppen
  "dispatch_group_codes": [    # TME-Codes
    str, str, ...
  ],

  # Messenger (optional)
  "emergency_id": str          # ID im alarm-messenger System
}
```

---

## Sicherheitsarchitektur

### Authentifizierung

**Geschützte Endpunkte** (Auswahl):

| Endpunkt | Authentifizierung |
|----------|-------------------|
| `POST /api/alarm` | `X-API-Key` |
| `POST /api/messages` | `X-API-Key` |
| `POST /api/settings` | `X-Settings-Password` + `X-CSRF-Token` |
| `POST/DELETE /api/settings/logo` | `X-Settings-Password` + `X-CSRF-Token` |
| `GET /api/metrics` | `X-Metrics-Token` |

**Öffentlich lesbar** (kein API-Key): `GET /api/alarm`, `GET /api/stream`, `GET /api/history`, `GET /api/calendar`, `GET /api/messages`, `GET /api/settings`, `GET /api/logo`, `GET /health` und alle HTML-Seiten.

API-Keys werden im `X-API-Key` Header übermittelt. Empfohlen: `openssl rand -hex 32`

**Best Practices**:
- Keys niemals in Git committen
- Verwendung von `.env`-Dateien
- Regelmäßige Key-Rotation
- Unterschiedliche Keys pro Umgebung (Dev/Prod)

### Netzwerksicherheit

**Interne Kommunikation**:
- HTTP ausreichend für Docker-Netzwerk
- Verwendung von Docker-internen Hostnamen

**Externe Kommunikation**:
- HTTPS für Produktion **zwingend erforderlich**
- Reverse-Proxy (nginx, Traefik) empfohlen
- Let's Encrypt für SSL-Zertifikate

### Datensicherheit

**Sensible Daten**:
- Alarm-Daten können personenbezogene Informationen enthalten
- Historie-Datei sollte geschützt werden (Dateiberechtigungen)
- Backups verschlüsseln

**DSGVO-Konformität**:
- Regelmäßige Löschung alter Alarme erwägen
- Zugriffsbeschränkung auf autorisierte Personen
- Logging von Datenzugriffen

### Container-Sicherheit

**Non-Root-User**:
```dockerfile
# Dockerfile
RUN useradd -m -u 1000 appuser
USER appuser
```

**Read-Only-Filesystem** (optional):
```yaml
# compose.yaml
services:
  alarm-monitor:
    read_only: true
    tmpfs:
      - /tmp
```

---

## Skalierung & Performance

### Horizontale Skalierung

**alarm-monitor**:
- Der alarm-monitor nutzt **In-Process-State** (AlarmStore, SSE-Subscriber-Liste, WeatherCache, WarningsCache)
- Mehrere Instanzen oder mehrere Gunicorn-Worker würden je unabhängigen Zustand haben
- Dies würde zu verlorenen SSE-Benachrichtigungen und inkonsistenten Alarm-Anzeigen führen
- **Empfehlung**: Einen einzigen Worker mit mehreren Threads (`--workers 1 --threads 8`) verwenden

```yaml
# compose.yaml (Standard-Konfiguration – 1 Worker empfohlen)
services:
  alarm-dashboard:
    build: .
    environment:
      - ALARM_DASHBOARD_GUNICORN_WORKERS=1
      - ALARM_DASHBOARD_GUNICORN_THREADS=8
    volumes:
      - ./instance:/app/instance
```

### Performance-Optimierung

**Caching**:
- Geocoding-Ergebnisse cachen
- Weather-Daten cachen (TTL: 10 Minuten)
- DWD-Warnungen cachen (TTL: 10 Minuten)
- Static Assets cachen (Browser-Cache)

**Database** (zukünftig):
- Migration von JSON zu SQLite/PostgreSQL für bessere Performance
- Indizierung von `incident_number` und `timestamp`
- Pagination für Historie-Abfragen

**Frontend**:
- Minification von CSS/JS
- CDN für externe Libraries (Leaflet, etc.)
- Lazy Loading für Bilder

### Monitoring

**Metriken**:
- Response Times (API-Endpunkte)
- Fehlerrate
- Anzahl aktiver Alarme
- Historie-Größe

**Tools**:
- Prometheus + Grafana
- ELK-Stack für Logs
- Uptime-Monitoring (z.B. UptimeRobot)

**Health-Check**:
```bash
# Automatischer Health-Check
curl -f http://localhost:8000/health || exit 1
```

---

## Deployment-Szenarien

### Szenario 1: Kleine Feuerwehr (Single-Host)

```
┌─────────────────────────────────┐
│  Raspberry Pi / Mini-PC         │
│                                  │
│  ┌───────────────────────────┐  │
│  │  Docker Compose           │  │
│  │  ├─ alarm-mail            │  │
│  │  ├─ alarm-monitor         │  │
│  │  └─ alarm-messenger       │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
        │
        └──▶ Clients im LAN
```

### Szenario 2: Größere Feuerwehr (Multi-Host)

```
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Server 1        │  │  Server 2        │  │  Server 3        │
│  alarm-mail      │  │  alarm-monitor   │  │  alarm-messenger │
└──────────────────┘  └──────────────────┘  └──────────────────┘
        │                     │                      │
        └─────────────────────┴──────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Reverse Proxy    │
                    │  (nginx/Traefik)  │
                    └───────────────────┘
                              │
                              └──▶ Clients
```

---

## Technische Schulden & Roadmap

### Bekannte Limitierungen

1. **Datenspeicherung**: JSON-Datei nicht optimal für große Datenmengen
2. **Keine Authentifizierung**: Dashboard hat keine Benutzerverwaltung
3. **Keine Offline-Fähigkeit**: Clients benötigen permanente Netzwerkverbindung

### Geplante Verbesserungen

- [ ] Migration zu relationaler Datenbank (SQLite/PostgreSQL)
- [ ] Benutzerverwaltung und Zugriffsrechte
- [x] Echtzeit-Updates via Server-Sent Events (implementiert)
- [ ] Progressive Web App (PWA) für Offline-Nutzung
- [x] Prometheus-Metriken Export (implementiert via `/api/metrics`)
- [x] Automatische Tests (CI/CD via GitHub Actions, 80 % Coverage-Gate)
- [ ] API-Versionierung

---

<div align="center">

**[⬆ Zurück nach oben](#-systemarchitektur--alarm-monitor)**

</div>
