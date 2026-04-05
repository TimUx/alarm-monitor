#!/usr/bin/env bash
# =============================================================================
# rpi-setup.sh – Feuerwehr Dashboard: vollautomatisches Einrichtungsskript
#
# Basiert auf: docs/RASPBERRY_PI_SETUP.md
# Getestet auf: Raspberry Pi OS Lite 64-bit (Bookworm)
# Ausführen als: pi (mit sudo-Rechten)
#
# Verwendung:
#   chmod +x rpi-setup.sh
#   ./rpi-setup.sh
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Farb-Hilfsfunktionen
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[1;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

step()    { echo -e "\n${BLUE}${BOLD}▶ $*${NC}"; }
ok()      { echo -e "  ${GREEN}✔ $*${NC}"; }
warn()    { echo -e "  ${YELLOW}⚠ $*${NC}"; }
info()    { echo -e "  ${CYAN}ℹ $*${NC}"; }
die()     { echo -e "\n${RED}${BOLD}✘ FEHLER: $*${NC}\n" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Voraussetzungen prüfen
# ---------------------------------------------------------------------------
[[ $EUID -eq 0 ]] && die "Dieses Skript NICHT als root ausführen. Als Benutzer 'pi' starten (sudo wird intern verwendet)."
command -v sudo >/dev/null 2>&1 || die "sudo ist nicht installiert."

SCRIPT_USER="${USER}"
HOME_DIR="${HOME}"
FEUERWEHR_DIR="${HOME_DIR}/feuerwehr"

echo -e "\n${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║        🚒  Feuerwehr Dashboard – RPi Einrichtung             ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}\n"
echo -e "  Benutzer    : ${CYAN}${SCRIPT_USER}${NC}"
echo -e "  Heimverzeichnis : ${CYAN}${HOME_DIR}${NC}"
echo -e "  Arbeitsordner   : ${CYAN}${FEUERWEHR_DIR}${NC}\n"

# ---------------------------------------------------------------------------
# Interaktive Konfiguration
# ---------------------------------------------------------------------------
step "Konfiguration erfassen"

prompt_value() {
    local var_name="$1"
    local prompt_text="$2"
    local default_val="${3:-}"
    local is_secret="${4:-false}"
    local value

    while true; do
        if [[ "$is_secret" == "true" ]]; then
            read -rsp "  ${prompt_text}${default_val:+ [Standard: ***]}: " value
            echo
        else
            read -rp  "  ${prompt_text}${default_val:+ [Standard: ${default_val}]}: " value
        fi
        value="${value:-${default_val}}"
        if [[ -n "$value" ]]; then
            printf -v "$var_name" '%s' "$value"
            break
        fi
        warn "Eingabe darf nicht leer sein."
    done
}

# alarm-monitor
prompt_value SECRET_KEY        "alarm-monitor SECRET_KEY"             "$(openssl rand -hex 32)"  "true"
prompt_value ADMIN_PASSWORD    "alarm-monitor ADMIN_PASSWORD"         ""                          "true"
prompt_value ORS_API_KEY       "OpenRouteService API-Key (optional)"  "leer-lassen"               "false"

# alarm-mail
prompt_value IMAP_HOST         "IMAP-Server (z.B. mail.example.com)"  ""  "false"
prompt_value IMAP_PORT         "IMAP-Port"                            "993" "false"
prompt_value IMAP_USER         "IMAP-Benutzername"                   ""  "false"
prompt_value IMAP_PASSWORD     "IMAP-Passwort"                       ""  "true"
prompt_value IMAP_FOLDER       "IMAP-Ordner"                         "INBOX" "false"
prompt_value ALARM_MONITOR_TOKEN "API-Token für alarm-monitor"       "$(openssl rand -hex 24)" "true"

echo ""
info "Konfiguration erfasst. Setup wird gestartet..."
sleep 1

# ---------------------------------------------------------------------------
# Schritt 1 – System aktualisieren
# ---------------------------------------------------------------------------
step "System aktualisieren"
sudo apt-get update -qq
sudo apt-get full-upgrade -y -qq
sudo apt-get autoremove -y -qq
ok "System ist auf dem neuesten Stand."

# ---------------------------------------------------------------------------
# Schritt 2 – Pakete installieren
# ---------------------------------------------------------------------------
step "Notwendige Pakete installieren"
sudo apt-get install -y -qq \
    git curl wget unzip \
    xorg xinit openbox unclutter \
    alsa-utils sox \
    fonts-dejavu-core \
    ca-certificates gnupg lsb-release \
    plymouth plymouth-themes
ok "Pakete installiert."

# ---------------------------------------------------------------------------
# Schritt 3 – Swap vergrößern
# ---------------------------------------------------------------------------
step "Swap auf 512 MB vergrößern"
if grep -q "CONF_SWAPSIZE=100" /etc/dphys-swapfile 2>/dev/null; then
    sudo dphys-swapfile swapoff
    sudo sed -i 's/CONF_SWAPSIZE=100/CONF_SWAPSIZE=512/' /etc/dphys-swapfile
    sudo dphys-swapfile setup
    sudo dphys-swapfile swapon
    ok "Swap auf 512 MB vergrößert."
else
    info "Swap-Größe bereits angepasst oder Standardwert abweichend – übersprungen."
fi

# ---------------------------------------------------------------------------
# Schritt 4 – Docker & Docker Compose installieren
# ---------------------------------------------------------------------------
step "Docker installieren"
if command -v docker >/dev/null 2>&1; then
    info "Docker ist bereits installiert ($(docker --version))."
else
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
    sudo sh /tmp/get-docker.sh
    rm /tmp/get-docker.sh
    ok "Docker installiert."
fi

sudo usermod -aG docker "${SCRIPT_USER}"
ok "Benutzer '${SCRIPT_USER}' zur Docker-Gruppe hinzugefügt."

step "Docker Compose installieren"
if docker compose version >/dev/null 2>&1; then
    info "Docker Compose bereits verfügbar ($(docker compose version))."
else
    sudo apt-get install -y -qq docker-compose-plugin
    ok "Docker Compose installiert."
fi

sudo systemctl enable docker
sudo systemctl start docker
ok "Docker-Service aktiviert und gestartet."

# ---------------------------------------------------------------------------
# Schritt 5 – Ordnerstruktur & Konfigurationsdateien erstellen
# ---------------------------------------------------------------------------
step "Ordnerstruktur anlegen"
mkdir -p "${FEUERWEHR_DIR}"/{alarm-monitor,alarm-mail,sounds}
mkdir -p "${FEUERWEHR_DIR}/alarm-monitor/instance"
ok "Verzeichnisse angelegt unter ${FEUERWEHR_DIR}."

step "alarm-monitor .env erstellen"
cat > "${FEUERWEHR_DIR}/alarm-monitor/.env" <<EOF
# Allgemein
TZ=Europe/Berlin
SECRET_KEY=${SECRET_KEY}

# Datenbank
DATABASE_URL=sqlite:///instance/alarms.db

# Authentifizierung
ADMIN_PASSWORD=${ADMIN_PASSWORD}

# API-Einstellungen
GEOCODING_PROVIDER=nominatim
ORS_API_KEY=${ORS_API_KEY}
EOF
ok "${FEUERWEHR_DIR}/alarm-monitor/.env erstellt."

step "alarm-mail .env erstellen"
cat > "${FEUERWEHR_DIR}/alarm-mail/.env" <<EOF
TZ=Europe/Berlin

# IMAP-Postfach
IMAP_HOST=${IMAP_HOST}
IMAP_PORT=${IMAP_PORT}
IMAP_USER=${IMAP_USER}
IMAP_PASSWORD=${IMAP_PASSWORD}
IMAP_SSL=true
IMAP_FOLDER=${IMAP_FOLDER}

# alarm-monitor Endpunkt
ALARM_MONITOR_URL=http://alarm-monitor:8000/api/alarm
ALARM_MONITOR_TOKEN=${ALARM_MONITOR_TOKEN}
EOF
ok "${FEUERWEHR_DIR}/alarm-mail/.env erstellt."

step "docker-compose.yml erstellen"
cat > "${FEUERWEHR_DIR}/docker-compose.yml" <<'EOF'
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
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "0.8"

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
    deploy:
      resources:
        limits:
          memory: 128M
          cpus: "0.3"

networks:
  alarm-net:
    driver: bridge
EOF
ok "${FEUERWEHR_DIR}/docker-compose.yml erstellt."

# ---------------------------------------------------------------------------
# Schritt 6 – kweb im Kiosk-Modus installieren
# ---------------------------------------------------------------------------
step "kweb / Kiosk-Browser installieren"
if sudo apt-get install -y -qq kweb 2>/dev/null; then
    KIOSK_CMD="kweb --kiosk --fullscreen --no-sandbox --disable-cache"
    ok "kweb installiert."
else
    warn "kweb nicht im Repository gefunden – Chromium wird als Fallback installiert."
    sudo apt-get install -y -qq chromium-browser
    KIOSK_CMD="chromium-browser --kiosk --noerrdialogs --disable-infobars --disable-translate \
--disable-features=TranslateUI --disable-session-crashed-bubble \
--disable-restore-session-state --autoplay-policy=no-user-gesture-required"
    ok "Chromium als Kiosk-Browser installiert."
fi

step "Openbox-Autostart konfigurieren"
mkdir -p "${HOME_DIR}/.config/openbox"
cat > "${HOME_DIR}/.config/openbox/autostart" <<'EOF'
# Bildschirmschoner & Energiesparmodus deaktivieren
xset s off &
xset s noblank &
xset -dpms &

# Mauszeiger ausblenden (nach 0.1 Sekunden Inaktivität)
unclutter -idle 0.1 -root &

# Kiosk-Browser starten
/home/pi/feuerwehr/kiosk.sh &
EOF
ok "Openbox-Autostart konfiguriert."

step "Automatischen X-Start in .bash_profile eintragen"
BASH_PROFILE="${HOME_DIR}/.bash_profile"
touch "${BASH_PROFILE}"
if ! grep -q "startx" "${BASH_PROFILE}" 2>/dev/null; then
    cat >> "${BASH_PROFILE}" <<'EOF'

# X-Server starten (nur auf tty1, nur wenn noch kein Display vorhanden)
if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
    exec startx -- -nocursor
fi
EOF
    ok ".bash_profile aktualisiert."
else
    info "startx-Eintrag in .bash_profile bereits vorhanden."
fi

# ---------------------------------------------------------------------------
# Schritt 7 – kiosk.sh erstellen
# ---------------------------------------------------------------------------
step "kiosk.sh erstellen"
cat > "${FEUERWEHR_DIR}/kiosk.sh" <<EOF
#!/usr/bin/env bash
#
# kiosk.sh – Feuerwehr Dashboard Kiosk
# Startet den Browser im Kiosk-Modus und neustartet bei Absturz automatisch.

DASHBOARD_URL="http://localhost:8000"
LOG_FILE="/var/log/kiosk.log"
RESTART_DELAY=5

echo "[\$(date)] Kiosk-Script gestartet" >> "\$LOG_FILE"

echo "[\$(date)] Warte auf Dashboard-Service..." >> "\$LOG_FILE"
until curl -sf "\${DASHBOARD_URL}/health" > /dev/null 2>&1; do
    echo "[\$(date)] Dashboard noch nicht erreichbar, warte \${RESTART_DELAY}s..." >> "\$LOG_FILE"
    sleep "\$RESTART_DELAY"
done
echo "[\$(date)] Dashboard erreichbar, starte Browser" >> "\$LOG_FILE"

while true; do
    echo "[\$(date)] Starte Browser..." >> "\$LOG_FILE"

    ${KIOSK_CMD} "\${DASHBOARD_URL}" >> "\$LOG_FILE" 2>&1

    EXIT_CODE=\$?
    echo "[\$(date)] Browser beendet (Exit-Code: \${EXIT_CODE}), Neustart in \${RESTART_DELAY}s..." >> "\$LOG_FILE"
    sleep "\$RESTART_DELAY"
done
EOF
chmod +x "${FEUERWEHR_DIR}/kiosk.sh"
ok "kiosk.sh erstellt und ausführbar gemacht."

# ---------------------------------------------------------------------------
# Schritt 8 – watchdog.sh erstellen
# ---------------------------------------------------------------------------
step "watchdog.sh erstellen"
cat > "${FEUERWEHR_DIR}/watchdog.sh" <<'EOF'
#!/usr/bin/env bash
#
# watchdog.sh – Überwacht Kiosk und Dashboard-Service

DASHBOARD_URL="http://localhost:8000"
CHECK_INTERVAL=30
LOG_FILE="/var/log/kiosk-watchdog.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

log "Watchdog gestartet"

while true; do
    if ! curl -sf --max-time 5 "$DASHBOARD_URL/health" > /dev/null 2>&1; then
        log "WARNUNG: Dashboard nicht erreichbar – starte Docker-Services neu"
        cd /home/pi/feuerwehr && docker compose restart
    fi

    if ! DISPLAY=:0 xdpyinfo > /dev/null 2>&1; then
        log "WARNUNG: X-Display nicht aktiv – starte Kiosk-Service neu"
        sudo systemctl restart kiosk.service
    fi

    sleep "$CHECK_INTERVAL"
done
EOF
chmod +x "${FEUERWEHR_DIR}/watchdog.sh"
ok "watchdog.sh erstellt und ausführbar gemacht."

# ---------------------------------------------------------------------------
# Schritt 9 – alarm-sound.sh erstellen
# ---------------------------------------------------------------------------
step "alarm-sound.sh erstellen"
cat > "${FEUERWEHR_DIR}/alarm-sound.sh" <<'EOF'
#!/usr/bin/env bash
#
# alarm-sound.sh – Überwacht neue Alarme und spielt Sound ab

DASHBOARD_URL="http://localhost:8000"
SOUND_FILE="/home/pi/feuerwehr/sounds/alarm.wav"
STATE_FILE="/tmp/last_alarm_id"
CHECK_INTERVAL=10
LOG_FILE="/var/log/alarm-sound.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

log "Alarm-Sound-Service gestartet"

LAST_ID=$(curl -sf "$DASHBOARD_URL/api/alarms/latest" 2>/dev/null | \
          python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',0))" 2>/dev/null || echo "0")
echo "$LAST_ID" > "$STATE_FILE"
log "Initialer letzter Alarm-ID: $LAST_ID"

while true; do
    sleep "$CHECK_INTERVAL"

    LATEST=$(curl -sf --max-time 5 "$DASHBOARD_URL/api/alarms/latest" 2>/dev/null)
    if [ -z "$LATEST" ]; then
        continue
    fi

    CURRENT_ID=$(echo "$LATEST" | \
        python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',0))" 2>/dev/null || echo "0")

    SAVED_ID=$(cat "$STATE_FILE" 2>/dev/null || echo "0")

    if [ "$CURRENT_ID" != "$SAVED_ID" ] && [ "$CURRENT_ID" -gt "$SAVED_ID" ] 2>/dev/null; then
        log "Neuer Alarm erkannt (ID: $CURRENT_ID) – spiele Sound ab"
        echo "$CURRENT_ID" > "$STATE_FILE"

        for i in 1 2 3; do
            aplay -q "$SOUND_FILE" 2>/dev/null || \
                sox "$SOUND_FILE" -d 2>/dev/null
            sleep 0.5
        done
    fi
done
EOF
chmod +x "${FEUERWEHR_DIR}/alarm-sound.sh"
ok "alarm-sound.sh erstellt und ausführbar gemacht."

step "Test-Alarm-Ton generieren"
if [ ! -f "${FEUERWEHR_DIR}/sounds/alarm.wav" ]; then
    if command -v sox >/dev/null 2>&1; then
        sox -n "${FEUERWEHR_DIR}/sounds/alarm.wav" \
            synth 3 sine 880 \
            synth 0.5 sine 1200 \
            gain -3 2>/dev/null || warn "Test-Ton konnte nicht generiert werden."
        ok "Test-Alarm-Ton erstellt: ${FEUERWEHR_DIR}/sounds/alarm.wav"
    else
        warn "sox nicht verfügbar – Test-Ton übersprungen."
    fi
else
    info "alarm.wav bereits vorhanden – übersprungen."
fi

# ---------------------------------------------------------------------------
# Schritt 10 – Systemd-Services einrichten
# ---------------------------------------------------------------------------
step "Systemd-Services einrichten"

# feuerwehr-dashboard.service
sudo tee /etc/systemd/system/feuerwehr-dashboard.service > /dev/null <<EOF
[Unit]
Description=Feuerwehr Dashboard Docker Compose
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=forking
User=${SCRIPT_USER}
WorkingDirectory=${FEUERWEHR_DIR}
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
RemainAfterExit=yes
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF
ok "feuerwehr-dashboard.service erstellt."

# kiosk.service
sudo tee /etc/systemd/system/kiosk.service > /dev/null <<EOF
[Unit]
Description=Feuerwehr Dashboard Kiosk
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=simple
User=${SCRIPT_USER}
Group=${SCRIPT_USER}
Environment=DISPLAY=:0
Environment=XAUTHORITY=${HOME_DIR}/.Xauthority
WorkingDirectory=${FEUERWEHR_DIR}
ExecStartPre=/bin/sleep 5
ExecStart=${FEUERWEHR_DIR}/kiosk.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
ok "kiosk.service erstellt."

# kiosk-watchdog.service
sudo tee /etc/systemd/system/kiosk-watchdog.service > /dev/null <<EOF
[Unit]
Description=Feuerwehr Dashboard Watchdog
After=kiosk.service docker.service
Requires=docker.service

[Service]
Type=simple
User=${SCRIPT_USER}
WorkingDirectory=${FEUERWEHR_DIR}
ExecStart=${FEUERWEHR_DIR}/watchdog.sh
Restart=always
RestartSec=15
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
ok "kiosk-watchdog.service erstellt."

# alarm-sound.service
sudo tee /etc/systemd/system/alarm-sound.service > /dev/null <<EOF
[Unit]
Description=Feuerwehr Alarm Sound
After=feuerwehr-dashboard.service network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SCRIPT_USER}
WorkingDirectory=${FEUERWEHR_DIR}
ExecStart=${FEUERWEHR_DIR}/alarm-sound.sh
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
ok "alarm-sound.service erstellt."

sudo systemctl daemon-reload
sudo systemctl enable feuerwehr-dashboard.service kiosk.service kiosk-watchdog.service alarm-sound.service
ok "Alle Services aktiviert (starten automatisch nach Neustart)."

# ---------------------------------------------------------------------------
# Schritt 11 – Plymouth-Splashscreen einrichten
# ---------------------------------------------------------------------------
step "Plymouth-Splashscreen einrichten"
sudo mkdir -p /usr/share/plymouth/themes/feuerwehr

sudo tee /usr/share/plymouth/themes/feuerwehr/feuerwehr.plymouth > /dev/null <<'EOF'
[Plymouth Theme]
Name=Feuerwehr Dashboard
Description=Feuerwehr Dashboard Ladebildschirm
ModuleName=text

[text]
Title=Feuerwehr Dashboard lädt...
SubTitle=Bitte warten...
EOF

sudo tee /usr/share/plymouth/themes/feuerwehr/feuerwehr.script > /dev/null <<'EOF'
Window.SetBackgroundTopColor(0.8, 0.1, 0.1);
Window.SetBackgroundBottomColor(0.5, 0.0, 0.0);

message_sprite = Sprite();
message_sprite.SetPosition(
    Window.GetWidth()  / 2 - 200,
    Window.GetHeight() / 2 - 20,
    10000
);

my_image = Image.Text("Feuerwehr Dashboard lädt...", 1.0, 1.0, 1.0);
message_sprite.SetImage(my_image);
EOF

sudo update-alternatives --install \
    /usr/share/plymouth/themes/default.plymouth \
    default.plymouth \
    /usr/share/plymouth/themes/feuerwehr/feuerwehr.plymouth 100

sudo update-alternatives --set \
    default.plymouth \
    /usr/share/plymouth/themes/feuerwehr/feuerwehr.plymouth

sudo update-initramfs -u 2>/dev/null || warn "update-initramfs fehlgeschlagen – Splashscreen evtl. ohne Wirkung bis zum nächsten Kernel-Update."
ok "Plymouth-Splashscreen eingerichtet."

# ---------------------------------------------------------------------------
# Schritt 12 – Stille Boot-Parameter setzen
# ---------------------------------------------------------------------------
step "Stille Boot-Parameter konfigurieren"
CMDLINE_FILE="/boot/firmware/cmdline.txt"
if [ -f "$CMDLINE_FILE" ]; then
    if ! grep -q "quiet splash" "$CMDLINE_FILE"; then
        sudo sed -i 's/$/ quiet splash plymouth.ignore-serial-consoles logo.nologo vt.global_cursor_default=0/' "$CMDLINE_FILE"
        ok "Boot-Parameter gesetzt."
    else
        info "Boot-Parameter bereits vorhanden."
    fi
else
    warn "${CMDLINE_FILE} nicht gefunden – Boot-Parameter nicht gesetzt."
fi

# ---------------------------------------------------------------------------
# Schritt 13 – config.txt Optimierungen
# ---------------------------------------------------------------------------
step "Raspberry Pi config.txt optimieren"
CONFIG_FILE="/boot/firmware/config.txt"
if [ -f "$CONFIG_FILE" ]; then
    # GPU-Speicher
    if ! grep -q "^gpu_mem=" "$CONFIG_FILE"; then
        echo -e "\n# GPU-Speicher auf Minimum (Kiosk-Modus)\ngpu_mem=64" | sudo tee -a "$CONFIG_FILE" > /dev/null
    fi
    # HDMI erzwingen
    if ! grep -q "hdmi_force_hotplug" "$CONFIG_FILE"; then
        cat <<'EOF' | sudo tee -a "$CONFIG_FILE" > /dev/null

# HDMI-Auflösung erzwingen
hdmi_force_hotplug=1
hdmi_group=1
hdmi_mode=16
EOF
    fi
    # Bluetooth deaktivieren
    if ! grep -q "disable-bt" "$CONFIG_FILE"; then
        echo "dtoverlay=disable-bt" | sudo tee -a "$CONFIG_FILE" > /dev/null
    fi
    ok "config.txt optimiert."
else
    warn "${CONFIG_FILE} nicht gefunden – übersprungen."
fi

# ---------------------------------------------------------------------------
# Schritt 14 – Automatischen Login einrichten (Console Autologin)
# ---------------------------------------------------------------------------
step "Automatischen Console-Login einrichten"
# raspi-config non-interactiv: boot_behaviour B2 = Console Autologin
if command -v raspi-config >/dev/null 2>&1; then
    sudo raspi-config nonint do_boot_behaviour B2
    ok "Console-Autologin aktiviert."
else
    warn "raspi-config nicht gefunden – Autologin manuell in raspi-config → System Options → Boot/Auto Login aktivieren."
fi

# ---------------------------------------------------------------------------
# Schritt 15 – Optimierungen (unnötige Dienste deaktivieren)
# ---------------------------------------------------------------------------
step "Unnötige Dienste deaktivieren"
for svc in bluetooth.service hciuart.service avahi-daemon.service triggerhappy.service \
           apt-daily.service apt-daily-upgrade.service apt-daily.timer apt-daily-upgrade.timer; do
    sudo systemctl disable --now "$svc" 2>/dev/null || true
done
ok "Unnötige Dienste deaktiviert."

# ---------------------------------------------------------------------------
# Schritt 16 – Nightly-Neustart einrichten
# ---------------------------------------------------------------------------
step "Nächtlichen Neustart (03:00 Uhr) einrichten"
if ! sudo crontab -l 2>/dev/null | grep -q "reboot"; then
    (sudo crontab -l 2>/dev/null; echo "0 3 * * * /sbin/reboot") | sudo crontab -
    ok "Cron-Job für täglichen Neustart um 03:00 Uhr eingerichtet."
else
    info "Reboot-Cron bereits vorhanden."
fi

# ---------------------------------------------------------------------------
# Schritt 17 – Docker Images laden (erster Test)
# ---------------------------------------------------------------------------
step "Docker Images herunterladen"
info "Dies kann auf dem RPi 3 einige Minuten dauern..."
# newgrp docker würde die Shell verlassen, daher via sg ausführen
sg docker -c "docker compose -f ${FEUERWEHR_DIR}/docker-compose.yml pull" || \
    warn "Docker pull fehlgeschlagen – entweder ist die Gruppe noch nicht aktiv (Neustart nötig) oder das Image nicht erreichbar."

# ---------------------------------------------------------------------------
# Abschluss
# ---------------------------------------------------------------------------
echo -e "\n${BOLD}${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║          ✅  Setup abgeschlossen!                            ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}\n"

echo -e "  ${BOLD}Nächste Schritte:${NC}"
echo -e "  1. System neu starten:   ${CYAN}sudo reboot${NC}"
echo -e "  2. Nach dem Neustart prüfen:"
echo -e "     ${CYAN}sudo systemctl status feuerwehr-dashboard.service${NC}"
echo -e "     ${CYAN}sudo systemctl status kiosk.service${NC}"
echo -e "     ${CYAN}docker compose -f ~/feuerwehr/docker-compose.yml ps${NC}"
echo -e "  3. Dashboard aufrufen:   ${CYAN}http://localhost:8000${NC}"
echo -e "  4. Testalarm senden:"
echo -e "     ${CYAN}curl -X POST http://localhost:8000/api/alarm \\\\"
echo -e "       -H 'Content-Type: application/json' \\\\"
echo -e "       -d '{\"keyword\":\"TEST\",\"location\":\"Feuerwehrhaus\",\"details\":\"Testalarm\"}'${NC}"
echo -e "\n  ${YELLOW}Hinweis: Audio-Ausgabe bitte manuell via${NC} ${CYAN}sudo raspi-config${NC}"
echo -e "  ${YELLOW}→ System Options → Audio festlegen (3,5mm-Klinke oder HDMI).${NC}"
echo -e "\n  ${YELLOW}Eigene Alarm-Sounddatei ablegen unter:${NC}"
echo -e "  ${CYAN}${FEUERWEHR_DIR}/sounds/alarm.wav${NC}\n"
