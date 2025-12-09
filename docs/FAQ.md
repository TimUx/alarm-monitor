# ❓ Häufig gestellte Fragen (FAQ)

Antworten auf die häufigsten Fragen zum Alarm Monitor System.

---

## Inhaltsverzeichnis

- [Allgemein](#allgemein)
- [Installation & Setup](#installation--setup)
- [Konfiguration](#konfiguration)
- [Betrieb](#betrieb)
- [Integration](#integration)
- [Fehlerbehebung](#fehlerbehebung)
- [Sicherheit](#sicherheit)
- [Erweiterte Themen](#erweiterte-themen)

---

## Allgemein

### Was ist der Alarm Monitor?

Der Alarm Monitor ist ein webbasiertes Dashboard-System zur automatischen Verarbeitung und Darstellung von Feuerwehr-Alarmen. Es besteht aus drei Komponenten:
- **alarm-mail**: Überwacht IMAP-Postfach und parst Alarm-E-Mails
- **alarm-monitor**: Dashboard und Datenverarbeitung
- **alarm-messenger** (optional): Mobile Push-Benachrichtigungen

### Für wen ist das System geeignet?

Das System ist ideal für:
- Freiwillige Feuerwehren
- Werkfeuerwehren
- Rettungsorganisationen
- Jede Organisation, die E-Mail-basierte Alarmierung nutzt

### Welche Hardware benötige ich?

**Minimal**:
- Raspberry Pi 3 oder besser (als Server)
- Beliebige Geräte mit Webbrowser (als Clients)

**Empfohlen**:
- Raspberry Pi 4 mit 2+ GB RAM oder Mini-PC
- Dedizierte Displays für Kiosk-Modus
- Unterbrechungsfreie Stromversorgung (USV)

### Was kostet das System?

Das System ist **kostenlos** und Open Source (MIT-Lizenz). Sie benötigen nur:
- Hardware (Raspberry Pi, Displays, etc.)
- Internet-Verbindung
- IMAP-Postfach (meist bereits vorhanden)

Optionale Kosten:
- OpenRouteService API-Key für Navigation (~5€/Monat für 500 Anfragen/Tag)

---

## Installation & Setup

### Kann ich das System ohne Docker betreiben?

Ja! Es gibt zwei Installationsmethoden:
1. **Docker** (empfohlen) – Einfacher und isoliert
2. **Native Python-Installation** – Mehr Kontrolle, aufwändiger

Siehe [Quick Start Guide](QUICK_START.md) für beide Varianten.

### Wie lange dauert die Installation?

**Erste Installation**: 15-30 Minuten  
**Mit Erfahrung**: 5-10 Minuten

### Kann ich alle drei Services auf einem Gerät betreiben?

Ja! Ein Raspberry Pi 4 mit 2+ GB RAM kann problemlos alle drei Services hosten:
- alarm-mail
- alarm-monitor
- alarm-messenger

### Benötige ich einen Domainnamen?

**Nein**, wenn Sie nur im lokalen Netzwerk arbeiten. Zugriff erfolgt dann über IP-Adresse:
```
http://192.168.1.100:8000
```

**Ja**, wenn Sie HTTPS nutzen möchten oder von extern zugreifen wollen (nicht empfohlen für Sicherheitsgründe).

### Läuft das System auf Windows?

Ja, aber Linux (Debian/Ubuntu/Raspberry Pi OS) ist stark empfohlen. Windows-Installation:
1. Docker Desktop installieren
2. Repository klonen
3. `docker compose up -d` ausführen

---

## Konfiguration

### Wie generiere ich einen sicheren API-Key?

```bash
openssl rand -hex 32
```

Das erzeugt einen 64-Zeichen langen Key. Speichern Sie diesen sicher!

### Muss ich für jeden Service einen eigenen API-Key verwenden?

**Nein**! Der API-Key für die Kommunikation zwischen alarm-mail und alarm-monitor muss **identisch** sein:
- `ALARM_MAIL_MONITOR_API_KEY` (in alarm-mail)
- `ALARM_DASHBOARD_API_KEY` (in alarm-monitor)

Für alarm-messenger verwenden Sie einen **separaten** API-Key.

### Wie aktiviere ich die Gruppenfilterung?

Setzen Sie die TME-Codes in der `.env`-Datei:
```bash
ALARM_DASHBOARD_GRUPPEN=WIL26,WIL41,WIL52
```

**Leer lassen** = Alle Alarme werden angezeigt  
**Mit Codes** = Nur Alarme mit diesen TME-Codes werden angezeigt

### Wie ändere ich die Anzeigedauer eines Alarms?

Standard ist 30 Minuten. Ändern via `.env`:
```bash
ALARM_DASHBOARD_DISPLAY_DURATION_MINUTES=45
```

### Wie kann ich mein Feuerwehr-Wappen einbinden?

1. Wappen als PNG mit transparentem Hintergrund vorbereiten
2. Datei ersetzen:
```bash
cp mein-wappen.png alarm_dashboard/static/img/crest.png
```
3. Container neu starten:
```bash
docker compose restart
```

### Wie ändere ich die Farben des Dashboards?

Bearbeiten Sie die CSS-Variablen in `alarm_dashboard/static/css/dashboard.css`:
```css
:root {
  --accent: #e74c3c;      /* Hauptfarbe */
  --accent-dark: #c0392b;
  --background: #1a1a1a;
}
```

---

## Betrieb

### Wie oft prüft alarm-mail das Postfach?

Standard: Alle 60 Sekunden. Ändern via `.env`:
```bash
ALARM_MAIL_POLL_INTERVAL=30  # in Sekunden
```

**Hinweis**: Zu kurze Intervalle können vom IMAP-Server blockiert werden!

### Werden Alarme automatisch gelöscht?

**Nein**, alle Alarme werden dauerhaft in der Historie gespeichert. Sie können alte Alarme manuell löschen:

```bash
# Historie-Datei bearbeiten
nano ~/alarm-monitor/instance/alarm_history.json
```

Oder programmatisch via API (zukünftiges Feature).

### Wie kann ich die Historie exportieren?

Die Historie liegt als JSON-Datei vor:
```bash
# Datei liegt hier:
~/alarm-monitor/instance/alarm_history.json

# Kopieren/Sichern:
cp ~/alarm-monitor/instance/alarm_history.json ~/backup/
```

### Kann ich das Dashboard auf mehreren Displays gleichzeitig anzeigen?

**Ja!** Öffnen Sie einfach die URL auf allen gewünschten Geräten:
- Desktop: `http://server-ip:8000/`
- Mobile: `http://server-ip:8000/mobile`
- Kiosk: `http://server-ip:8000/` im Vollbildmodus

### Wie viele Clients kann das System gleichzeitig bedienen?

Ein Raspberry Pi 4 kann problemlos **10-20 Clients** gleichzeitig bedienen. Bei mehr Clients:
- Verwenden Sie einen stärkeren Server
- Oder skalieren Sie horizontal (mehrere alarm-monitor Instanzen hinter Load Balancer)

### Wie kann ich das Dashboard automatisch aktualisieren lassen?

Das Dashboard aktualisiert sich **automatisch**:
- Alarm-Status: Alle 5 Sekunden
- Teilnehmerrückmeldungen: Alle 10 Sekunden (wenn aktiv)
- Wetter: Bei jedem neuen Alarm

Keine manuelle Aktualisierung nötig!

---

## Integration

### Ist der alarm-messenger zwingend erforderlich?

**Nein!** Der alarm-messenger ist **optional**. Ohne ihn funktioniert das System vollständig, zeigt aber keine Teilnehmerrückmeldungen an.

### Wie verbinde ich alarm-mail mit alarm-monitor?

In der `.env`-Datei von alarm-mail:
```bash
ALARM_MAIL_MONITOR_URL=http://alarm-monitor:8000
ALARM_MAIL_MONITOR_API_KEY=<derselbe-key-wie-im-monitor>
```

**Wichtig**: Beide API-Keys müssen identisch sein!

### Kann ich mehrere alarm-mail Services mit einem alarm-monitor verbinden?

**Ja!** Mehrere alarm-mail Instanzen können Alarme an denselben alarm-monitor senden. Nützlich für:
- Mehrere IMAP-Postfächer
- Verschiedene Leitstellen
- Redundanz

### Welches E-Mail-Format wird unterstützt?

Das System erwartet Alarm-E-Mails mit XML-Inhalt im Format:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<INCIDENT>
  <STICHWORT>F3Y</STICHWORT>
  <ENR>2024-001</ENR>
  ...
</INCIDENT>
```

Siehe [README.md](../README.md) für vollständiges Beispiel.

### Kann ich das System mit anderen Leitstellen-Systemen verwenden?

Ja, wenn die Leitstelle E-Mails mit strukturierten Daten sendet. Falls das Format abweicht:
1. Passen Sie den Parser in alarm-mail an
2. Oder erstellen Sie einen eigenen Parser

### Funktioniert das System mit SMS-Alarmierung?

**Nicht direkt**. Aber Sie können:
1. SMS-zu-E-Mail-Gateway nutzen
2. Oder eigenen SMS-Parser entwickeln und via API an alarm-monitor senden

---

## Fehlerbehebung

### Dashboard zeigt "Verbindung fehlgeschlagen"

**Ursachen**:
1. alarm-monitor Service läuft nicht
2. Falsche IP-Adresse/Port
3. Firewall blockiert Port 8000

**Lösung**:
```bash
# Service-Status prüfen
docker compose ps
docker compose logs -f

# Netzwerk testen
curl http://localhost:8000/health
```

### Alarme werden nicht angezeigt

**Ursachen**:
1. API-Keys stimmen nicht überein
2. Gruppenfilter blockiert Alarm
3. Duplikat (Alarm bereits vorhanden)

**Lösung**:
```bash
# API-Keys vergleichen
grep ALARM_DASHBOARD_API_KEY ~/alarm-monitor/.env
grep ALARM_MAIL_MONITOR_API_KEY ~/alarm-mail/.env

# Logs prüfen
docker compose logs -f | grep -i error

# Testalarm senden
curl -X POST http://localhost:8000/api/alarm \
  -H "X-API-Key: <ihr-key>" \
  -H "Content-Type: application/json" \
  -d '{"incident_number":"TEST-001","keyword":"Test"}'
```

### Karte wird nicht angezeigt

**Ursachen**:
1. Keine Internet-Verbindung
2. JavaScript-Fehler im Browser
3. Fehlende Koordinaten

**Lösung**:
```bash
# OpenStreetMap erreichbar?
ping tile.openstreetmap.org

# Browser-Konsole öffnen (F12)
# → JavaScript-Fehler prüfen

# Koordinaten im Alarm prüfen
curl http://localhost:8000/api/alarm | jq '.alarm.latitude'
```

### Geokodierung schlägt fehl

**Ursachen**:
1. Nominatim nicht erreichbar
2. Adresse nicht gefunden
3. Rate-Limit überschritten

**Lösung**:
```bash
# Nominatim-API testen
curl "https://nominatim.openstreetmap.org/search?q=Berlin&format=json"

# Eigene Nominatim-Instanz verwenden (empfohlen für Produktion):
ALARM_DASHBOARD_NOMINATIM_URL=http://eigener-nominatim-server/search
```

### Wetterdaten fehlen

**Ursachen**:
1. Open-Meteo API nicht erreichbar
2. Ungültige Koordinaten

**Lösung**:
```bash
# Open-Meteo API testen
curl "https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current_weather=true"

# Koordinaten prüfen
# Latitude: -90 bis 90
# Longitude: -180 bis 180
```

### Container startet nicht

**Ursachen**:
1. Port bereits belegt
2. Fehler in .env-Datei
3. Docker-Probleme

**Lösung**:
```bash
# Port-Belegung prüfen
sudo netstat -tulpn | grep 8000

# .env-Syntax prüfen
cat .env | grep -v '^#' | grep -v '^$'

# Docker neu starten
sudo systemctl restart docker
```

---

## Sicherheit

### Ist das System sicher?

Ja, wenn Sie die **Best Practices** befolgen:
- ✅ API-Keys mit 32+ Zeichen
- ✅ Nur im lokalen Netzwerk betreiben
- ✅ Keine Portweiterleitung ins Internet
- ✅ HTTPS für externe Zugriffe (falls nötig)
- ✅ Regelmäßige Updates

### Sollte ich das Dashboard ins Internet stellen?

**Nein!** Das Dashboard sollte **nur im lokalen Netzwerk** erreichbar sein:
- Alarm-Daten sind sensibel
- Keine Benutzerauthentifizierung implementiert
- Sicherheitsrisiko bei öffentlichem Zugang

**Ausnahme**: Mit Reverse-Proxy, HTTPS und Authentifizierung (z.B. Nginx + Basic Auth).

### Wie sichere ich den API-Endpunkt ab?

Der `/api/alarm` Endpunkt ist durch den API-Key geschützt. Zusätzliche Maßnahmen:
1. **Firewall**: Nur alarm-mail darf zugreifen
2. **Docker-Netzwerk**: Interne Kommunikation ohne externen Port
3. **API-Key Rotation**: Regelmäßig ändern

```yaml
# compose.yaml - Intern ohne Port-Mapping
services:
  alarm-monitor:
    # KEIN ports-Mapping für API
    # Nur für Dashboard:
    ports:
      - "8000:8000"
```

### Wie schütze ich die Historie-Datei?

```bash
# Dateiberechtigungen setzen
chmod 600 ~/alarm-monitor/instance/alarm_history.json

# Regelmäßige Backups (verschlüsselt!)
tar -czf - instance/ | gpg -c > backup.tar.gz.gpg
```

### Werden Passwörter sicher gespeichert?

Ja, in `.env`-Dateien. **Niemals**:
- `.env` in Git committen
- `.env` per E-Mail versenden
- `.env` öffentlich zugänglich machen

`.gitignore` sorgt dafür, dass `.env` nicht committed wird.

---

## Erweiterte Themen

### Kann ich eine Datenbank statt JSON verwenden?

Aktuell: **Nein** (JSON-Datei only).  
**Geplant**: Migration zu SQLite/PostgreSQL in zukünftigen Versionen.

Workaround: Eigene Anpassung in `storage.py` möglich.

### Wie kann ich das System horizontal skalieren?

Für größere Installationen:

```yaml
# compose.yaml
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
    ports:
      - "8000:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf

volumes:
  shared-history:
```

### Wie integriere ich Prometheus-Monitoring?

Aktuell nicht nativ unterstützt. Geplant für zukünftige Versionen.

Workaround: Externes Monitoring via:
- Health-Check Endpunkt (`/health`)
- Log-Parsing
- Response-Time-Monitoring

### Kann ich WebSockets statt Polling verwenden?

Aktuell: **Nein** (HTTP Polling only).  
**Geplant**: WebSocket-Support für Echtzeit-Updates.

### Wie kann ich zu älteren Versionen zurückkehren?

```bash
# Git-Tag anzeigen
git tag

# Zu Version wechseln
git checkout v1.0.0

# Container neu bauen
docker compose up --build -d
```

### Gibt es eine API-Dokumentation?

Ja, siehe [README.md](../README.md) Abschnitt "API-Endpunkte".

Für OpenAPI/Swagger-Dokumentation: Geplant für zukünftige Versionen.

### Kann ich eigene Widgets hinzufügen?

Ja! Das Dashboard ist modular aufgebaut:
1. Template bearbeiten: `alarm_dashboard/templates/dashboard.html`
2. CSS anpassen: `alarm_dashboard/static/css/dashboard.css`
3. JavaScript erweitern: `alarm_dashboard/static/js/dashboard.js`

Beispiel: Eigenes Widget für Hydranten-Standorte.

### Wie aktiviere ich Debug-Logging?

```bash
# In .env hinzufügen:
FLASK_ENV=development
FLASK_DEBUG=1

# Oder beim Start:
docker compose up --build
# Logs werden ausführlicher
```

**Achtung**: Nicht für Produktion nutzen!

---

## Weitere Hilfe benötigt?

**Dokumentation**:
- [README.md](../README.md) – Vollständige Dokumentation
- [Quick Start Guide](QUICK_START.md) – Schnelleinstieg
- [Betriebshandbuch](../Betriebshandbuch.md) – Ausführliche Anleitung
- [Architecture](ARCHITECTURE.md) – Technische Details

**Community**:
- **GitHub Issues**: [github.com/TimUx/alarm-monitor/issues](https://github.com/TimUx/alarm-monitor/issues)
- **E-Mail**: t.braun@feuerwehr-willingshausen.de

---

<div align="center">

**Ihre Frage wurde nicht beantwortet?**  
[Öffnen Sie ein Issue auf GitHub](https://github.com/TimUx/alarm-monitor/issues/new) 

[⬆ Zurück nach oben](#-häufig-gestellte-fragen-faq)

</div>
