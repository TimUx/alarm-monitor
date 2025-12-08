# Beispiel: Alarm-Messenger Integration

Dieses Beispiel zeigt, wie die Alarm-Messenger-Integration konfiguriert und verwendet wird.

## Konfiguration

Fügen Sie die folgenden Umgebungsvariablen zu Ihrer `.env`-Datei hinzu:

```bash
# Alarm-Messenger Server-URL (erforderlich)
ALARM_DASHBOARD_MESSENGER_SERVER_URL=https://messenger.example.com

# Alarm-Messenger API-Key (erforderlich)
ALARM_DASHBOARD_MESSENGER_API_KEY=your-secret-api-key-here
```

## Funktionsweise

Wenn beide Variablen gesetzt sind:

1. Der Alarm-Monitor initialisiert beim Start eine `AlarmMessenger`-Instanz
2. Bei jedem verarbeiteten Alarm sendet der Monitor automatisch eine Benachrichtigung
3. Die Benachrichtigung wird als JSON-POST-Request an `{SERVER_URL}/api/alarm` gesendet
4. Authentifizierung erfolgt über `Authorization: Bearer {API_KEY}` Header

## Payload-Format

Die an den Messenger-Server gesendeten Daten haben folgendes Format:

```json
{
  "incident_number": "12345",
  "timestamp": "2024-01-01T12:00:00",
  "keyword": "F3Y – Brand in Wohngebäude",
  "location": "Musterstraße 1, 12345 Musterstadt",
  "description": "Brand in Wohngebäude",
  "remark": "Mehrere Anrufer",
  "groups": ["LF 1", "DLK 1"],
  "coordinates": {
    "lat": 51.5,
    "lon": 9.5
  }
}
```

## Fehlerbehandlung

- Bei Timeout oder Verbindungsfehlern wird der Fehler geloggt
- Der Hauptbetrieb des Alarm-Monitors wird nicht beeinträchtigt
- Alarme werden weiterhin lokal gespeichert und im Dashboard angezeigt

## Deaktivierung

Um die Integration zu deaktivieren, entfernen oder kommentieren Sie die
Umgebungsvariablen:

```bash
# ALARM_DASHBOARD_MESSENGER_SERVER_URL=https://messenger.example.com
# ALARM_DASHBOARD_MESSENGER_API_KEY=your-secret-api-key-here
```

## Testen

Sie können die Integration testen, indem Sie einen Test-Alarm senden und die
Logs des Alarm-Monitors überprüfen:

```bash
# Docker
docker compose logs -f

# Native Installation
journalctl -u alarm-dashboard -f
```

Bei erfolgreicher Übermittlung sehen Sie eine Meldung wie:

```
INFO:alarm_dashboard.messenger:Successfully sent alarm notification to messenger: incident=12345
```

Bei Fehlern wird eine entsprechende Fehlermeldung geloggt:

```
ERROR:alarm_dashboard.messenger:Failed to send alarm to messenger: <error details>
```
