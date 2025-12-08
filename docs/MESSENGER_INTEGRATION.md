# Alarm-Messenger Integration

Dieses Dokument beschreibt die Integration zwischen dem Alarm-Monitor und dem [Alarm-Messenger System](https://github.com/TimUx/alarm-messenger).

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

Wenn beide Variablen gesetzt sind:

1. Der Alarm-Monitor initialisiert beim Start eine `AlarmMessenger`-Instanz
2. Bei jedem verarbeiteten Alarm sendet der Monitor automatisch eine Benachrichtigung
3. Die Benachrichtigung wird als JSON-POST-Request an `{SERVER_URL}/api/emergencies` gesendet
4. Authentifizierung erfolgt über `X-API-Key` Header
5. Der Alarm-Messenger verteilt die Benachrichtigung über WebSocket an alle registrierten mobilen Geräte

## API-Endpunkt

Der Alarm-Monitor sendet Daten an:
```
POST {MESSENGER_SERVER_URL}/api/emergencies
```

Mit Header:
```
X-API-Key: {MESSENGER_API_KEY}
Content-Type: application/json
```

## Payload-Format

Die an den Messenger-Server gesendeten Daten entsprechen der Alarm-Messenger API-Spezifikation:

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

### Feldmapping

Der Alarm-Monitor mappt seine Felder auf die Alarm-Messenger API wie folgt:

| Alarm-Monitor Feld | Alarm-Messenger Feld | Beschreibung |
|-------------------|---------------------|--------------|
| `incident_number` | `emergencyNumber` | Einsatznummer (ENR) |
| `timestamp` | `emergencyDate` | Zeitstempel des Alarms |
| `keyword` | `emergencyKeyword` | Einsatzstichwort (z.B. "F3Y") |
| `description` | `emergencyDescription` | Einsatzbeschreibung |
| `location` | `emergencyLocation` | Einsatzort |
| `dispatch_group_codes` | `groups` | TME-Codes (komma-getrennt) |

### Gruppenfilterung

Wenn das Feld `dispatch_group_codes` im Alarm vorhanden ist, werden die TME-Codes als komma-getrennte Liste an den Messenger gesendet. Der Messenger benachrichtigt dann nur die Geräte, die diesen Gruppen zugeordnet sind.

Beispiel:
- Alarm-Monitor erhält TME-Codes: `["WIL26", "WIL41"]`
- Wird gesendet als: `"groups": "WIL26,WIL41"`
- Messenger benachrichtigt nur Geräte in Gruppe WIL26 oder WIL41

## Fehlerbehandlung

- Bei Timeout oder Verbindungsfehlern wird der Fehler geloggt
- Der Hauptbetrieb des Alarm-Monitors wird nicht beeinträchtigt
- Alarme werden weiterhin lokal gespeichert und im Dashboard angezeigt

## Deaktivierung

Um die Integration zu deaktivieren, entfernen oder kommentieren Sie die Umgebungsvariablen:

```bash
# ALARM_DASHBOARD_MESSENGER_SERVER_URL=https://messenger.example.com
# ALARM_DASHBOARD_MESSENGER_API_KEY=your-secret-api-key-here
```

## Testen

Sie können die Integration testen, indem Sie einen Test-Alarm senden und die Logs des Alarm-Monitors überprüfen:

```bash
# Docker
docker compose logs -f

# Native Installation
journalctl -u alarm-dashboard -f
```

Bei erfolgreicher Übermittlung sehen Sie eine Meldung wie:

```
INFO:alarm_dashboard.messenger:Successfully sent alarm notification to messenger: incident=2024-001
```

Bei Fehlern wird eine entsprechende Fehlermeldung geloggt:

```
ERROR:alarm_dashboard.messenger:Failed to send alarm to messenger: <error details>
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
