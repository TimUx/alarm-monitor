# 🍓 Raspberry Pi 3 – Installationsanleitung: Feuerwehr Dashboard

Diese Anleitung beschreibt den vollständigen Aufbau eines Feuerwehr-Dashboard-Systems auf einem **Raspberry Pi 3** mit:

- **Raspberry Pi OS Lite** als minimales Betriebssystem
- **Docker & Docker Compose** für die Services `alarm-mail` und `alarm-monitor`
- **kweb** im Kiosk-Modus als Vollbild-Browser auf HDMI
- **Watchdog** für automatischen Browser-Neustart bei Absturz
- **Splashscreen** beim Systemstart ("Feuerwehr Dashboard lädt…")
- **Alarm-Sound** bei neuen Einsatzmeldungen
- Diverse **Optimierungen** für den ressourcenbeschränkten RPi 3

---

## Inhaltsverzeichnis

1. [Voraussetzungen & Hardware](#1-voraussetzungen--hardware)
2. [Raspberry Pi OS vorbereiten](#2-raspberry-pi-os-vorbereiten)
3. [Grundkonfiguration des Systems](#3-grundkonfiguration-des-systems)
4. [Docker & Docker Compose installieren](#4-docker--docker-compose-installieren)
5. [Ordnerstruktur & docker-compose.yml erstellen](#5-ordnerstruktur--docker-composeyml-erstellen)
6. [kweb im Kiosk-Modus installieren](#6-kweb-im-kiosk-modus-installieren)
7. [Endlosschleife für Browser-Neustart](#7-endlosschleife-für-browser-neustart)
8. [Systemd-Services einrichten](#8-systemd-services-einrichten)
9. [Splashscreen beim Boot](#9-splashscreen-beim-boot)
10. [Alarm-Sound bei neuen Events](#10-alarm-sound-bei-neuen-events)
11. [System starten & prüfen](#11-system-starten--prüfen)
12. [Optimierungen für Stabilität & Ressourcen](#12-optimierungen-für-stabilität--ressourcen)
13. [Optional: Netzwerk- & Soundeinstellungen](#13-optional-netzwerk---soundeinstellungen)
14. [Fazit](#14-fazit)

---

## 1. Voraussetzungen & Hardware

### Benötigte Hardware

| Komponente | Empfehlung |
|------------|------------|
| Raspberry Pi | RPi 3 Model B oder B+ |
| microSD-Karte | min. 16 GB, Class 10 / A1 |
| Netzteil | 5 V / 2,5 A (offizielles RPi-Netzteil) |
| Monitor/Bildschirm | HDMI, min. 1920×1080 empfohlen |
| HDMI-Kabel | Standard HDMI |
| Lautsprecher | 3,5-mm-Klinke oder HDMI-Audio |
| Netzwerk | Ethernet-Kabel (empfohlen) oder WLAN |
| Tastatur + Maus | Nur für Ersteinrichtung |

### Benötigte Software / Accounts

- [Raspberry Pi Imager](https://www.raspberrypi.com/software/) auf einem anderen PC
- GitHub-Repositories:
  - [`TimUx/alarm-monitor`](https://github.com/TimUx/alarm-monitor)
  - [`TimUx/alarm-mail`](https://github.com/TimUx/alarm-mail)
- IMAP-Postfach-Zugangsdaten (für `alarm-mail`)

---

## 2. Raspberry Pi OS vorbereiten

### 2.1 Image schreiben

1. **Raspberry Pi Imager** starten
2. Gerät: **Raspberry Pi 3**
3. Betriebssystem: **Raspberry Pi OS Lite (64-bit)** *(kein Desktop – wir brauchen keinen)*
4. SD-Karte auswählen und auf **Weiter** klicken
5. In den **erweiterten Einstellungen** (Zahnrad-Icon):
   - Hostname: `feuerwehr-dashboard`
   - SSH aktivieren (Passwort-Authentifizierung)
   - Benutzername: `pi`, Passwort nach Wahl setzen
   - WLAN-Zugangsdaten eintragen (falls kein Ethernet)
   - Zeitzone: `Europe/Berlin`
   - Tastaturlayout: `de`
6. Auf **Schreiben** klicken und warten

### 2.2 Ersten Start durchführen

SD-Karte in den RPi einlegen, HDMI anschließen und mit Strom versorgen.  
Nach dem Boot per SSH verbinden (oder direkt mit Tastatur):

```bash
ssh pi@feuerwehr-dashboard.local
# alternativ mit IP-Adresse:
ssh pi@192.168.1.xxx
```

---

## 3. Grundkonfiguration des Systems

### 3.1 System aktualisieren

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt autoremove -y
sudo reboot
```

### 3.2 Notwendige Pakete installieren

```bash
sudo apt update
sudo apt install -y \
    git curl wget unzip \
    xorg xinit openbox \
    alsa-utils sox \
    fonts-dejavu-core \
    ca-certificates gnupg lsb-release
```

> **Hinweis:** `xorg` und `openbox` werden für den kweb-Kiosk-Modus benötigt, auch wenn kein vollständiger Desktop installiert ist.

### 3.3 GPU-Speicher reduzieren (RPi 3 Optimierung)

Da kein Desktop-GUI benötigt wird, kann mehr RAM für die Anwendungen reserviert werden:

```bash
sudo raspi-config
```

Navigiere zu:  
`Performance Options` → `GPU Memory` → Wert auf **`64`** setzen → Bestätigen → Neustart

### 3.4 Swap vergrößern (optional, aber empfohlen für RPi 3)

```bash
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
```

Zeile `CONF_SWAPSIZE=100` ändern zu:

```
CONF_SWAPSIZE=512
```

```bash
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

---

## 4. Docker & Docker Compose installieren

### 4.1 Docker installieren

```bash
# Offizielles Installations-Skript von Docker (empfohlen für ARM)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
rm get-docker.sh

# Benutzer "pi" zur Docker-Gruppe hinzufügen
sudo usermod -aG docker pi

# Neu anmelden, damit die Gruppe aktiv wird
newgrp docker
```

### 4.2 Docker Compose installieren

```bash
sudo apt install -y docker-compose-plugin

# Version prüfen
docker compose version
```

### 4.3 Docker beim Boot starten

```bash
sudo systemctl enable docker
sudo systemctl start docker

# Funktionstest
docker run --rm hello-world
```

---

## 5. Ordnerstruktur & docker-compose.yml erstellen

### 5.1 Verzeichnisse anlegen

```bash
mkdir -p ~/feuerwehr/{alarm-monitor,alarm-mail}
mkdir -p ~/feuerwehr/alarm-monitor/instance
```

### 5.2 Konfigurationsdateien erstellen

#### alarm-monitor `.env`

```bash
nano ~/feuerwehr/alarm-monitor/.env
```

Inhalt (Werte anpassen):

```env
# Allgemein
TZ=Europe/Berlin
SECRET_KEY=dein-geheimer-schluessel-hier

# Datenbank
DATABASE_URL=sqlite:///instance/alarms.db

# Authentifizierung (optional)
ADMIN_PASSWORD=sicheres-passwort

# API-Einstellungen
GEOCODING_PROVIDER=nominatim
ORS_API_KEY=dein-openrouteservice-key
```

#### alarm-mail `.env`

```bash
nano ~/feuerwehr/alarm-mail/.env
```

Inhalt (Werte anpassen):

```env
TZ=Europe/Berlin

# IMAP-Postfach
IMAP_HOST=mail.example.com
IMAP_PORT=993
IMAP_USER=alarm@feuerwehr.example.com
IMAP_PASSWORD=imap-passwort
IMAP_SSL=true
IMAP_FOLDER=INBOX

# alarm-monitor Endpunkt
ALARM_MONITOR_URL=http://alarm-monitor:8000/api/alarm
ALARM_MONITOR_TOKEN=dein-api-token
```

### 5.3 docker-compose.yml erstellen

```bash
nano ~/feuerwehr/docker-compose.yml
```

```yaml
services:

  alarm-monitor:
    image: ghcr.io/timux/alarm-monitor:latest
    container_name: alarm-monitor
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - ./alarm-monitor/.env
    volumes:
      - ./alarm-monitor/instance:/app/instance
    networks:
      - alarm-net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      start_period: 60s
      retries: 5

  alarm-mail:
    image: ghcr.io/timux/alarm-mail:latest
    container_name: alarm-mail
    restart: unless-stopped
    env_file:
      - ./alarm-mail/.env
    networks:
      - alarm-net
    depends_on:
      alarm-monitor:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "pgrep", "-f", "alarm-mail"]
      interval: 60s
      timeout: 10s
      start_period: 30s
      retries: 3

networks:
  alarm-net:
    driver: bridge
```

### 5.4 Services starten (erster Test)

```bash
cd ~/feuerwehr
docker compose pull
docker compose up -d

# Status prüfen
docker compose ps
docker compose logs -f
```

Das Dashboard sollte nun unter `http://localhost:8000` erreichbar sein.

---

## 6. kweb im Kiosk-Modus installieren

### 6.1 kweb installieren

`kweb` ist ein schlanker Webkit-basierter Browser, der sich ideal für Kiosk-Systeme auf dem RPi eignet.

```bash
sudo apt install -y kweb
```

> Falls `kweb` nicht im Repository verfügbar ist:
>
> ```bash
> # Alternative: Installation über das offizielle RPi-Kiosk-Paket
> sudo apt install -y rpi-chromium-mods
> # Oder Chromium im Kiosk-Modus (mehr RAM-Verbrauch)
> sudo apt install -y chromium-browser
> ```

### 6.2 Autostart für X-Session einrichten

Openbox-Autostart konfigurieren:

```bash
mkdir -p ~/.config/openbox
nano ~/.config/openbox/autostart
```

Inhalt:

```bash
# Bildschirmschoner & Energiesparmodus deaktivieren
xset s off &
xset s noblank &
xset -dpms &

# Mauszeiger ausblenden (nach 0.1 Sekunden Inaktivität)
unclutter -idle 0.1 -root &

# Kiosk-Browser starten (Skript wird in Schritt 7 erstellt)
/home/pi/feuerwehr/kiosk.sh &
```

### 6.3 Automatischen Login für Benutzer `pi` einrichten

```bash
sudo raspi-config
```

Navigiere zu:  
`System Options` → `Boot / Auto Login` → **`Console Autologin`** auswählen

### 6.4 X-Server beim Login automatisch starten

```bash
nano ~/.bash_profile
```

Folgendes ans Ende anfügen:

```bash
# X-Server starten (nur auf tty1, nur wenn noch kein Display vorhanden)
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    exec startx -- -nocursor
fi
```

---

## 7. Endlosschleife für Browser-Neustart

Das Kiosk-Skript startet den Browser in einer Endlosschleife, sodass er bei einem Absturz automatisch neu gestartet wird.

```bash
nano ~/feuerwehr/kiosk.sh
```

```bash
#!/usr/bin/env bash
#
# kiosk.sh – Feuerwehr Dashboard Kiosk
# Startet kweb im Kiosk-Modus und neustartet bei Absturz automatisch

DASHBOARD_URL="http://localhost:8000"
LOG_FILE="/var/log/kiosk.log"
RESTART_DELAY=5  # Sekunden Wartezeit vor Neustart

echo "[$(date)] Kiosk-Script gestartet" >> "$LOG_FILE"

# Warten bis der Dashboard-Service erreichbar ist
echo "[$(date)] Warte auf Dashboard-Service..." >> "$LOG_FILE"
until curl -sf "$DASHBOARD_URL/health" > /dev/null 2>&1; do
    echo "[$(date)] Dashboard noch nicht erreichbar, warte ${RESTART_DELAY}s..." >> "$LOG_FILE"
    sleep "$RESTART_DELAY"
done
echo "[$(date)] Dashboard erreichbar, starte Browser" >> "$LOG_FILE"

# Endlosschleife: Browser starten und bei Beendigung neu starten
while true; do
    echo "[$(date)] Starte kweb..." >> "$LOG_FILE"

    kweb \
        --kiosk \
        --fullscreen \
        --no-sandbox \
        --disable-cache \
        "$DASHBOARD_URL" \
        >> "$LOG_FILE" 2>&1

    EXIT_CODE=$?
    echo "[$(date)] kweb beendet (Exit-Code: ${EXIT_CODE}), Neustart in ${RESTART_DELAY}s..." >> "$LOG_FILE"
    sleep "$RESTART_DELAY"
done
```

```bash
chmod +x ~/feuerwehr/kiosk.sh
```

> **Alternative für Chromium** (falls kweb nicht verfügbar):
>
> ```bash
> chromium-browser \
>     --kiosk \
>     --noerrdialogs \
>     --disable-infobars \
>     --disable-translate \
>     --disable-features=TranslateUI \
>     --disable-session-crashed-bubble \
>     --disable-restore-session-state \
>     --autoplay-policy=no-user-gesture-required \
>     "$DASHBOARD_URL"
> ```

---

## 8. Systemd-Services einrichten

Statt den Start nur über `.bash_profile` zu steuern, verwenden wir zusätzlich Systemd-Services für mehr Kontrolle und Logging.

### 8.1 Kiosk-Service

```bash
sudo nano /etc/systemd/system/kiosk.service
```

```ini
[Unit]
Description=Feuerwehr Dashboard Kiosk
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
User=pi
Group=pi
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/pi/.Xauthority
WorkingDirectory=/home/pi/feuerwehr
ExecStartPre=/bin/sleep 5
ExecStart=/home/pi/feuerwehr/kiosk.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 8.2 Watchdog-Service

Der Watchdog überwacht den Kiosk-Prozess und den Dashboard-Service und startet beides bei Bedarf neu.

```bash
nano ~/feuerwehr/watchdog.sh
```

```bash
#!/usr/bin/env bash
#
# watchdog.sh – Überwacht Kiosk und Dashboard-Service

DASHBOARD_URL="http://localhost:8000"
CHECK_INTERVAL=30  # Sekunden zwischen Prüfungen
LOG_FILE="/var/log/kiosk-watchdog.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

log "Watchdog gestartet"

while true; do
    # Prüfen ob Dashboard erreichbar ist
    if ! curl -sf --max-time 5 "$DASHBOARD_URL/health" > /dev/null 2>&1; then
        log "WARNUNG: Dashboard nicht erreichbar – starte Docker-Services neu"
        cd /home/pi/feuerwehr && docker compose restart
    fi

    # Prüfen ob X-Display aktiv ist
    if ! DISPLAY=:0 xdpyinfo > /dev/null 2>&1; then
        log "WARNUNG: X-Display nicht aktiv – starte X-Server neu"
        sudo systemctl restart display-manager 2>/dev/null || \
            sudo systemctl restart kiosk.service
    fi

    sleep "$CHECK_INTERVAL"
done
```

```bash
chmod +x ~/feuerwehr/watchdog.sh
```

```bash
sudo nano /etc/systemd/system/kiosk-watchdog.service
```

```ini
[Unit]
Description=Feuerwehr Dashboard Watchdog
After=kiosk.service docker.service
Requires=docker.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/feuerwehr
ExecStart=/home/pi/feuerwehr/watchdog.sh
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### 8.3 Docker-Compose-Service

```bash
sudo nano /etc/systemd/system/feuerwehr-dashboard.service
```

```ini
[Unit]
Description=Feuerwehr Dashboard Docker Compose
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=forking
User=pi
WorkingDirectory=/home/pi/feuerwehr
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
RemainAfterExit=yes
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

### 8.4 Alle Services aktivieren

```bash
sudo systemctl daemon-reload
sudo systemctl enable feuerwehr-dashboard.service
sudo systemctl enable kiosk.service
sudo systemctl enable kiosk-watchdog.service

# Sofort starten (ohne Neustart)
sudo systemctl start feuerwehr-dashboard.service
sudo systemctl start kiosk.service
sudo systemctl start kiosk-watchdog.service
```

---

## 9. Splashscreen beim Boot

Beim Systemstart soll anstelle der Standard-Bootmeldungen ein eigener Splashscreen erscheinen ("Feuerwehr Dashboard lädt…").

### 9.1 Plymouth installieren und konfigurieren

```bash
sudo apt install -y plymouth plymouth-themes
```

### 9.2 Einfachen Text-Splashscreen erstellen

```bash
sudo mkdir -p /usr/share/plymouth/themes/feuerwehr
sudo nano /usr/share/plymouth/themes/feuerwehr/feuerwehr.plymouth
```

```ini
[Plymouth Theme]
Name=Feuerwehr Dashboard
Description=Feuerwehr Dashboard Ladebildschirm
ModuleName=text

[text]
Title=Feuerwehr Dashboard lädt...
SubTitle=Bitte warten...
```

```bash
sudo nano /usr/share/plymouth/themes/feuerwehr/feuerwehr.script
```

```
# Einfaches Plymouth-Script für Text-Splash
Window.SetBackgroundTopColor(0.8, 0.1, 0.1);   # Rot oben
Window.SetBackgroundBottomColor(0.5, 0.0, 0.0); # Dunkelrot unten

message_sprite = Sprite();
message_sprite.SetPosition(
    Window.GetWidth()  / 2 - 200,
    Window.GetHeight() / 2 - 20,
    10000
);

my_image = Image.Text("Feuerwehr Dashboard lädt...", 1.0, 1.0, 1.0);
message_sprite.SetImage(my_image);
```

```bash
# Theme aktivieren
sudo update-alternatives --install \
    /usr/share/plymouth/themes/default.plymouth \
    default.plymouth \
    /usr/share/plymouth/themes/feuerwehr/feuerwehr.plymouth 100

sudo update-alternatives --set \
    default.plymouth \
    /usr/share/plymouth/themes/feuerwehr/feuerwehr.plymouth

sudo update-initramfs -u
```

### 9.3 Stille Boot-Parameter setzen

```bash
sudo nano /boot/firmware/cmdline.txt
```

Am Ende der bestehenden Zeile folgende Parameter **ergänzen** (nicht ersetzen):

```
quiet splash plymouth.ignore-serial-consoles logo.nologo vt.global_cursor_default=0
```

> **Achtung:** Die gesamte `cmdline.txt` muss eine einzige Zeile ohne Zeilenumbrüche sein!

---

## 10. Alarm-Sound bei neuen Events

### 10.1 Sounddateien bereitstellen

```bash
mkdir -p ~/feuerwehr/sounds
```

Eigene Sounddatei (WAV-Format empfohlen) nach `~/feuerwehr/sounds/alarm.wav` kopieren. Alternativ eine Testdatei erstellen:

```bash
# Einfachen Testton mit sox generieren
sox -n ~/feuerwehr/sounds/alarm.wav \
    synth 3 sine 880 \
    synth 0.5 sine 1200 \
    gain -3
```

### 10.2 Audio-Ausgabe konfigurieren

```bash
# Verfügbare Audio-Geräte anzeigen
aplay -l

# Standard-Audio auf 3,5mm-Klinke setzen (falls HDMI-Audio nicht verwendet)
sudo raspi-config
# → System Options → Audio → 3.5mm Jack
```

Lautstärke dauerhaft setzen:

```bash
amixer set Master 85%
# Einstellungen speichern
sudo alsactl store
```

### 10.3 Alarm-Sound-Service erstellen

Das Dashboard meldet neue Alarme über eine Webhook-URL oder es wird zyklisch der `/api/alarms`-Endpunkt gepollt.

```bash
nano ~/feuerwehr/alarm-sound.sh
```

```bash
#!/usr/bin/env bash
#
# alarm-sound.sh – Überwacht neue Alarme und spielt Sound ab

DASHBOARD_URL="http://localhost:8000"
SOUND_FILE="/home/pi/feuerwehr/sounds/alarm.wav"
STATE_FILE="/tmp/last_alarm_id"
CHECK_INTERVAL=10  # Sekunden
LOG_FILE="/var/log/alarm-sound.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

log "Alarm-Sound-Service gestartet"

# Initialen Zustand setzen
LAST_ID=$(curl -sf "$DASHBOARD_URL/api/alarms/latest" 2>/dev/null | \
          python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',0))" 2>/dev/null || echo "0")
echo "$LAST_ID" > "$STATE_FILE"
log "Initialer letzter Alarm-ID: $LAST_ID"

while true; do
    sleep "$CHECK_INTERVAL"

    # Neuesten Alarm abrufen
    LATEST=$(curl -sf --max-time 5 "$DASHBOARD_URL/api/alarms/latest" 2>/dev/null)
    if [ -z "$LATEST" ]; then
        continue
    fi

    CURRENT_ID=$(echo "$LATEST" | \
        python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',0))" 2>/dev/null || echo "0")

    SAVED_ID=$(cat "$STATE_FILE" 2>/dev/null || echo "0")

    # Neuer Alarm erkannt
    if [ "$CURRENT_ID" != "$SAVED_ID" ] && [ "$CURRENT_ID" -gt "$SAVED_ID" ] 2>/dev/null; then
        log "Neuer Alarm erkannt (ID: $CURRENT_ID) – spiele Sound ab"
        echo "$CURRENT_ID" > "$STATE_FILE"

        # Sound 3x abspielen
        for i in 1 2 3; do
            aplay -q "$SOUND_FILE" 2>/dev/null || \
                sox "$SOUND_FILE" -d 2>/dev/null
            sleep 0.5
        done
    fi
done
```

```bash
chmod +x ~/feuerwehr/alarm-sound.sh
```

### 10.4 Alarm-Sound-Service als Systemd-Unit

```bash
sudo nano /etc/systemd/system/alarm-sound.service
```

```ini
[Unit]
Description=Feuerwehr Alarm Sound
After=feuerwehr-dashboard.service network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/feuerwehr
ExecStart=/home/pi/feuerwehr/alarm-sound.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable alarm-sound.service
sudo systemctl start alarm-sound.service
```

---

## 11. System starten & prüfen

### 11.1 Vollständiger Neustart

```bash
sudo reboot
```

Nach dem Neustart sollte folgende Sequenz ablaufen:

1. **Splashscreen** erscheint ("Feuerwehr Dashboard lädt…")
2. **Docker Compose** startet `alarm-monitor` und `alarm-mail`
3. **X-Server** startet automatisch (via `.bash_profile`)
4. **Openbox** öffnet sich mit dem `autostart`-Skript
5. **kiosk.sh** wartet, bis das Dashboard erreichbar ist
6. **kweb** öffnet das Dashboard im Vollbild

### 11.2 Status der Services prüfen

```bash
# Alle Systemd-Services prüfen
sudo systemctl status feuerwehr-dashboard.service
sudo systemctl status kiosk.service
sudo systemctl status kiosk-watchdog.service
sudo systemctl status alarm-sound.service

# Docker Container prüfen
docker compose -f ~/feuerwehr/docker-compose.yml ps
docker compose -f ~/feuerwehr/docker-compose.yml logs --tail=50

# Dashboard-Gesundheitscheck
curl http://localhost:8000/health
```

### 11.3 Log-Dateien prüfen

```bash
# Kiosk-Logs
tail -f /var/log/kiosk.log

# Watchdog-Logs
tail -f /var/log/kiosk-watchdog.log

# Alarm-Sound-Logs
tail -f /var/log/alarm-sound.log

# Systemd Journal (alle Services)
journalctl -u kiosk.service -u kiosk-watchdog.service \
           -u alarm-sound.service -u feuerwehr-dashboard.service \
           -f --since "1 hour ago"
```

### 11.4 Testalarm senden

```bash
# Testalarm über die API auslösen
curl -X POST http://localhost:8000/api/alarm \
    -H "Content-Type: application/json" \
    -d '{
        "keyword": "TEST",
        "location": "Feuerwehrhaus",
        "details": "Dies ist ein Testalarm"
    }'
```

---

## 12. Optimierungen für Stabilität & Ressourcen

### 12.1 Speicherkarte schonen (Overlay-Filesystem)

Häufige Schreibzugriffe auf die SD-Karte können diese langfristig beschädigen. Ein Read-Only-Root-Filesystem mit Overlay verhindert dies:

```bash
sudo raspi-config
```

`Performance Options` → `Overlay File System` → **aktivieren**

> **Achtung:** Nach Aktivierung können keine dauerhaften Änderungen mehr vorgenommen werden! Temporäre Deaktivierung über `raspi-config` möglich.

### 12.2 Unnötige Dienste deaktivieren

```bash
# Dienste deaktivieren, die auf einem Kiosk nicht benötigt werden
sudo systemctl disable \
    bluetooth.service \
    hciuart.service \
    avahi-daemon.service \
    triggerhappy.service \
    rsyslog.service

# Bluetooth im Kernel deaktivieren
echo "dtoverlay=disable-bt" | sudo tee -a /boot/firmware/config.txt
```

### 12.3 RAM-Verbrauch reduzieren

```bash
sudo nano /boot/firmware/config.txt
```

Folgende Zeilen hinzufügen oder anpassen:

```ini
# GPU-Speicher auf Minimum reduzieren (Kiosk-Modus)
gpu_mem=64

# HDMI-Auflösung erzwingen (verhindert HDMI-Hotplug-Probleme)
hdmi_force_hotplug=1
hdmi_group=1
hdmi_mode=16        # 1080p 60Hz – bei Bedarf anpassen

# Overclock für RPi 3 (optional, nur mit ausreichender Kühlung!)
# arm_freq=1300
# over_voltage=4
```

### 12.4 Automatische Updates deaktivieren

```bash
sudo systemctl disable apt-daily.service
sudo systemctl disable apt-daily-upgrade.service
sudo systemctl disable apt-daily.timer
sudo systemctl disable apt-daily-upgrade.timer
```

> Updates sollten manuell zu einem kontrollierten Zeitpunkt durchgeführt werden:
>
> ```bash
> sudo apt update && sudo apt upgrade -y
> ```

### 12.5 Nightly-Neustart einrichten

Ein täglicher Neustart in den frühen Morgenstunden sorgt für einen sauberen Systemzustand:

```bash
sudo crontab -e
```

Zeile hinzufügen:

```cron
# Täglicher Neustart um 03:00 Uhr
0 3 * * * /sbin/reboot
```

### 12.6 Docker-Ressourcen begrenzen

In der `docker-compose.yml` können Ressourcenlimits gesetzt werden, um den RPi 3 nicht zu überlasten:

```yaml
services:
  alarm-monitor:
    # ... (bestehende Konfiguration)
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "0.8"

  alarm-mail:
    # ... (bestehende Konfiguration)
    deploy:
      resources:
        limits:
          memory: 128M
          cpus: "0.3"
```

---

## 13. Optional: Netzwerk- & Soundeinstellungen

### 13.1 Statische IP-Adresse (empfohlen)

Eine feste IP-Adresse verhindert Probleme, wenn sich die IP nach einem Neustart ändert.

```bash
sudo nano /etc/dhcpcd.conf
```

Am Ende der Datei hinzufügen (Werte anpassen):

```
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 8.8.8.8

# Für WLAN:
# interface wlan0
# static ip_address=192.168.1.101/24
# static routers=192.168.1.1
# static domain_name_servers=192.168.1.1 8.8.8.8
```

```bash
sudo systemctl restart dhcpcd
```

### 13.2 WLAN-Verbindung manuell einrichten

```bash
sudo raspi-config
```

`System Options` → `Wireless LAN` → SSID und Passwort eingeben

Oder manuell:

```bash
sudo nano /etc/wpa_supplicant/wpa_supplicant.conf
```

```
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=DE

network={
    ssid="DEIN-WLAN-NAME"
    psk="DEIN-WLAN-PASSWORT"
    key_mgmt=WPA-PSK
    priority=1
}
```

```bash
wpa_cli -i wlan0 reconfigure
```

### 13.3 Audio über HDMI ausgeben

```bash
# HDMI-Audio aktivieren
sudo raspi-config
# → System Options → Audio → HDMI 1 (oder HDMI 2)

# Test
speaker-test -c2 -t wav -l1

# Oder mit aplay
aplay /usr/share/sounds/alsa/Front_Left.wav
```

### 13.4 Lautstärke-Profil dauerhaft speichern

```bash
# Lautstärke auf 85% setzen
amixer set Master 85%

# Konfiguration dauerhaft speichern
sudo alsactl store

# Test
aplay ~/feuerwehr/sounds/alarm.wav
```

### 13.5 Netzwerk-Watchdog (NetworkManager)

```bash
sudo apt install -y network-manager
sudo systemctl enable NetworkManager
```

Automatische WLAN-Wiederverbindung konfigurieren:

```bash
nmcli connection modify "DEIN-WLAN-NAME" \
    connection.autoconnect yes \
    connection.autoconnect-priority 10
```

---

## 14. Fazit

Dieses Setup verwandelt einen **Raspberry Pi 3** in ein vollständig autonomes, wartungsarmes **Feuerwehr-Dashboard-Terminal**:

### Gesamtarchitektur im Überblick

```
┌─────────────────────────────────────────────────────┐
│                  Raspberry Pi 3                      │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │          Docker (feuerwehr-dashboard)        │   │
│  │                                             │   │
│  │  ┌─────────────────┐  ┌──────────────────┐  │   │
│  │  │  alarm-monitor  │  │   alarm-mail     │  │   │
│  │  │  :8000          │◄─┤  (IMAP-Poller)   │  │   │
│  │  │  (Dashboard)    │  │                  │  │   │
│  │  └─────────────────┘  └──────────────────┘  │   │
│  └─────────────────────────────────────────────┘   │
│                       ▲                            │
│                       │ HTTP                       │
│  ┌─────────────────────────────────────────────┐   │
│  │    X-Server + Openbox + kweb (Kiosk)        │   │
│  │    → Vollbild-Browser auf HDMI-Display      │   │
│  └─────────────────────────────────────────────┘   │
│                                                     │
│  Systemd-Services:                                  │
│  • feuerwehr-dashboard  → Docker Compose           │
│  • kiosk                → X + Browser              │
│  • kiosk-watchdog       → Überwachung & Neustart   │
│  • alarm-sound          → Audio bei Alarmen        │
└─────────────────────────────────────────────────────┘
         │                           │
         ▼                           ▼
   HDMI-Display               3,5mm / HDMI-Audio
   (Vollbild-Dashboard)       (Alarm-Sound)
```

### Wichtigste Eigenschaften des Setups

| Feature | Lösung |
|---------|--------|
| **Betriebssystem** | Raspberry Pi OS Lite (minimal, kein Desktop) |
| **Container-Engine** | Docker + Docker Compose |
| **Dashboard-Backend** | alarm-monitor (Python/Flask) |
| **E-Mail-Integration** | alarm-mail (IMAP-Poller) |
| **Browser (Kiosk)** | kweb (schlanker Webkit-Browser) |
| **Fenstermanager** | Openbox (minimaler X-Fenstermanager) |
| **Watchdog** | Systemd + Shell-Skript |
| **Splashscreen** | Plymouth (Text-Theme in Feuerwehr-Rot) |
| **Alarm-Audio** | aplay / sox + Polling-Skript |
| **Ausfallsicherheit** | Systemd `Restart=always` + nächtlicher Reboot |
| **SD-Karten-Schutz** | Overlay-Filesystem (optional) |

### Nächste Schritte

- **Testen:** Testalarm senden und Reaktion des Systems prüfen
- **Feintuning:** Lautstärke, Bildschirmauflösung und URLs nach Bedarf anpassen
- **Monitoring:** Fernzugriff per SSH für Wartungsarbeiten sicherstellen
- **Backup:** SD-Karte nach erfolgreicher Einrichtung sichern (`dd`-Image)
- **Updates:** Regelmäßige Updates von Docker-Images und Systempaketen einplanen

```bash
# SD-Karten-Backup erstellen (auf anderem Rechner)
sudo dd if=/dev/sdX bs=4M status=progress | gzip > feuerwehr-dashboard-backup.img.gz

# Backup wiederherstellen
gunzip -c feuerwehr-dashboard-backup.img.gz | sudo dd of=/dev/sdX bs=4M status=progress
```

---

> 💡 **Tipp:** Für Produktionsbetrieb wird empfohlen, das Overlay-Filesystem zu aktivieren und regelmäßige SD-Karten-Backups durchzuführen. SD-Karten haben eine begrenzte Anzahl von Schreibzyklen und können bei Dauerbetrieb nach einigen Jahren ausfallen.

---

<div align="center">

**Probleme oder Fragen?**  
[GitHub Issues](https://github.com/TimUx/alarm-monitor/issues) | [FAQ](FAQ.md) | [Betriebshandbuch](../Betriebshandbuch.md)

[⬆ Zurück nach oben](#-raspberry-pi-3--installationsanleitung-feuerwehr-dashboard)

</div>
