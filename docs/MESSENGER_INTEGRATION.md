# 📱 Alarm-Messenger Integration

Dieses Dokument beschreibt die Integration zwischen dem Alarm-Monitor und dem [Alarm-Messenger System](https://github.com/TimUx/alarm-messenger) für mobile Push-Benachrichtigungen und Teilnehmerrückmeldungen.

---

## Inhaltsverzeichnis

- [Überblick](#überblick)
- [Systemübersicht](#systemübersicht)
- [Datenfluss](#datenfluss)
- [Installation](#installation)
- [Konfiguration](#konfiguration)
- [API-Endpunkte](#api-endpunkte)
- [Payload-Formate](#payload-formate)
- [Teilnehmerrückmeldungen](#teilnehmerrückmeldungen)
- [Fehlerbehandlung](#fehlerbehandlung)
- [Testen](#testen)
- [Sicherheit](#sicherheit)

---

## Überblick

Der **alarm-messenger** ist eine **optionale** Komponente, die folgende Funktionen bietet:

✅ **Push-Benachrichtigungen**: Mobile Alarmierung auf iOS und Android  
✅ **Teilnehmerrückmeldungen**: Zusagen/Absagen von Einsatzkräften  
✅ **Qualifikationen**: Anzeige von Qualifikationen (Atemschutz, Maschinist, etc.)  
✅ **Führungsrollen**: Kennzeichnung von Zugführern, Gruppenführern, etc.  
✅ **Gruppenfilterung**: Gezielte Benachrichtigung nach TME-Codes

**Wichtig**: Das System funktioniert **vollständig ohne** alarm-messenger. Diese Integration ist optional.

---

## Systemübersicht

Die Messenger-Integration verbindet drei Komponenten:

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  alarm-mail     │─────▶│  alarm-monitor   │      │ alarm-messenger │
│  (IMAP Parser)  │      │  (Dashboard)     │◀────▶│ (Push-Service)  │
└─────────────────┘      └──────────────────┘      └─────────────────┘
        │                                                    │
        │                                                    │
        └────────────────────────────────────────────────────┘
                           Alarme weiterleiten
```

**Datenfluss:**

1. **alarm-mail** empfängt Alarm-E-Mails vom IMAP-Server
2. **alarm-mail** sendet den Alarm an den **alarm-monitor** (immer erforderlich)
3. **alarm-mail** sendet den Alarm optional auch an **alarm-messenger** (wenn konfiguriert)
4. **alarm-messenger** sendet Push-Notifications an registrierte Geräte (optional)
5. Teilnehmer geben Rückmeldung über ihre mobilen Apps (optional)
6. **alarm-monitor** ruft bei Bedarf Teilnehmerlisten vom **alarm-messenger** ab (optional)

**Hinweis:** Der alarm-messenger ist optional. Ohne ihn funktioniert das System 
vollständig, zeigt aber keine Teilnehmerrückmeldungen an.

---

## Datenfluss

### Kompletter Ablauf mit alarm-messenger

```
1. Leitstelle sendet Alarm-E-Mail
          ↓
2. alarm-mail empfängt und parst E-Mail
          ↓
3. alarm-mail sendet parallel an:
   ├─▶ alarm-monitor (Dashboard)
   └─▶ alarm-messenger (Push-Service)
          ↓
4. alarm-messenger sendet Push-Notifications
   ├─▶ iOS-Geräte (via APNs)
   └─▶ Android-Geräte (via FCM)
          ↓
5. Teilnehmer öffnen App und geben Rückmeldung:
   ├─ Zusage (accepted)
   ├─ Absage (declined)
   └─ Optional: Kommentar
          ↓
6. alarm-monitor fragt Teilnehmerliste ab
   GET /api/emergencies/{id}/participants
          ↓
7. Dashboard zeigt Rückmeldungen in Echtzeit
   - Wer hat zugesagt?
   - Qualifikationen verfügbar?
   - Führungskräfte dabei?
```

---

## Installation

### Voraussetzungen

- Docker und Docker Compose
- Firebase-Projekt (für Push-Notifications)
- Firebase Admin SDK JSON-Datei

### Schritt 1: Repository klonen

```bash
git clone https://github.com/TimUx/alarm-messenger.git
cd alarm-messenger
```

### Schritt 2: Firebase einrichten

1. Gehen Sie zur [Firebase Console](https://console.firebase.google.com/)
2. Erstellen Sie ein neues Projekt oder wählen Sie ein bestehendes
3. Aktivieren Sie **Cloud Messaging**
4. Erstellen Sie einen Service Account:
   - Projekteinstellungen → Service Accounts → Neuen privaten Schlüssel generieren
5. Laden Sie die JSON-Datei herunter und speichern Sie sie als `firebase-adminsdk.json`

### Schritt 3: Konfiguration erstellen

```bash
cp .env.example .env
nano .env
```

**Minimal-Konfiguration**:
```bash
# API Secret Key (für Authentifizierung)
API_SECRET_KEY=<generieren-mit-openssl-rand-hex-32>

# Firebase Admin SDK Pfad
FIREBASE_ADMIN_SDK_PATH=/app/firebase-adminsdk.json

# Server-Port
PORT=3000
```

### Schritt 4: Service starten

```bash
# Firebase-Datei kopieren
cp /pfad/zu/firebase-adminsdk.json firebase-adminsdk.json

# Container starten
docker compose up -d

# Logs prüfen
docker compose logs -f
```

---

## Konfiguration

### alarm-monitor konfigurieren

Fügen Sie die folgenden Umgebungsvariablen zu Ihrer `.env`-Datei hinzu:

```bash
# Alarm-Messenger Server-URL (erforderlich)
ALARM_DASHBOARD_MESSENGER_SERVER_URL=https://messenger.example.com

# Alarm-Messenger API-Key (erforderlich)
ALARM_DASHBOARD_MESSENGER_API_KEY=your-secret-api-key-here
```

**Wichtig**: 
- Der `ALARM_DASHBOARD_MESSENGER_API_KEY` muss **identisch** mit dem `API_SECRET_KEY` im alarm-messenger sein
- Nach Änderungen Container neu starten: `docker compose restart`

### alarm-mail konfigurieren

Damit alarm-mail Alarme auch an den Messenger sendet:

```bash
# In alarm-mail/.env hinzufügen:
ALARM_MAIL_MESSENGER_URL=http://alarm-messenger:3000
ALARM_MAIL_MESSENGER_API_KEY=<derselbe-api-key>
```

**Docker-Netzwerk**: Wenn alle Services im selben Docker-Netzwerk laufen, verwenden Sie die Container-Namen als Hostnamen (`alarm-messenger`, `alarm-monitor`).

**Verschiedene Hosts**: Verwenden Sie IP-Adressen oder Domainnamen:
```bash
ALARM_DASHBOARD_MESSENGER_SERVER_URL=https://messenger.example.com
ALARM_MAIL_MESSENGER_URL=https://messenger.example.com
```

---

## Funktionsweise

Die Integration funktioniert bidirektional:

### Alarmweiterleitung (alarm-mail → alarm-messenger)

1. Der **alarm-mail Service** empfängt eine Alarm-E-Mail vom IMAP-Server
2. alarm-mail parst den Alarm und sendet ihn an **beide** Services:
   - An alarm-monitor (Dashboard) für die Anzeige
   - An alarm-messenger für mobile Benachrichtigungen
3. Der alarm-messenger verteilt Push-Benachrichtigungen an registrierte Geräte
4. Teilnehmer können auf ihren Geräten Rückmeldung geben (Zusage/Absage)

### Teilnehmerrückmeldungen (alarm-messenger → alarm-monitor)

1. Das Dashboard fragt beim aktiven Alarm alle 10 Sekunden `GET /api/alarm/participants/<incident_number>` ab
2. Der alarm-monitor sucht die Emergency-UUID beim alarm-messenger via `GET /api/emergencies?emergencyNumber=<incident_number>`
3. Anschließend werden Teilnehmer via `GET /api/emergencies/{uuid}/participants` geladen
4. Teilnehmerrückmeldungen werden im Dashboard angezeigt (Qualifikationen, Führungsrollen)

## API-Endpunkte

### Alarmweiterleitung (alarm-mail → alarm-messenger)

Der **alarm-mail Service** sendet neue Alarme an:
```
POST {MESSENGER_SERVER_URL}/api/emergencies
```

Mit Header:
```
X-API-Key: {MESSENGER_API_KEY}
Content-Type: application/json
```

### Teilnehmerabruf (alarm-monitor → alarm-messenger)

Der **alarm-monitor** ruft Teilnehmerlisten ab von:
```
GET {MESSENGER_SERVER_URL}/api/emergencies/{emergency_id}/participants
```

Mit Header:
```
X-API-Key: {MESSENGER_API_KEY}
```

## Payload-Formate

### Alarmbenachrichtigung (POST /api/emergencies)

Die vom **alarm-mail Service** an den Messenger-Server gesendeten Daten:

```json
{
  "emergencyNumber": "2024-001",
  "emergencyDate": "2024-01-01T12:00:00",
  "emergencyKeyword": "F3Y – Brand",
  "emergencyDescription": "Brand in Wohngebäude",
  "emergencyLocation": "Musterstraße 1, 12345 Musterstadt",
  "groups": "WIL26,WIL41"
}
```

### Teilnehmerrückmeldungen (GET /api/emergencies/{id}/participants)

Die vom alarm-messenger an den **alarm-monitor** zurückgegebenen Daten:

```json
{
  "participants": [
    {
      "deviceId": "device-uuid-123",
      "deviceName": "Max Mustermann - iPhone",
      "response": "accepted",
      "respondedAt": "2024-01-01T12:05:30",
      "note": ""
    },
    {
      "deviceId": "device-uuid-456",
      "deviceName": "Erika Musterfrau - Android",
      "response": "declined",
      "respondedAt": "2024-01-01T12:06:15",
      "note": "Im Urlaub"
    }
  ]
}
```

### Feldmapping

#### Alarmbenachrichtigung (alarm-mail → alarm-messenger)

Der **alarm-mail Service** mappt die Felder wie folgt:

| Geparste XML-Felder | Alarm-Messenger API | Beschreibung |
|-------------------|---------------------|--------------|
| `ENR` | `emergencyNumber` | Einsatznummer |
| `EBEGINN` | `emergencyDate` | Zeitstempel des Alarms |
| `ESTICHWORT_1` | `emergencyKeyword` | Einsatzstichwort (z. B. "F3Y") |
| `DIAGNOSE` | `emergencyDescription` | Einsatzbeschreibung |
| `ORT`, `STRASSE` | `emergencyLocation` | Einsatzort |
| `TME` Codes | `groups` | TME-Codes (komma-getrennt) |

#### Teilnehmerrückmeldungen (alarm-messenger → alarm-monitor)

Der **alarm-monitor** empfängt:

| Messenger-Feld | Beschreibung |
|---------------|--------------|
| `deviceId` | Eindeutige Geräte-ID |
| `deviceName` | Anzeigename des Geräts (z. B. "Max M. - iPhone") |
| `response` | Rückmeldestatus: `accepted`, `declined`, `pending` |
| `respondedAt` | ISO-Zeitstempel der Rückmeldung |
| `note` | Optional: Freitext-Notiz des Teilnehmers |

### Gruppenfilterung

Wenn das Feld `dispatch_group_codes` im Alarm vorhanden ist, werden die TME-Codes als komma-getrennte Liste an den Messenger gesendet. Der Messenger benachrichtigt dann nur die Geräte, die diesen Gruppen zugeordnet sind.

Beispiel:
- Alarm-Monitor erhält TME-Codes: `["WIL26", "WIL41"]`
- Wird gesendet als: `"groups": "WIL26,WIL41"`
- Messenger benachrichtigt nur Geräte in Gruppe WIL26 oder WIL41

---

## Teilnehmerrückmeldungen

### Dashboard-Anzeige

Wenn Teilnehmer auf ihren Geräten Rückmeldung geben, werden diese im Dashboard angezeigt:

**Anzeige-Elemente**:
```
┌─────────────────────────────────────────────────────┐
│ Teilnehmerrückmeldungen                             │
├─────────────────────────────────────────────────────┤
│                                                     │
│ ✓ Max Mustermann                                   │
│   Atemschutzgeräteträger, Maschinist               │
│   Zugführer                                         │
│                                                     │
│ ✓ Erika Musterfrau                                 │
│   Atemschutzgeräteträger                           │
│                                                     │
│ ✗ Hans Beispiel                                    │
│   "Im Urlaub"                                       │
│                                                     │
│ 2 Zusagen • 1 Absage • 5 Ausstehend               │
└─────────────────────────────────────────────────────┘
```

### Response-Typen

| Typ | Bedeutung | Symbol im Dashboard |
|-----|-----------|---------------------|
| `accepted` | Zusage | ✓ (grün) |
| `declined` | Absage | ✗ (rot) |
| `pending` | Noch keine Rückmeldung | ⏳ (grau) |

### Polling-Mechanismus

Das Dashboard fragt Teilnehmerrückmeldungen **aktiv ab** (Polling):

```javascript
// Automatisches Polling alle 10 Sekunden
setInterval(() => {
  if (alarmActive && messengerEnabled) {
    fetchParticipants(incidentNumber);
  }
}, 10000);
```

**Vorteile**:
- Einfache Implementierung
- Kompatibel mit allen Browsern
- Keine permanente Verbindung nötig

**Nachteil**:
- Verzögerung bis zu 10 Sekunden

**Hinweis**: Das Dashboard nutzt für Alarm-Updates bereits **Server-Sent Events** (`/api/stream`). Teilnehmerrückmeldungen werden weiterhin per HTTP-Polling (10 s) abgefragt.

### Qualifikationen

Der alarm-messenger unterstützt folgende Standard-Qualifikationen:

- **Atemschutzgeräteträger** (AGT)
- **Maschinist**
- **Truppführer** (TF)
- **Gruppenführer** (GF)
- **Zugführer** (ZF)
- **Sanitäter**
- **Notfallsanitäter**
- **Weitere...** (konfigurierbar)

Qualifikationen werden im Dashboard **unter dem Namen** angezeigt.

### Führungsrollen

Führungskräfte werden **hervorgehoben** dargestellt:

```html
<div class="participant leader">
  <span class="name">Max Mustermann</span>
  <span class="role">Zugführer</span>
</div>
```

CSS:
```css
.participant.leader {
  border-left: 4px solid #f39c12;
  font-weight: bold;
}
```

---

## Fehlerbehandlung

### Alarmweiterleitung

- Wird vom **alarm-mail Service** durchgeführt
- Bei Timeout oder Verbindungsfehlern wird der Fehler geloggt
- Alarme werden trotzdem an den alarm-monitor gesendet
- Der Betrieb beider Services wird nicht beeinträchtigt

### Teilnehmerabruf

- Wird vom **alarm-monitor** durchgeführt
- Bei Timeout oder Fehlern werden keine Teilnehmer angezeigt
- Das Dashboard funktioniert weiterhin normal
- Fehler werden geloggt, beeinträchtigen aber nicht die Alarmdarstellung

## Deaktivierung

Um die Integration zu deaktivieren, entfernen oder kommentieren Sie die Umgebungsvariablen:

```bash
# ALARM_DASHBOARD_MESSENGER_SERVER_URL=https://messenger.example.com
# ALARM_DASHBOARD_MESSENGER_API_KEY=your-secret-api-key-here
```

## Testen

### Alarmweiterleitung testen

Die Alarmweiterleitung erfolgt durch den **alarm-mail Service**. Logs prüfen:

```bash
# alarm-mail Service (Docker)
cd alarm-mail && docker compose logs -f

# alarm-mail Service (systemd)
sudo journalctl -u alarm-mail -f
```

### Teilnehmerabruf testen

Der Teilnehmerabruf erfolgt durch den **alarm-monitor**. Logs prüfen:

```bash
# alarm-monitor (Docker)
docker compose logs -f

# alarm-monitor (systemd)
sudo journalctl -u alarm-dashboard -f
```

Bei erfolgreicher Teilnehmerabfrage sehen Sie eine Meldung wie:

```
INFO:alarm_dashboard.messenger:Retrieved 5 participants for incident 2024-001
```

Bei Fehlern wird eine entsprechende Fehlermeldung geloggt:

```
WARNING:alarm_dashboard.messenger:No emergency found for incident 2024-001 in messenger
ERROR:alarm_dashboard.messenger:Failed to fetch participants from messenger: <error details>
```

### Manuelle API-Tests

```bash
# Teilnehmerliste abrufen (benötigt emergency_id vom alarm-messenger)
curl -H "X-API-Key: your-api-key" \
  https://messenger.example.com/api/emergencies/{emergency-id}/participants | jq
```

## Alarm-Messenger Setup

Für das vollständige Setup des Alarm-Messenger Systems siehe:
- [Alarm-Messenger Repository](https://github.com/TimUx/alarm-messenger)
- [Alarm-Messenger API-Dokumentation](https://github.com/TimUx/alarm-messenger/blob/main/docs/API.md)
- [Alarm-Messenger Docker-Setup](https://github.com/TimUx/alarm-messenger/blob/main/DOCKER-QUICKSTART.md)

### Schnellstart Alarm-Messenger

```bash
# Alarm-Messenger klonen
git clone https://github.com/TimUx/alarm-messenger.git
cd alarm-messenger

# .env konfigurieren
cp .env.example .env
nano .env  # API_SECRET_KEY setzen

# Mit Docker starten
docker compose up -d

# QR-Code für Geräteregistrierung generieren (via Admin-Interface)
# Navigieren Sie zu: http://server:3000/admin/
```

## Sicherheit

- **HTTPS verwenden:** In Produktion immer HTTPS verwenden
- **API-Key schützen:** Den API-Key niemals im Code committen
- **Firewall-Regeln:** Nur notwendige Ports öffnen
- **Rate Limiting:** Der Alarm-Messenger hat Rate Limiting (100 Requests / 15 Min)
