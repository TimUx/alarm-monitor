# Alarm-Messenger Integration

Dieses Dokument beschreibt die Integration zwischen dem Alarm-Monitor und dem [Alarm-Messenger System](https://github.com/TimUx/alarm-messenger).


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
2. **alarm-mail** sendet den Alarm an **beide** Services parallel:
   - An **alarm-monitor** für die Dashboard-Anzeige
   - An **alarm-messenger** für mobile Benachrichtigungen
3. **alarm-messenger** sendet Push-Notifications an registrierte Geräte
4. Teilnehmer geben Rückmeldung über ihre mobilen Apps
5. **alarm-monitor** ruft bei Bedarf Teilnehmerlisten vom **alarm-messenger** ab

## Konfiguration

Fügen Sie die folgenden Umgebungsvariablen zu Ihrer `.env`-Datei hinzu:

```bash
# Alarm-Messenger Server-URL (erforderlich)
ALARM_DASHBOARD_MESSENGER_SERVER_URL=https://messenger.example.com

# Alarm-Messenger API-Key (erforderlich)
ALARM_DASHBOARD_MESSENGER_API_KEY=your-secret-api-key-here
```

**Wichtig:** Der API-Key muss mit dem Wert übereinstimmen, der im Alarm-Messenger als `API_SECRET_KEY` konfiguriert ist.

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

1. Der alarm-monitor registriert beim Empfang eines Alarms die `emergency_id`
2. Das Dashboard kann Teilnehmerlisten vom alarm-messenger abrufen
3. Teilnehmerrückmeldungen werden im Dashboard angezeigt (wer hat zugesagt)
4. Die Abfrage erfolgt über den API-Endpunkt `/api/emergencies/{emergency_id}/participants`

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
WARNING:alarm_dashboard.messenger:No emergency_id cached for incident 2024-001
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
