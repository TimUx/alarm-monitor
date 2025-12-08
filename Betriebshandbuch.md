# Betriebshandbuch – Feuerwehr Alarm Monitor

Dieses Betriebshandbuch beschreibt die Einrichtung, den Betrieb und die
Wartung des Feuerwehr Alarm Monitors. Es richtet sich an Administratoren
und technisch versierte Anwender.

## Inhaltsverzeichnis

1. [Systemanforderungen](#systemanforderungen)
2. [Installation](#installation)
3. [Konfiguration](#konfiguration)
4. [Inbetriebnahme](#inbetriebnahme)
5. [Betrieb](#betrieb)
6. [Wartung](#wartung)
7. [Fehlerbehebung](#fehlerbehebung)
8. [Sicherheitshinweise](#sicherheitshinweise)
9. [Backup und Wiederherstellung](#backup-und-wiederherstellung)

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

Der Server benötigt ausgehende Verbindungen zu:

| Dienst | URL | Port | Zweck |
|--------|-----|------|-------|
| IMAP-Server | Konfigurierbar | 993 (SSL) / 143 | E-Mail-Abruf |
| Nominatim | nominatim.openstreetmap.org | 443 | Geokodierung |
| Open-Meteo | api.open-meteo.com | 443 | Wetterdaten |
| OpenStreetMap | tile.openstreetmap.org | 443 | Kartenkacheln |

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
# IMAP-Konfiguration (Pflichtfelder)
ALARM_DASHBOARD_IMAP_HOST=imap.ihr-provider.de
ALARM_DASHBOARD_IMAP_PORT=993
ALARM_DASHBOARD_IMAP_USE_SSL=true
ALARM_DASHBOARD_IMAP_USERNAME=alarm@feuerwehr-beispiel.de
ALARM_DASHBOARD_IMAP_PASSWORD=IhrSicheresPasswort
ALARM_DASHBOARD_IMAP_MAILBOX=INBOX
ALARM_DASHBOARD_IMAP_SEARCH=UNSEEN

# Polling-Intervall in Sekunden
ALARM_DASHBOARD_POLL_INTERVAL=60

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
| `POLL_INTERVAL` | Abrufintervall in Sekunden | 60 |
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

## Fehlerbehebung

### Häufige Probleme

#### Dashboard zeigt keine Alarme

1. **IMAP-Verbindung prüfen**:
   ```bash
   # Logs auf Fehler prüfen
   sudo journalctl -u alarm-dashboard | grep -i "imap\|error"
   ```

2. **Zugangsdaten verifizieren**: Testen Sie die IMAP-Zugangsdaten
   manuell mit einem E-Mail-Client.

3. **Firewall prüfen**: Port 993 (IMAPS) muss ausgehend erlaubt sein.

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

# Netzwerk-Verbindung testen
curl -s http://localhost:8000/health

# IMAP-Verbindung testen
openssl s_client -connect imap.example.com:993

# API-Antwort prüfen
curl -s http://localhost:8000/api/alarm | python3 -m json.tool
```

---

## Sicherheitshinweise

### Netzwerksicherheit

- **Kein Internetzugang**: Das Dashboard sollte nur im lokalen Netzwerk
  erreichbar sein. Richten Sie **keine** Portweiterleitungen ein.

- **Firewall**: Erlauben Sie nur die notwendigen ausgehenden Verbindungen
  (IMAP, Nominatim, Open-Meteo, OpenStreetMap).

### Zugangsdaten

- Speichern Sie IMAP-Passwörter niemals im Klartext in öffentlichen
  Repositories.
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

## Anhang

### Beispiel: Vollständige .env-Datei

```ini
# IMAP-Konfiguration
ALARM_DASHBOARD_IMAP_HOST=imap.mailserver.de
ALARM_DASHBOARD_IMAP_PORT=993
ALARM_DASHBOARD_IMAP_USE_SSL=true
ALARM_DASHBOARD_IMAP_USERNAME=alarm@feuerwehr-beispiel.de
ALARM_DASHBOARD_IMAP_PASSWORD=GeheimesPasswort123!
ALARM_DASHBOARD_IMAP_MAILBOX=INBOX
ALARM_DASHBOARD_IMAP_SEARCH=UNSEEN

# Betriebsparameter
ALARM_DASHBOARD_POLL_INTERVAL=60
ALARM_DASHBOARD_GRUPPEN=
ALARM_DASHBOARD_DISPLAY_DURATION_MINUTES=30

# Anzeige
ALARM_DASHBOARD_FIRE_DEPARTMENT_NAME=Feuerwehr Musterstadt
ALARM_DASHBOARD_DEFAULT_LATITUDE=51.2345
ALARM_DASHBOARD_DEFAULT_LONGITUDE=9.8765
ALARM_DASHBOARD_DEFAULT_LOCATION_NAME=Feuerwehrhaus Musterstadt

# Alarm-Messenger Integration (optional)
# ALARM_DASHBOARD_MESSENGER_SERVER_URL=https://messenger.example.com
# ALARM_DASHBOARD_MESSENGER_API_KEY=your-api-key-here

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
