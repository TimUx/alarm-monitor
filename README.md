# Alarm Dashboard

Dieses Projekt stellt ein webbasiertes Dashboard bereit, das Alarm-E-Mails
von einer Leitstelle automatisiert verarbeitet und einsatzrelevante
Informationen inklusive Karten- und Wetteranzeige darstellt. Es richtet
sich insbesondere an Installationen auf einem Raspberry Pi im lokalen
Netzwerk, bei dem ein Gerät als Server fungiert und weitere Geräte das
Dashboard im Vollbildmodus anzeigen.

## Funktionsumfang

* Polling eines IMAP-Postfachs nach neuen Alarm-E-Mails.
* Parsing der E-Mail-Inhalte inklusive Einsatzstichwort (Haupt- und
  Unterstichwort), Diagnose, Bemerkungen, alarmierter Fahrzeuge (AAO)
  sowie detaillierter Adresse mit Ort, Ortsteil, Straße und Hausnummer.
* Geokodierung des Einsatzortes über OpenStreetMap (Nominatim).
* Anzeige einer OpenStreetMap-Karte des Einsatzortes mittels Leaflet.
* Abruf der aktuellen Wetterdaten über die Open-Meteo API.
* REST-API und Weboberfläche auf Basis von Flask.
* Dashboard optimiert für eine Darstellung im Kiosk-/Vollbildmodus.
* Automatischer Wechsel auf eine Standardanzeige mit Uhrzeit, Lokalwetter
  und Vereinswappen, sobald kein Alarm vorliegt oder ein Alarm älter als
  die konfigurierbare Anzeigedauer (Standard: 30 Minuten) ist.
* Darstellung des zuletzt eingegangenen Einsatzes in der Standardansicht
  inklusive Alarmstichwort und Zeitstempel.
* Abrufbare Einsatzhistorie über das Dashboard (Button) oder die REST-API.
* Separate mobilfreundliche Ansicht unter `/mobile` für Smartphones und Tablets.
* Mobilansicht mit direktem Navigations-Button, der Apple Karten oder Google Maps mit dem Einsatzziel öffnet.

## Architekturüberblick

```
+------------------+         +----------------------+        +-------------------+
|  IMAP Postfach   | ---->   |  Flask Backend       | ---->  |  Browser Clients  |
|  (Leitstelle)    |         |  Raspberry Pi Server |        |  Raspberry Pi etc |
+------------------+         +----------------------+        +-------------------+
         |                           |                              |
         |                           |                              |
         v                           v                              v
  Alarm-Mail            Geokodierung & Wetter             Leaflet Dashboard
```

Der Server-Raspberry-Pi ruft regelmäßig das IMAP-Postfach ab, parst neue
Alarme und stellt sie im internen Speicher bereit. Browser-Clients im
LAN können über die Weboberfläche oder die REST-API auf die Informationen
zugreifen. Es ist keine eingehende Verbindung aus dem Internet zum Pi
notwendig; lediglich ausgehende Verbindungen für IMAP, Geokodierung und
Wetter werden benötigt.

## Deployment-Varianten

Die Anwendung lässt sich sowohl klassisch (Python-Umgebung) als auch in
Containern betreiben. Die Konfiguration erfolgt in beiden Fällen über
Environment-Variablen, die bequem in einer `.env` Datei verwaltet werden
können.

### Native Installation (Python)

1. **System vorbereiten**
   ```bash
   sudo apt update
   sudo apt install python3 python3-venv python3-pip
   ```

2. **Projekt klonen und Umgebung erstellen**
   ```bash
   git clone <repo-url>
   cd alarm-dashboard
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Konfiguration festlegen**

   Passen Sie `.env.example` an und speichern Sie die Datei als `.env`.
   Alternativ können die Variablen direkt exportiert werden:

   ```bash
   export ALARM_DASHBOARD_IMAP_HOST=imap.example.com
   export ALARM_DASHBOARD_IMAP_USERNAME=leitstelle@example.com
   export ALARM_DASHBOARD_IMAP_PASSWORD=geheim
   export ALARM_DASHBOARD_IMAP_MAILBOX=INBOX
   export ALARM_DASHBOARD_POLL_INTERVAL=60
   ```

   Optional lassen sich Variablen wie `ALARM_DASHBOARD_IMAP_SEARCH`,
   `ALARM_DASHBOARD_NOMINATIM_URL` oder `ALARM_DASHBOARD_WEATHER_PARAMS`
   setzen. Für die Standardanzeige empfiehlt sich die Angabe einer festen
   Position, damit das lokale Wetter auch ohne aktuellen Einsatz ermittelt
   werden kann:

   ```bash
   export ALARM_DASHBOARD_DEFAULT_LATITUDE=52.52
   export ALARM_DASHBOARD_DEFAULT_LONGITUDE=13.405
   export ALARM_DASHBOARD_DEFAULT_LOCATION_NAME="Feuerwache Musterstadt"
   ```

4. **Anwendung starten**
   ```bash
   flask --app alarm_dashboard.app run --host 0.0.0.0 --port 8000
   ```

   Alternativ kann `python -m alarm_dashboard.app` genutzt werden.

5. **Dashboard anzeigen**

   Öffnen Sie im lokalen Netzwerk `http://<server-ip>:8000` im Browser der
   Client-Raspberry-Pis und aktivieren Sie den Kiosk- oder Vollbildmodus.

### Container Deployment (Docker / Podman)

1. **.env vorbereiten**

   ```bash
   cp .env.example .env
   # Datei bearbeiten und Zugangsdaten eintragen
   ```

2. **Container bauen und starten**

   Mit Docker Compose:

   ```bash
   docker compose up --build
   ```

   Mit Podman (ab Version 4, `podman compose`):

   ```bash
   podman compose up --build
   ```

   Beide Varianten greifen auf `compose.yaml` zurück. Die Datei liest die
   Variablen aus `.env` ein und startet den Container auf Port `8000`. Bei
   Bedarf können zusätzliche Environment-Variablen direkt in der Compose-
   Datei oder beim Aufruf (`docker compose run -e ...`) gesetzt werden.

3. **Log- und Health-Prüfung**

   ```bash
   docker compose logs -f
   docker compose ps
   ```

   Der Container verfügt über einen Healthcheck (`/health` Endpoint). Bei
   Podman sind die Kommandos analog (`podman compose logs`, `podman ps`).

4. **Stoppen & Aktualisieren**

   ```bash
   docker compose down
   # oder
   podman compose down
   ```

   Nach Code- oder Konfigurationsänderungen genügt ein erneutes
   `--build`, um das Image zu aktualisieren.

5. **Skalierung im LAN**

   Für weitere Anzeige-Clients reicht ein Browser, der auf
   `http://<server-ip>:8000` (Desktop) bzw. `http://<server-ip>:8000/mobile`
   zeigt. Containerisierte Clients können denselben Compose-Stack nutzen
   oder mittels Reverse-Proxy auf das Dashboard zugreifen.

## Beispiel `.env`

Die Datei `.env.example` enthält alle unterstützten Variablen und kann als
Vorlage genutzt werden:

```
ALARM_DASHBOARD_IMAP_HOST=imap.mailserver.de
ALARM_DASHBOARD_IMAP_PORT=993
ALARM_DASHBOARD_IMAP_USE_SSL=true
ALARM_DASHBOARD_IMAP_USERNAME=alarm@wehr.de
ALARM_DASHBOARD_IMAP_PASSWORD=topsecret
ALARM_DASHBOARD_IMAP_MAILBOX=INBOX
ALARM_DASHBOARD_IMAP_SEARCH=UNSEEN
ALARM_DASHBOARD_POLL_INTERVAL=60
ALARM_DASHBOARD_GRUPPEN=
ALARM_DASHBOARD_DISPLAY_DURATION_MINUTES=30
ALARM_DASHBOARD_DEFAULT_LATITUDE=52.52
ALARM_DASHBOARD_DEFAULT_LONGITUDE=13.405
ALARM_DASHBOARD_DEFAULT_LOCATION_NAME=Feuerwache Musterstadt
```

Weitere optionale Variablen zur Anpassung von Geokodierungs- und
Wetterdiensten lassen sich einfach ergänzen.

### Alarmaktivierung über Gruppenfilter

Über die Variable `ALARM_DASHBOARD_GRUPPEN` lassen sich die anzuzeigenden
Alarme auf bestimmte TME-Gruppen einschränken. Hinterlegen Sie eine
kommagetrennte Liste (z. B. `ALARM_DASHBOARD_GRUPPEN=WIL26,WIL41`). Das
Dashboard reagiert nur dann auf eingehende Meldungen, wenn mindestens einer
dieser Codes im Abschnitt `<TME>` der Einsatzmaßnahmen vorkommt. Wird kein
Filter gesetzt, werden weiterhin alle eingehenden Alarme dargestellt.

Die maximale Dauer, wie lange ein Alarm aktiv sichtbar bleibt, kann über
`ALARM_DASHBOARD_DISPLAY_DURATION_MINUTES` angepasst werden. Standardmäßig
kehrt das Dashboard nach 30 Minuten ohne neue Meldung in die Standardansicht
zurück. Setzen Sie bei Bedarf z. B. `ALARM_DASHBOARD_DISPLAY_DURATION_MINUTES=45`.

## Entwicklung

* Konfigurationsdateien liegen unter `alarm_dashboard/config.py`.
* Der Mail-Polling-Thread ist in `alarm_dashboard/mail_checker.py`
  implementiert.
* Parsing-Logik befindet sich in `alarm_dashboard/parser.py`.
* Die Flask-App wird in `alarm_dashboard/app.py` erzeugt.
* Statische Assets (CSS/JS) liegen unter `alarm_dashboard/static/`.

### E-Mail-Format und Feldzuordnung

Die Leitstellen-Mails können als XML im Format `<INCIDENT>` eintreffen. Die
Parser-Logik liest dabei u. a. folgende Elemente aus und stellt sie der
Oberfläche zur Verfügung:

| XML-Element         | Dashboard-Feld                                                |
| ------------------- | ------------------------------------------------------------- |
| `EBEGINN`           | Zeitstempel der Alarmierung                                   |
| `ESTICHWORT_1`      | Hauptstichwort (Anzeige als Überschrift)                      |
| `ESTICHWORT_2`      | Unterstichwort (optional, unterhalb der Überschrift)          |
| `DIAGNOSE`          | Diagnose/Detailtext                                           |
| `EO_BEMERKUNG`      | Bemerkung (rote Hervorhebung)                                 |
| `AAO`               | Alarmierte Fahrzeuge (Semikolon-getrennte Liste)              |
| `ORT`, `ORTSTEIL`   | Ort und Ortsteil                                              |
| `STRASSE`, `HAUSNUMMER` | Straße und Hausnummer                                     |
| `ORTSZUSATZ`, `OBJEKT` | Zusatzinformationen (werden ebenfalls angezeigt)          |
| `KOORDINATE_LAT/LON` | Koordinaten zur Kartenanzeige und Wetterabfrage              |

Fehlen einzelne Felder, bleiben die entsprechenden Bereiche leer bzw. werden mit `-`
gekennzeichnet. Liegen Koordinaten vor, wird keine zusätzliche Geokodierung mehr
benötigt; andernfalls greift das System weiterhin auf Nominatim zurück.

### Tests und lokale Entwicklung

Für lokale Tests können Beispiel-E-Mails als `.eml` Datei abgelegt und
über ein kleines Skript in den Store eingelesen werden. Die Anwendung
ist so ausgelegt, dass der Mail-Poller auch deaktiviert werden kann,
indem die `AlarmMailFetcher`-Instanz nicht gestartet wird. Nutzen Sie z.B.
Postman oder `curl`, um die API unter `http://localhost:8000/api/alarm`
anzufragen.

## Einsatzhistorie & Standardansicht

Sobald kein aktueller Alarm vorliegt oder der letzte Alarm älter als die
eingestellte Anzeigedauer ist, wechselt das Dashboard automatisch in die
Standardansicht.
Diese zeigt neben Uhrzeit, Wetter und Wappen auch kompakt den zuletzt
eingegangenen Einsatz (Datum/Uhrzeit und Stichwort) an. Über den Button
"Historie ansehen" führt ein Link zur tabellarischen Übersicht der
letzten Einsätze, die sowohl vom großen Dashboard als auch aus der
mobilen Ansicht erreichbar ist.

Die tabellarische Übersicht ist direkt unter `http://<server>/history`
erreichbar. Die zugrunde liegenden Daten können außerdem per API
abgefragt werden:

* `GET /api/history` – liefert die gespeicherten Einsätze (neuester zuerst).
  Optional kann mit dem Query-Parameter `limit` die Anzahl der Einträge
  begrenzt werden (maximal 500). Jedes Element enthält u.a. Zeitstempel,
  Stichwort, Ort, Diagnose/Beschreibung, Bemerkungen und alarmierte Fahrzeuge.
* `GET /api/alarm` – wie bisher, ergänzt im Idle-Fall um das Feld
  `last_alarm`, das die wichtigsten Informationen des letzten Einsatzes
  enthält und für die kompakte Anzeige genutzt wird.

Für einfache mobile Zugriffe ohne native App stehen die mobiloptimierte Route `/mobile` sowie die JSON-API `GET /api/mobile/alarm` zur Verfügung. Beide Varianten greifen auf dieselben Alarm- und Historieninformationen wie das Hauptdashboard zu und aktualisieren sich automatisch.

Die mobile Oberfläche blendet zusätzlich einen Button "Navigation starten" ein, der je nach Endgerät Apple Karten oder Google Maps mit den übermittelten Koordinaten bzw. Adressdaten öffnet, sodass die Anfahrt direkt begonnen werden kann.

## Standardansicht & Gestaltung

* In Ruhephasen blendet das Dashboard eine großformatige Uhr, das lokale
  Wetter sowie das Gemeindewappen ein. Die Ansicht greift dabei auf die
  konfigurierten Standardkoordinaten zurück.
* Läuft ein Alarm länger als die konfigurierte Anzeigedauer, wird
  automatisch in die Standardansicht gewechselt, um Fehlinterpretationen
  zu vermeiden.
* Farbgebung und Layout sind an das bereitgestellte Wappen angelehnt und
  binden das Wappen sowohl in der Alarm- als auch in der Idle-Ansicht ein.

## Betrieb auf dem Raspberry Pi

* Aktivieren Sie den Autostart der Flask-App via `systemd`-Service.
* Nutzen Sie `chromium-browser --kiosk http://<server-ip>:8000` oder
  `firefox --kiosk` auf den Client-Raspberry-Pis.
* Stellen Sie sicher, dass die Geräte im gleichen LAN sind und der Server
  ausgehende Verbindungen zu IMAP, Nominatim und Open-Meteo aufbauen darf.
* Aus Sicherheitsgründen sollten keine Portweiterleitungen ins Internet
  eingerichtet werden.

## Lizenz

Dieses Projekt steht unter der MIT-Lizenz.
