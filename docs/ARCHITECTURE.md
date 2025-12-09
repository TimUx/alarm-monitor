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
- **Stateless**: Services sind zustandslos und können einfach repliziert werden
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
│                   │                                                 │
└───────────────────┼─────────────────────────────────────────────────┘
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
        └─▶ Rendering im Browser

17. Teilnehmerrückmeldungen (optional)
        ├─▶ JavaScript startet Polling
        ├─▶ Alle 10s: GET /api/emergencies/{id}/participants
        ├─▶ Messenger liefert Teilnehmerliste
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
    └──▶ GET /api/emergencies/{emergency_id}/participants
         │
         └──▶ alarm-messenger
              └──▶ Rückgabe: { participants: [...] }
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
- REST-API Endpunkte
- Template-Rendering
- Error-Handling
- Health-Check

#### `config.py` – Konfiguration
- Environment-Variable-Parsing
- Default-Werte
- Validation

#### `storage.py` – Datenhaltung
```python
class AlarmStore:
    def __init__(self, history_file: str):
        self.current_alarm = None
        self.history = []
        self.history_file = history_file
    
    def store_alarm(self, alarm: dict) -> bool:
        """Speichert Alarm, wenn nicht Duplikat"""
    
    def has_incident_number(self, incident_number: str) -> bool:
        """Prüft auf Duplikat"""
    
    def get_current_alarm(self) -> Optional[dict]:
        """Gibt aktuellen Alarm zurück"""
    
    def get_history(self, limit: int = 100) -> list:
        """Gibt Historie zurück"""
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

#### `messenger.py` – Messenger-Integration
```python
class MessengerClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.api_key = api_key
        self.emergency_cache = {}
    
    def cache_emergency_id(
        self,
        incident_number: str,
        emergency_id: str
    ) -> None:
        """Cached emergency_id für Rückmeldungsabfrage"""
    
    def fetch_participants(
        self,
        incident_number: str
    ) -> list:
        """Ruft Teilnehmerliste vom Messenger ab"""
```

**Datenpersistenz**:
```json
// instance/alarm_history.json
{
  "current": { ... },
  "history": [
    {
      "incident_number": "2024-001",
      "timestamp": "2024-01-01T12:00:00",
      "keyword": "F3Y",
      "description": "Brand",
      ...
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
  "keyword": "F3Y",
  "keyword_sub": "Brand",
  "timestamp": "2024-01-01T12:00:00",
  "description": "Brand in Wohngebäude",
  "remarks": "Mehrere Anrufer",
  "location": "Musterstraße 1",
  "city": "Musterstadt",
  "district": "Nordviertel",
  "latitude": 51.2345,
  "longitude": 9.8765,
  "object": "Wohnhaus",
  "sub_object": "Erdgeschoss",
  "location_note": "Zufahrt über Ringstraße",
  "resources": [
    {
      "name": "LF Musterstadt 1",
      "dispatched_at": "2024-01-01T12:01:00"
    }
  ],
  "fme_resources": [...],
  "tme_resources": [...],
  "dispatch_group_codes": ["WIL26", "WIL41"]
}
```

**Response**:
```json
{
  "success": true,
  "message": "Alarm processed successfully"
}
```

**Fehlercodes**:
- `400` – Validation Error (z.B. fehlende Pflichtfelder)
- `401` – Invalid API Key
- `409` – Duplicate (Alarm bereits vorhanden)
- `500` – Internal Server Error

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
  "keyword_sub": str,          # ESTICHWORT_2

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

**API-Keys**:
- Alle API-Endpunkte sind durch API-Keys geschützt
- Keys werden im `X-API-Key` Header übermittelt
- Mindestlänge: 32 Zeichen (empfohlen: `openssl rand -hex 32`)

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
- Stateless Design erlaubt Load Balancing
- Mehrere Instanzen hinter Reverse Proxy
- Gemeinsamer Zugriff auf History-File (z.B. via NFS)

```yaml
# compose.yaml (Beispiel)
services:
  alarm-monitor-1:
    build: .
    volumes:
      - shared-history:/app/instance
  
  alarm-monitor-2:
    build: .
    volumes:
      - shared-history:/app/instance
  
  nginx:
    image: nginx
    depends_on:
      - alarm-monitor-1
      - alarm-monitor-2

volumes:
  shared-history:
```

### Performance-Optimierung

**Caching**:
- Geocoding-Ergebnisse cachen
- Weather-Daten cachen (TTL: 10 Minuten)
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
3. **Eingeschränktes Monitoring**: Keine eingebauten Metriken
4. **Keine Offline-Fähigkeit**: Clients benötigen permanente Netzwerkverbindung

### Geplante Verbesserungen

- [ ] Migration zu relationaler Datenbank (SQLite/PostgreSQL)
- [ ] Benutzerverwaltung und Zugriffsrechte
- [ ] WebSocket für Echtzeit-Updates (aktuell Polling)
- [ ] Progressive Web App (PWA) für Offline-Nutzung
- [ ] Prometheus-Metriken Export
- [ ] Automatische Tests (CI/CD)
- [ ] API-Versionierung

---

<div align="center">

**[⬆ Zurück nach oben](#-systemarchitektur--alarm-monitor)**

</div>
