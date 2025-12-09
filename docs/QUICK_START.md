# 🚀 Quick Start Guide – Alarm Monitor

Schnelleinstieg für die Installation und Inbetriebnahme des Alarm Monitor Systems.

---

## Inhaltsverzeichnis

- [Was Sie benötigen](#was-sie-benötigen)
- [Schritt 1: alarm-monitor installieren](#schritt-1-alarm-monitor-installieren)
- [Schritt 2: alarm-mail installieren](#schritt-2-alarm-mail-installieren)
- [Schritt 3: Ersten Testalarm senden](#schritt-3-ersten-testalarm-senden)
- [Schritt 4: alarm-messenger einrichten (optional)](#schritt-4-alarm-messenger-einrichten-optional)
- [Nächste Schritte](#nächste-schritte)
- [Fehlerbehebung](#fehlerbehebung)

---

## Was Sie benötigen

### Hardware
- **Server**: Raspberry Pi 3/4, Mini-PC oder Server (min. 1 GB RAM)
- **Client-Geräte**: Beliebige Geräte mit Webbrowser

### Software
- **Docker & Docker Compose** (empfohlen)  
  ODER  
- **Python 3.9+** für native Installation

### Zugangsdaten
- **IMAP-Postfach**: Host, Port, Benutzername, Passwort
- **Internet-Zugang**: Für Geocoding und Wetter-APIs

### Zeitbedarf
⏱️ **15-30 Minuten** für Grundinstallation

---

## Schritt 1: alarm-monitor installieren

### 1.1 Docker installieren (falls noch nicht vorhanden)

```bash
# Auf Debian/Ubuntu/Raspberry Pi OS
sudo apt update
sudo apt install -y docker.io docker-compose git curl

# Docker-Benutzer hinzufügen (optional, um ohne sudo zu arbeiten)
sudo usermod -aG docker $USER
# Nach diesem Befehl neu anmelden!
```

### 1.2 Repository klonen

```bash
# In Ihr bevorzugtes Verzeichnis wechseln
cd ~  # oder cd /opt

# Repository klonen
git clone https://github.com/TimUx/alarm-monitor.git
cd alarm-monitor
```

### 1.3 Konfiguration erstellen

```bash
# Beispiel-Konfiguration kopieren
cp .env.example .env

# API-Key generieren
echo "Ihr neuer API-Key:"
openssl rand -hex 32

# .env-Datei bearbeiten
nano .env
```

**Minimal-Konfiguration** (`.env`):
```bash
# PFLICHTFELD: API-Key für Alarmempfang
ALARM_DASHBOARD_API_KEY=<hier-den-generierten-key-einfügen>

# Feuerwehr-Name (optional)
ALARM_DASHBOARD_FIRE_DEPARTMENT_NAME=Feuerwehr Musterstadt

# Standardkoordinaten für Idle-Ansicht (optional)
ALARM_DASHBOARD_DEFAULT_LATITUDE=51.2345
ALARM_DASHBOARD_DEFAULT_LONGITUDE=9.8765
ALARM_DASHBOARD_DEFAULT_LOCATION_NAME=Feuerwache Musterstadt
```

**Wichtig**: Notieren Sie sich den API-Key! Sie benötigen ihn für alarm-mail.

### 1.4 Container starten

```bash
# Container bauen und starten
docker compose up -d

# Logs anzeigen
docker compose logs -f

# Warten Sie, bis Sie folgende Meldung sehen:
# "Alarm Dashboard started on port 8000"
```

### 1.5 Dashboard testen

Öffnen Sie in Ihrem Browser:
```
http://localhost:8000
```

✅ **Erfolgreich**, wenn Sie die Idle-Ansicht mit Uhrzeit und Wetter sehen!

---

## Schritt 2: alarm-mail installieren

Der `alarm-mail` Service überwacht das IMAP-Postfach und leitet Alarme weiter.

### 2.1 Repository klonen

```bash
# In ein anderes Verzeichnis wechseln
cd ~  # oder cd /opt

# alarm-mail Repository klonen
git clone https://github.com/TimUx/alarm-mail.git
cd alarm-mail
```

### 2.2 Konfiguration erstellen

```bash
# Beispiel-Konfiguration kopieren
cp .env.example .env

# .env-Datei bearbeiten
nano .env
```

**Minimal-Konfiguration** (`.env`):
```bash
# ===== IMAP-Postfach =====
ALARM_MAIL_IMAP_HOST=imap.example.com
ALARM_MAIL_IMAP_PORT=993
ALARM_MAIL_IMAP_USE_SSL=true
ALARM_MAIL_IMAP_USERNAME=alarm@feuerwehr.de
ALARM_MAIL_IMAP_PASSWORD=IhrPasswort
ALARM_MAIL_IMAP_MAILBOX=INBOX
ALARM_MAIL_POLL_INTERVAL=60

# ===== alarm-monitor Integration =====
# Wichtig: Derselbe API-Key wie in alarm-monitor!
ALARM_MAIL_MONITOR_URL=http://localhost:8000
ALARM_MAIL_MONITOR_API_KEY=<derselbe-api-key-wie-in-schritt-1>
```

**Wichtig**: 
- Der `ALARM_MAIL_MONITOR_API_KEY` muss **identisch** mit dem `ALARM_DASHBOARD_API_KEY` aus Schritt 1 sein!
- Wenn beide Services auf demselben Host laufen: `http://localhost:8000`
- Wenn Services auf verschiedenen Hosts: `http://IP-ADRESSE:8000`
- Im Docker-Netzwerk: `http://alarm-monitor:8000`

### 2.3 Service starten

```bash
# Container starten
docker compose up -d

# Logs anzeigen
docker compose logs -f

# Warten Sie auf:
# "Starting IMAP mail checker..."
# "Connected to IMAP server"
```

### 2.4 Verbindung testen

```bash
# alarm-mail Logs prüfen
docker compose logs -f

# Erfolgreiche Verbindung:
# ✅ "Connected to IMAP server imap.example.com"
# ✅ "Checking mailbox INBOX..."

# Fehlgeschlagene Verbindung:
# ❌ "Failed to connect to IMAP server"
# → IMAP-Zugangsdaten prüfen!
```

---

## Schritt 3: Ersten Testalarm senden

Sobald beide Services laufen, können Sie einen Testalarm senden.

### Option A: Testalarm via API

```bash
# API-Key aus .env auslesen
API_KEY=$(grep ALARM_DASHBOARD_API_KEY ~/alarm-monitor/.env | cut -d= -f2)

# Testalarm senden
curl -X POST http://localhost:8000/api/alarm \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "incident_number": "TEST-001",
    "keyword": "F3Y",
    "keyword_sub": "Brand",
    "timestamp": "2024-01-01T12:00:00",
    "description": "Testalarm - Brand in Wohngebäude",
    "remarks": "Dies ist ein Testalarm",
    "location": "Teststraße 1",
    "city": "Teststadt",
    "latitude": 51.2345,
    "longitude": 9.8765,
    "resources": [
      {
        "name": "LF Teststadt 1",
        "dispatched_at": "2024-01-01T12:01:00"
      }
    ]
  }'

# Erwartete Antwort:
# {"success": true, "message": "Alarm processed successfully"}
```

### Option B: Test-E-Mail senden

Falls Sie Zugriff auf das IMAP-Postfach haben, senden Sie eine Test-E-Mail mit XML-Inhalt. Beispiel-Format siehe [README.md](../README.md).

### Alarm im Dashboard prüfen

1. Öffnen Sie das Dashboard: `http://localhost:8000`
2. ✅ **Erfolgreich**, wenn der Testalarm angezeigt wird!
3. Nach 30 Minuten (Standard-DISPLAY_DURATION) wechselt die Ansicht automatisch zu Idle

---

## Schritt 4: alarm-messenger einrichten (optional)

Der `alarm-messenger` Service ermöglicht mobile Push-Benachrichtigungen und Teilnehmerrückmeldungen.

**Hinweis**: Dieser Schritt ist **optional**. Das System funktioniert vollständig ohne alarm-messenger.

### 4.1 Repository klonen

```bash
cd ~  # oder cd /opt

git clone https://github.com/TimUx/alarm-messenger.git
cd alarm-messenger
```

### 4.2 Konfiguration erstellen

```bash
cp .env.example .env
nano .env
```

```bash
# Minimal-Konfiguration
API_SECRET_KEY=<neuer-api-key-für-messenger>

# Firebase-Konfiguration (für Push-Notifications)
# Details siehe alarm-messenger Dokumentation
```

API-Key generieren:
```bash
openssl rand -hex 32
```

### 4.3 Service starten

```bash
docker compose up -d
docker compose logs -f
```

### 4.4 Integration konfigurieren

#### alarm-monitor konfigurieren

```bash
cd ~/alarm-monitor
nano .env
```

Fügen Sie hinzu:
```bash
# Messenger-Integration
ALARM_DASHBOARD_MESSENGER_SERVER_URL=http://localhost:3000
ALARM_DASHBOARD_MESSENGER_API_KEY=<api-secret-key-vom-messenger>
```

```bash
# Container neu starten
docker compose restart
```

#### alarm-mail konfigurieren

```bash
cd ~/alarm-mail
nano .env
```

Fügen Sie hinzu:
```bash
# Messenger-Integration
ALARM_MAIL_MESSENGER_URL=http://localhost:3000
ALARM_MAIL_MESSENGER_API_KEY=<api-secret-key-vom-messenger>
```

```bash
# Container neu starten
docker compose restart
```

### 4.5 Mobile Geräte registrieren

1. Öffnen Sie das Messenger-Admin-Interface: `http://localhost:3000/admin/`
2. Generieren Sie einen QR-Code für die Geräteregistrierung
3. Scannen Sie den QR-Code mit der Messenger-App auf Ihrem Smartphone

Details siehe [alarm-messenger Dokumentation](https://github.com/TimUx/alarm-messenger).

---

## Nächste Schritte

### ✅ Grundinstallation abgeschlossen!

Ihr System ist jetzt einsatzbereit. Folgende Schritte empfohlen:

### 1. Kiosk-Modus einrichten

Für dedizierte Anzeigegeräte (z.B. Raspberry Pi mit Display):

```bash
# Autostart-Skript erstellen
mkdir -p ~/.config/autostart

cat > ~/.config/autostart/alarm-dashboard.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=Alarm Dashboard Kiosk
Exec=chromium-browser --kiosk --noerrdialogs --disable-infobars http://SERVER-IP:8000
EOF
```

Ersetzen Sie `SERVER-IP` mit der IP-Adresse Ihres Servers.

### 2. Autostart einrichten (Systemd)

Damit die Services beim Systemstart automatisch starten:

```bash
# Für alarm-monitor
sudo nano /etc/systemd/system/alarm-monitor.service
```

```ini
[Unit]
Description=Alarm Monitor Dashboard
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/pi/alarm-monitor
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable alarm-monitor
sudo systemctl start alarm-monitor
```

Wiederholen Sie dies für `alarm-mail` und `alarm-messenger`.

### 3. Backup einrichten

```bash
# Backup-Skript erstellen
cat > ~/backup-alarm-monitor.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=~/backups/alarm-monitor
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Konfiguration sichern
cp ~/alarm-monitor/.env $BACKUP_DIR/.env.$DATE

# Historie sichern
cp ~/alarm-monitor/instance/alarm_history.json $BACKUP_DIR/alarm_history.$DATE.json

# Alte Backups löschen (älter als 30 Tage)
find $BACKUP_DIR -type f -mtime +30 -delete

echo "Backup erstellt: $BACKUP_DIR"
EOF

chmod +x ~/backup-alarm-monitor.sh

# Cronjob einrichten (täglich um 2 Uhr)
(crontab -l 2>/dev/null; echo "0 2 * * * ~/backup-alarm-monitor.sh") | crontab -
```

### 4. Branding anpassen

```bash
# Eigenes Wappen einbinden
cp /pfad/zu/ihrem/wappen.png ~/alarm-monitor/alarm_dashboard/static/img/crest.png

# Container neu starten
cd ~/alarm-monitor
docker compose restart
```

### 5. Weitere Dokumentation lesen

- **[README.md](../README.md)** – Vollständige Dokumentation
- **[Betriebshandbuch.md](../Betriebshandbuch.md)** – Ausführliche Betriebsanleitung
- **[ARCHITECTURE.md](ARCHITECTURE.md)** – Technische Architektur
- **[MESSENGER_INTEGRATION.md](MESSENGER_INTEGRATION.md)** – Messenger-Details

---

## Fehlerbehebung

### Problem: Dashboard zeigt "Verbindung fehlgeschlagen"

**Lösung**:
```bash
# Service-Status prüfen
cd ~/alarm-monitor
docker compose ps

# Logs prüfen
docker compose logs -f

# Container neu starten
docker compose restart
```

### Problem: alarm-mail kann keine E-Mails abrufen

**Lösung**:
```bash
# IMAP-Verbindung testen
cd ~/alarm-mail
docker compose logs -f

# Häufige Ursachen:
# - Falsche IMAP-Zugangsdaten
# - Firewall blockiert Port 993
# - IMAP nicht aktiviert im E-Mail-Konto
```

### Problem: Alarme werden nicht angezeigt

**Lösung**:
```bash
# 1. API-Key prüfen
grep ALARM_DASHBOARD_API_KEY ~/alarm-monitor/.env
grep ALARM_MAIL_MONITOR_API_KEY ~/alarm-mail/.env
# → Müssen identisch sein!

# 2. Netzwerkverbindung testen
curl http://localhost:8000/health
# → {"status": "ok"}

# 3. Testalarm manuell senden (siehe Schritt 3)
```

### Problem: Karte wird nicht angezeigt

**Lösung**:
```bash
# 1. Internet-Verbindung prüfen
ping -c 3 tile.openstreetmap.org

# 2. Browser-Konsole öffnen (F12)
# → JavaScript-Fehler prüfen

# 3. Koordinaten prüfen
# Sind gültige Koordinaten im Alarm vorhanden?
```

### Problem: Wetter wird nicht angezeigt

**Lösung**:
```bash
# Open-Meteo API testen
curl "https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current_weather=true"

# Firewall-Regeln prüfen
# → Muss ausgehende HTTPS-Verbindungen erlauben
```

---

## Hilfe & Support

**Bei weiteren Fragen**:

- **GitHub Issues**: [github.com/TimUx/alarm-monitor/issues](https://github.com/TimUx/alarm-monitor/issues)
- **E-Mail**: t.braun@feuerwehr-willingshausen.de
- **Dokumentation**: [github.com/TimUx/alarm-monitor](https://github.com/TimUx/alarm-monitor)

---

<div align="center">

**Viel Erfolg mit Ihrem Alarm Monitor System! 🚒**

[⬆ Zurück nach oben](#-quick-start-guide--alarm-monitor)

</div>
