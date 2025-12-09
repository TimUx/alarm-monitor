# 📖 Betriebshandbuch – Feuerwehr Alarm Monitor

Dieses Betriebshandbuch beschreibt die Einrichtung, den Betrieb und die Wartung des Feuerwehr Alarm Monitors. Es richtet sich an Administratoren und technisch versierte Anwender, die das System in ihrer Feuerwehr oder Organisation betreiben möchten.

---

## Inhaltsverzeichnis

1. [Systemanforderungen](#systemanforderungen)
2. [Installation](#installation)
3. [Konfiguration](#konfiguration)
4. [Inbetriebnahme](#inbetriebnahme)
5. [Betrieb](#betrieb)
6. [Wartung](#wartung)
7. [Monitoring](#monitoring)
8. [Fehlerbehebung](#fehlerbehebung)
9. [Sicherheitshinweise](#sicherheitshinweise)
10. [Backup und Wiederherstellung](#backup-und-wiederherstellung)
11. [Performance-Optimierung](#performance-optimierung)
12. [Anhang](#anhang)

---

## Dokumentation

**Weitere Ressourcen**:
- **[README.md](README.md)** – Projekt-Überblick und Features
- **[Quick Start Guide](docs/QUICK_START.md)** – Schnelleinstieg in 15 Minuten
- **[Architecture](docs/ARCHITECTURE.md)** – Technische Systemarchitektur
- **[FAQ](docs/FAQ.md)** – Häufig gestellte Fragen
- **[Messenger-Integration](docs/MESSENGER_INTEGRATION.md)** – Push-Benachrichtigungen
- **[Contributing](CONTRIBUTING.md)** – Beiträge zum Projekt

---

## Systemanforderungen

### Server (Mindestanforderungen)

| Komponente | Anforderung |
|------------|-------------|
| CPU | 1 GHz (ARM oder x86) |
| RAM | 512 MB |
| Speicher | 1 GB freier Speicherplatz |
| Betriebssystem | Linux (Debian/Ubuntu empfohlen), Windows, macOS |
| Python | Version 3.9 oder höher |
| Netzwerk | Ethernet oder WLAN mit Internetzugang |

### Client (Anzeigegeräte)

- Beliebiger Webbrowser (Chrome, Firefox, Safari, Edge)
- Bildschirmauflösung: mindestens 1024×768 (Full HD empfohlen)
- Netzwerkverbindung zum Server

### Externe Dienste

Der alarm-monitor benötigt ausgehende Verbindungen zu:

| Dienst | URL | Port | Zweck |
|--------|-----|------|-------|
| Nominatim | nominatim.openstreetmap.org | 443 | Geokodierung |
| Open-Meteo | api.open-meteo.com | 443 | Wetterdaten |
| OpenStreetMap | tile.openstreetmap.org | 443 | Kartenkacheln |
| alarm-messenger | Konfigurierbar (optional) | 443/3000 | Teilnehmerrückmeldungen |

**Hinweis:** Der E-Mail-Abruf (IMAP) wird vom separaten **alarm-mail Service**
durchgeführt, nicht vom alarm-monitor.

---

## Installation

### Option A: Native Python-Installation

```bash
# 1. System aktualisieren
sudo apt update && sudo apt upgrade -y

# 2. Python und Abhängigkeiten installieren
sudo apt install python3 python3-venv python3-pip git -y

# 3. Repository klonen
git clone https://github.com/TimUx/alarm-monitor.git
cd alarm-monitor

# 4. Virtuelle Umgebung erstellen und aktivieren
python3 -m venv .venv
source .venv/bin/activate

# 5. Abhängigkeiten installieren
pip install -r requirements.txt
```

### Option B: Docker-Installation

```bash
# 1. Docker und Docker Compose installieren
sudo apt install docker.io docker-compose -y

# 2. Repository klonen
git clone https://github.com/TimUx/alarm-monitor.git
cd alarm-monitor

# 3. Konfiguration vorbereiten
cp .env.example .env
# .env-Datei bearbeiten (siehe Abschnitt Konfiguration)

# 4. Container bauen und starten
docker compose up --build -d
```

---

## Konfiguration

### Umgebungsvariablen

Erstellen Sie eine `.env`-Datei im Projektverzeichnis:

```bash
cp .env.example .env
```

Bearbeiten Sie die Datei mit Ihren Zugangsdaten:

```ini
# API-Key für Alarmempfang (Pflichtfeld)
# Generieren mit: openssl rand -hex 32
ALARM_DASHBOARD_API_KEY=a1b2c3d4e5f6...

# Gruppenfilter (optional, kommagetrennt)
ALARM_DASHBOARD_GRUPPEN=WIL26,WIL41

# Anzeigedauer eines Alarms in Minuten
ALARM_DASHBOARD_DISPLAY_DURATION_MINUTES=30

# Feuerwehrname für die Anzeige
ALARM_DASHBOARD_FIRE_DEPARTMENT_NAME=Feuerwehr Beispielstadt

# Standardkoordinaten für die Idle-Ansicht
ALARM_DASHBOARD_DEFAULT_LATITUDE=51.2345
ALARM_DASHBOARD_DEFAULT_LONGITUDE=9.8765
ALARM_DASHBOARD_DEFAULT_LOCATION_NAME=Feuerwehrhaus Beispielstadt

# Alarm-Messenger Integration (optional)
# ALARM_DASHBOARD_MESSENGER_SERVER_URL=https://messenger.example.com
# ALARM_DASHBOARD_MESSENGER_API_KEY=your-api-key-here
```

### Wichtige Konfigurationsparameter

| Parameter | Beschreibung | Standardwert |
|-----------|--------------|--------------|
| `API_KEY` | API-Schlüssel für Alarmempfang | (erforderlich) |
| `DISPLAY_DURATION_MINUTES` | Anzeigedauer eines Alarms | 30 |
| `GRUPPEN` | TME-Codes für Alarmfilterung | (alle) |
| `MESSENGER_SERVER_URL` | URL des Alarm-Messenger-Servers | (deaktiviert) |
| `MESSENGER_API_KEY` | API-Key für Messenger-Authentifizierung | (deaktiviert) |
| `HISTORY_FILE` | Pfad zur Historie-Datei | instance/alarm_history.json |

---

## Inbetriebnahme

### Erster Start (Native Installation)

```bash
# Virtuelle Umgebung aktivieren
source .venv/bin/activate

# Anwendung starten
flask --app alarm_dashboard.app run --host 0.0.0.0 --port 8000
```

### Erster Start (Docker)

```bash
docker compose up -d
```

### Prüfung der Funktionalität

1. **Health-Check**: Öffnen Sie `http://<server-ip>:8000/health`
   - Erwartete Antwort: `{"status": "ok"}`

2. **Dashboard**: Öffnen Sie `http://<server-ip>:8000/`
   - Die Standardansicht (Idle) sollte erscheinen

3. **Logs prüfen**:
   ```bash
   # Native
   # Ausgabe im Terminal beobachten

   # Docker
   docker compose logs -f
   ```

---


## Einrichtung des alarm-mail Service

Der alarm-monitor benötigt den **alarm-mail Service**, um Alarme zu empfangen.
Dieser Service überwacht das IMAP-Postfach und leitet Alarme weiter.

### Schnellinstallation mit Docker Compose

1. **Repository klonen**
   ```bash
   cd /home/pi  # oder ein anderes Verzeichnis
   git clone https://github.com/TimUx/alarm-mail.git
   cd alarm-mail
   ```

2. **Konfiguration erstellen**
   ```bash
   cp .env.example .env
   nano .env
   ```

   Tragen Sie folgende Werte ein:
   ```ini
   # IMAP-Konfiguration (E-Mail-Abruf)
   ALARM_MAIL_IMAP_HOST=imap.example.com
   ALARM_MAIL_IMAP_PORT=993
   ALARM_MAIL_IMAP_USE_SSL=true
   ALARM_MAIL_IMAP_USERNAME=alarm@feuerwehr.de
   ALARM_MAIL_IMAP_PASSWORD=IhrSicheresPasswort
   ALARM_MAIL_IMAP_MAILBOX=INBOX
   ALARM_MAIL_POLL_INTERVAL=60
   
   # alarm-monitor Integration
   ALARM_MAIL_MONITOR_URL=http://localhost:8000
   ALARM_MAIL_MONITOR_API_KEY=<der-api-key-aus-alarm-monitor>
   
   # Optional: alarm-messenger Integration
   # ALARM_MAIL_MESSENGER_URL=http://localhost:3000
   # ALARM_MAIL_MESSENGER_API_KEY=<messenger-api-key>
   ```

3. **Service starten**
   ```bash
   docker compose up -d
   ```

4. **Logs prüfen**
   ```bash
   docker compose logs -f
   ```

### Systemd-Service für alarm-mail

Für eine native Installation ohne Docker:

```bash
sudo nano /etc/systemd/system/alarm-mail.service
```

Inhalt:
```ini
[Unit]
Description=Alarm Mail Service
After=network.target alarm-dashboard.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/alarm-mail
Environment="PATH=/home/pi/alarm-mail/.venv/bin"
ExecStart=/home/pi/alarm-mail/.venv/bin/python -m alarm_mail.app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Service aktivieren:
```bash
sudo systemctl daemon-reload
sudo systemctl enable alarm-mail
sudo systemctl start alarm-mail
```

---

## Betrieb

### Autostart einrichten (systemd)

Erstellen Sie eine Service-Datei:

```bash
sudo nano /etc/systemd/system/alarm-dashboard.service
```

Inhalt:

```ini
[Unit]
Description=Feuerwehr Alarm Dashboard
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/alarm-monitor
Environment="PATH=/home/pi/alarm-monitor/.venv/bin"
ExecStart=/home/pi/alarm-monitor/.venv/bin/gunicorn \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --threads 4 \
    --worker-class gthread \
    alarm_dashboard.app:create_app()
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Service aktivieren:

```bash
sudo systemctl daemon-reload
sudo systemctl enable alarm-dashboard
sudo systemctl start alarm-dashboard
```

### Kiosk-Modus einrichten (Raspberry Pi)

Für Anzeigegeräte im Vollbildmodus:

```bash
# Autostart-Skript erstellen
mkdir -p ~/.config/autostart

cat > ~/.config/autostart/kiosk.desktop << EOF
[Desktop Entry]
Type=Application
Name=Alarm Dashboard Kiosk
Exec=chromium-browser --kiosk --noerrdialogs --disable-infobars http://server-ip:8000
EOF
```

### API-Endpunkte

| Endpunkt | Methode | Beschreibung |
|----------|---------|--------------|
| `/` | GET | Haupt-Dashboard |
| `/mobile` | GET | Mobile Ansicht |
| `/history` | GET | Einsatzhistorie (HTML) |
| `/health` | GET | Health-Check |
| `/api/alarm` | GET | Aktueller Alarm (JSON) |
| `/api/history` | GET | Historie (JSON) |
| `/api/mobile/alarm` | GET | Alarm für Mobile (JSON) |

---

## Wartung

### Regelmäßige Aufgaben

| Aufgabe | Intervall | Beschreibung |
|---------|-----------|--------------|
| Log-Rotation | Wöchentlich | Alte Logs archivieren/löschen |
| System-Updates | Monatlich | OS und Pakete aktualisieren |
| Backup | Täglich | Historie-Datei sichern |
| SSL-Zertifikate | Jährlich | Wenn HTTPS verwendet wird |

### Updates einspielen

```bash
# Native Installation
cd alarm-monitor
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart alarm-dashboard

# Docker Installation
cd alarm-monitor
git pull
docker compose down
docker compose up --build -d
```

### Logs einsehen

```bash
# Native (systemd)
sudo journalctl -u alarm-dashboard -f

# Docker
docker compose logs -f
```

---

## Monitoring

### Health-Checks

Der alarm-monitor bietet einen Health-Check-Endpunkt für Monitoring-Systeme.

```bash
# Health-Check abfragen
curl http://localhost:8000/health

# Erwartete Antwort:
{"status": "ok"}

# Status-Code: 200 = OK, 503 = Service Unavailable
```

### Docker Health-Check

Im `compose.yaml` ist bereits ein Health-Check konfiguriert:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 5s
  start_period: 30s
  retries: 3
```

**Status prüfen**:
```bash
docker compose ps
# Zeigt "healthy" oder "unhealthy"
```

### Log-Monitoring

**Docker-Logs**:
```bash
# Live-Logs anzeigen
docker compose logs -f

# Logs der letzten Stunde
docker compose logs --since 1h

# Nur Fehler
docker compose logs | grep -i error
```

**Systemd-Logs** (native Installation):
```bash
# Live-Logs
sudo journalctl -u alarm-monitor -f

# Logs seit Systemstart
sudo journalctl -u alarm-monitor -b

# Fehler der letzten 24h
sudo journalctl -u alarm-monitor --since "24 hours ago" | grep -i error
```

### Uptime-Monitoring

**Externes Monitoring** (z.B. UptimeRobot, Pingdom):
- URL: `http://server-ip:8000/health`
- Intervall: 5 Minuten
- Timeout: 30 Sekunden
- Benachrichtigung: E-Mail/SMS bei Ausfall

**Eigenes Monitoring-Skript**:
```bash
#!/bin/bash
# health-check.sh

URL="http://localhost:8000/health"
EXPECTED="\"status\":\"ok\""

RESPONSE=$(curl -s $URL)

if echo "$RESPONSE" | grep -q "$EXPECTED"; then
  echo "OK: Service is healthy"
  exit 0
else
  echo "CRITICAL: Service is not responding correctly"
  echo "Response: $RESPONSE"
  exit 2
fi
```

```bash
# Cronjob einrichten (alle 5 Minuten)
*/5 * * * * /usr/local/bin/health-check.sh
```

### Metriken sammeln

**Basis-Metriken**:
```bash
# Anzahl Alarme in Historie
jq '.history | length' ~/alarm-monitor/instance/alarm_history.json

# Letzter Alarm (Zeitstempel)
jq -r '.history[0].timestamp' ~/alarm-monitor/instance/alarm_history.json

# Dateigröße Historie
du -h ~/alarm-monitor/instance/alarm_history.json
```

**Container-Ressourcen**:
```bash
# CPU/Memory-Nutzung
docker stats alarm-dashboard --no-stream

# Disk-Nutzung
docker system df
```

### Alarmierung bei Problemen

**E-Mail-Benachrichtigung**:
```bash
#!/bin/bash
# alert-on-failure.sh

if ! curl -sf http://localhost:8000/health > /dev/null; then
  echo "Alarm Monitor ist nicht erreichbar!" | \
    mail -s "ALARM: Monitor Down" admin@example.com
fi
```

**Telegram-Bot** (optional):
```bash
# Via Telegram-Bot benachrichtigen
BOT_TOKEN="your-bot-token"
CHAT_ID="your-chat-id"

MESSAGE="⚠️ Alarm Monitor ist down!"
curl -s -X POST \
  "https://api.telegram.org/bot$BOT_TOKEN/sendMessage" \
  -d "chat_id=$CHAT_ID" \
  -d "text=$MESSAGE"
```

---

## Fehlerbehebung

### Diagnosebefehle

**Schnell-Diagnose**:
```bash
# Alle Services prüfen
docker compose ps

# Netzwerk testen
curl -I http://localhost:8000

# Logs auf Fehler prüfen
docker compose logs | grep -iE "error|critical|fail"

# Disk Space prüfen
df -h

# Memory prüfen
free -h
```

### Häufige Probleme

#### Dashboard zeigt keine Alarme

1. **API-Verbindung prüfen**:
   ```bash
   # alarm-monitor Logs auf Fehler prüfen
   sudo journalctl -u alarm-dashboard | grep -i "api\|error"
   
   # alarm-mail Service Logs prüfen
   sudo journalctl -u alarm-mail | grep -i "error\|failed"
   # oder bei Docker:
   cd alarm-mail && docker compose logs -f
   ```

2. **API-Key verifizieren**: Stellen Sie sicher, dass der API-Key in beiden
   Services identisch ist (`ALARM_DASHBOARD_API_KEY` im alarm-monitor und
   `ALARM_MAIL_MONITOR_API_KEY` im alarm-mail Service).

3. **Netzwerkverbindung testen**: Der alarm-mail Service muss den alarm-monitor
   erreichen können:
   ```bash
   curl -X POST http://localhost:8000/api/alarm \
     -H "X-API-Key: <ihr-api-key>" \
     -H "Content-Type: application/json" \
     -d '{"incident_number":"TEST-001"}'
   ```

4. **alarm-mail Service Status prüfen**:
   ```bash
   sudo systemctl status alarm-mail
   # oder bei Docker:
   docker compose ps
   ```

#### Karte wird nicht angezeigt

- Prüfen Sie die Internetverbindung
- Stellen Sie sicher, dass JavaScript im Browser aktiviert ist
- Prüfen Sie die Browser-Konsole auf Fehler (F12)

#### Wetterdaten fehlen

- Prüfen Sie die Koordinaten in der Konfiguration
- Stellen Sie sicher, dass api.open-meteo.com erreichbar ist

### Diagnose-Befehle

```bash
# Service-Status prüfen
sudo systemctl status alarm-dashboard
sudo systemctl status alarm-mail

# Netzwerk-Verbindung testen
curl -s http://localhost:8000/health

# API-Endpunkt testen (GET für aktuellen Alarm)
curl -s http://localhost:8000/api/alarm | python3 -m json.tool

# API-Endpunkt testen (POST für neuen Alarm - nur zu Testzwecken)
curl -X POST http://localhost:8000/api/alarm \
  -H "X-API-Key: <ihr-api-key>" \
  -H "Content-Type: application/json" \
  -d '{"incident_number":"TEST-001","keyword":"Test","location":"Testort"}'

# alarm-mail Service Logs prüfen
sudo journalctl -u alarm-mail --since "10 minutes ago"

# Netzwerkverbindung zwischen Services testen
nc -zv localhost 8000
```

---

## Sicherheitshinweise

### Netzwerksicherheit

- **Kein Internetzugang**: Das Dashboard sollte nur im lokalen Netzwerk
  erreichbar sein. Richten Sie **keine** Portweiterleitungen ein.

- **Firewall**: Erlauben Sie nur die notwendigen ausgehenden Verbindungen
  (Nominatim, Open-Meteo, OpenStreetMap). Der alarm-mail Service benötigt
  zusätzlich Zugriff auf den IMAP-Server.

### API-Sicherheit

- **API-Key schützen**: Der API-Key für den Alarmempfang ist sensibel und
  sollte niemals in öffentlichen Repositories committed werden.
- **Starke Keys verwenden**: Generieren Sie API-Keys mit ausreichender
  Entropie (`openssl rand -hex 32`).
- **Keys regelmäßig rotieren**: Wechseln Sie API-Keys in regelmäßigen
  Abständen oder bei Verdacht auf Kompromittierung.
- **Zugriffsbeschränkung**: Stellen Sie sicher, dass der `/api/alarm`
  Endpunkt nur vom alarm-mail Service erreichbar ist (z. B. über
  Firewall-Regeln oder Docker-Netzwerke).

### Zugangsdaten

- Speichern Sie IMAP-Passwörter (alarm-mail Service) niemals im Klartext
  in öffentlichen Repositories.
- Verwenden Sie starke, einzigartige Passwörter für das Alarm-Postfach.
- Nutzen Sie wenn möglich App-spezifische Passwörter.

### Container-Sicherheit

Der Docker-Container läuft als non-root User (`appuser`) für zusätzliche
Sicherheit.

---

## Backup und Wiederherstellung

### Zu sichernde Dateien

| Datei/Verzeichnis | Beschreibung |
|-------------------|--------------|
| `.env` | Konfiguration mit Zugangsdaten |
| `instance/alarm_history.json` | Einsatzhistorie |
| `alarm_dashboard/static/img/crest.png` | Angepasstes Wappen |

### Backup-Skript

```bash
#!/bin/bash
BACKUP_DIR="/backup/alarm-dashboard"
DATE=$(date +%Y%m%d)

mkdir -p $BACKUP_DIR
cp .env $BACKUP_DIR/.env.$DATE
cp instance/alarm_history.json $BACKUP_DIR/alarm_history.$DATE.json
```

### Wiederherstellung

```bash
# Konfiguration wiederherstellen
cp /backup/alarm-dashboard/.env.YYYYMMDD .env

# Historie wiederherstellen
cp /backup/alarm-dashboard/alarm_history.YYYYMMDD.json instance/alarm_history.json

# Service neu starten
sudo systemctl restart alarm-dashboard
```

---

## Performance-Optimierung

### Hardware-Optimierung

**Raspberry Pi**:
```bash
# GPU-Memory reduzieren (für Headless-Betrieb)
sudo nano /boot/config.txt
# Hinzufügen:
gpu_mem=16

# Overclock (optional, auf eigene Gefahr)
over_voltage=2
arm_freq=1750

# Reboot erforderlich
sudo reboot
```

**SSD statt SD-Karte**: Deutlich bessere I/O-Performance

**Kühlkörper**: Verhindert Thermal-Throttling

### Software-Optimierung

**Gunicorn-Worker anpassen**:
```bash
# Für Raspberry Pi 4 (4 Cores)
gunicorn --workers 2 --threads 4 \
  --worker-class gthread \
  'alarm_dashboard.app:create_app()'

# Regel: workers = (2 × CPU_CORES) + 1
# Threads: 2-4 pro Worker
```

**Docker-Ressourcen limitieren**:
```yaml
# compose.yaml
services:
  alarm-monitor:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
```

### Caching

**Nginx Reverse-Proxy** (für statische Assets):
```nginx
server {
    listen 80;
    server_name alarm-monitor.local;

    location /static/ {
        alias /app/alarm_dashboard/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Browser-Caching** (für Clients):
Bereits implementiert via Flask's `send_from_directory`.

### Datenbankoptimierung

**JSON-Datei** (aktuell):
- Gut für < 1000 Alarme
- Einfach, keine Abhängigkeiten
- Performance sinkt bei großen Dateien

**Migration zu SQLite** (geplant):
```python
# Zukünftige Implementierung
CREATE TABLE alarms (
    id INTEGER PRIMARY KEY,
    incident_number TEXT UNIQUE,
    timestamp DATETIME,
    keyword TEXT,
    location TEXT,
    data JSON
);

CREATE INDEX idx_incident_number ON alarms(incident_number);
CREATE INDEX idx_timestamp ON alarms(timestamp DESC);
```

**Workaround bei großen Historien**:
```bash
# Alte Alarme archivieren (älter als 1 Jahr)
DATE_CUTOFF=$(date -d '1 year ago' +%Y-%m-%d)

# Backup erstellen
cp instance/alarm_history.json instance/alarm_history_backup.json

# Mit jq filtern
jq --arg date "$DATE_CUTOFF" \
  '{history: [.history[] | select(.timestamp >= $date)]}' \
  instance/alarm_history.json > instance/alarm_history_filtered.json

mv instance/alarm_history_filtered.json instance/alarm_history.json
```

### Netzwerk-Optimierung

**Lokale Nominatim-Instanz** (für viele Geocoding-Anfragen):
```yaml
# compose.yaml
services:
  nominatim:
    image: mediagis/nominatim:latest
    ports:
      - "8080:8080"
    environment:
      - PBF_URL=https://download.geofabrik.de/europe/germany-latest.osm.pbf
```

```bash
# In alarm-monitor .env:
ALARM_DASHBOARD_NOMINATIM_URL=http://nominatim:8080/search
```

**CDN für externe Libraries** (optional):
```html
<!-- Leaflet von CDN statt lokal -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9/dist/leaflet.css"/>
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9/dist/leaflet.js"></script>
```

### Frontend-Optimierung

**Lazy Loading** (für Bilder):
```html
<img src="wappen.png" loading="lazy" alt="Wappen">
```

**CSS/JS Minification**:
```bash
# Mit Terser (JavaScript)
npm install -g terser
terser alarm_dashboard/static/js/dashboard.js \
  -o alarm_dashboard/static/js/dashboard.min.js

# Mit cssnano (CSS)
npm install -g cssnano-cli
cssnano alarm_dashboard/static/css/dashboard.css \
  alarm_dashboard/static/css/dashboard.min.css
```

### Monitoring-Overhead reduzieren

**Polling-Intervall anpassen**:
```javascript
// dashboard.js
// Standard: 5 Sekunden
const POLL_INTERVAL = 10000; // 10 Sekunden

// Messenger-Polling
const MESSENGER_POLL_INTERVAL = 30000; // 30 Sekunden
```

### Performance-Messungen

**Backend-Response-Times**:
```bash
# Mit curl
time curl -s http://localhost:8000/api/alarm > /dev/null

# Mit Apache Bench
ab -n 100 -c 10 http://localhost:8000/api/alarm
```

**Frontend Load-Times**:
```javascript
// In Browser-Console
performance.timing.loadEventEnd - performance.timing.navigationStart
```

---

## Anhang

### Beispiel: Vollständige .env-Datei

```ini
# API-Key für Alarmempfang (erforderlich)
ALARM_DASHBOARD_API_KEY=a1b2c3d4e5f6...  # openssl rand -hex 32

# Betriebsparameter
ALARM_DASHBOARD_GRUPPEN=
ALARM_DASHBOARD_DISPLAY_DURATION_MINUTES=30

# Anzeige
ALARM_DASHBOARD_FIRE_DEPARTMENT_NAME=Feuerwehr Musterstadt
ALARM_DASHBOARD_DEFAULT_LATITUDE=51.2345
ALARM_DASHBOARD_DEFAULT_LONGITUDE=9.8765
ALARM_DASHBOARD_DEFAULT_LOCATION_NAME=Feuerwehrhaus Musterstadt

# Alarm-Messenger Integration (optional - für Teilnehmerrückmeldungen)
# ALARM_DASHBOARD_MESSENGER_SERVER_URL=https://messenger.example.com
# ALARM_DASHBOARD_MESSENGER_API_KEY=your-messenger-api-key-here

# Optional
ALARM_DASHBOARD_ORS_API_KEY=
ALARM_DASHBOARD_APP_VERSION=v1.0.0
```

### Kontakt und Support

Bei Fragen oder Problemen wenden Sie sich an:

- **GitHub Issues**: https://github.com/TimUx/alarm-monitor/issues
- **E-Mail**: t.braun@feuerwehr-willingshausen.de

---

*Letzte Aktualisierung: Dezember 2025*
