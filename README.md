# Alarm Dashboard

Dieses Projekt stellt ein webbasiertes Dashboard bereit, das Alarm-E-Mails
von einer Leitstelle automatisiert verarbeitet und einsatzrelevante
Informationen inklusive Karten- und Wetteranzeige darstellt. Es eignet sich
für Installationen im lokalen Netzwerk, bei denen ein Gerät als Server
fungiert und weitere Geräte das Dashboard im Vollbildmodus anzeigen. Als
Server oder Client können sowohl Raspberry Pis als auch klassische PCs,
Notebooks oder Smart-Displays eingesetzt werden.

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
|  (Leitstelle)    |         |  Server-Instanz      |        |  Endgeräte        |
+------------------+         +----------------------+        +-------------------+
         |                           |                              |
         |                           |                              |
         v                           v                              v
  Alarm-Mail            Geokodierung & Wetter             Leaflet Dashboard
```

Der Server ruft regelmäßig das IMAP-Postfach ab, parst neue Alarme und
stellt sie im internen Speicher bereit. Browser-Clients im LAN können
über die Weboberfläche oder die REST-API auf die Informationen zugreifen.
Es ist keine eingehende Verbindung aus dem Internet zum Server
notwendig; lediglich ausgehende Verbindungen für IMAP, Geokodierung und
Wetter werden benötigt. Die Serverrolle kann z. B. von einem Raspberry Pi
übernommen werden, funktioniert aber ebenso auf klassischen PCs, VMs oder
Cloud-Instanzen. Als Anzeigegeräte eignen sich alle Browser-fähigen
Clients (Raspberry Pi, Desktop-PC, Notebook, Tablet, Smartphone,
Smart-TV, TV-Stick usw.).

## Funktionsweise im Überblick

1. **E-Mail-Empfang** – Ein Hintergrund-Thread verbindet sich in
   konfigurierbaren Intervallen mit dem IMAP-Postfach der Leitstelle und
   sucht nach neuen, ungelesenen Nachrichten.
2. **Parsing & Validierung** – E-Mails im erwarteten XML-Format werden
   geparst. Relevante Felder (z. B. Stichworte, Adresse, Einsatzmittel)
   werden extrahiert und in strukturierter Form gespeichert.
3. **Anreicherung** – Falls keine Koordinaten mitgeliefert werden, wird
   der Einsatzort per Nominatim geokodiert. Anschließend ruft das System
   passende Wetterdaten über Open-Meteo ab.
4. **Visualisierung** – Das Flask-Backend liefert die Daten an die
   Browser-Clients aus. Dort werden Karte, Einsatztabelle, AAO, Wetter
   sowie Zusatzinformationen dargestellt. Für mobile Geräte steht eine
   separate Route zur Verfügung.

## Installation

Die Anwendung kann sowohl klassisch in einer lokalen Python-Umgebung als
auch containerisiert mit Docker beziehungsweise Docker Compose betrieben
werden. In beiden Varianten erfolgt die Konfiguration komfortabel über
Environment-Variablen, die beispielsweise in einer `.env` Datei
gespeichert werden.

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
   gewünschten Anzeige-Geräte (z. B. Raspberry Pi, PC, Notebook, Tablet)
   und aktivieren Sie bei Bedarf den Kiosk- oder Vollbildmodus.

### Container Deployment (Docker)

1. **.env vorbereiten**

   ```bash
   cp .env.example .env
   # Datei bearbeiten und Zugangsdaten eintragen
   ```

2. **Container bauen und starten**

   ```bash
   docker compose up --build
   ```

   `compose.yaml` liest die Variablen aus `.env` ein und startet den
   Container auf Port `8000`. Das lokale Verzeichnis `./instance` wird in
   den Container gemountet, sodass die Datei `instance/alarm_history.json`
   auch nach dem Neuerstellen des Containers erhalten bleibt. Bei Bedarf
   können zusätzliche Environment-Variablen direkt in der Compose-Datei
   oder beim Aufruf (`docker compose run -e ...`) gesetzt werden.

3. **Log- und Health-Prüfung**

   ```bash
   docker compose logs -f
   docker compose ps
   ```

   Der Container verfügt über einen Healthcheck (`/health` Endpoint).

4. **Stoppen & Aktualisieren**

   ```bash
   docker compose down
   ```

   Nach Code- oder Konfigurationsänderungen genügt ein erneutes
   `--build`, um das Image zu aktualisieren.

5. **Skalierung im LAN**

   Für weitere Anzeige-Clients reicht ein Browser, der auf
   `http://<server-ip>:8000` (Desktop) bzw. `http://<server-ip>:8000/mobile`
   zeigt. Containerisierte Clients können denselben Compose-Stack nutzen
   oder mittels Reverse-Proxy auf das Dashboard zugreifen.

### Konfiguration über Environment-Variablen

Alle Variablen tragen den Präfix `ALARM_DASHBOARD_`. Pflichtfelder sind
markiert.

| Variable | Pflicht | Beschreibung |
| --- | --- | --- |
| `IMAP_HOST` | ja | Hostname oder IP des IMAP-Servers der Leitstelle. |
| `IMAP_PORT` | nein (Default `993`) | Port des IMAP-Servers. |
| `IMAP_USE_SSL` | nein (Default `true`) | `true` für TLS-geschützte Verbindung, `false` für unverschlüsselt. |
| `IMAP_USERNAME` | ja | Benutzername für das Alarm-Postfach. |
| `IMAP_PASSWORD` | ja | Passwort für das Alarm-Postfach. |
| `IMAP_MAILBOX` | nein (Default `INBOX`) | Zu überwachender Ordner im Postfach. |
| `IMAP_SEARCH` | nein (Default `UNSEEN`) | IMAP-Suchfilter für neue Nachrichten. |
| `POLL_INTERVAL` | nein (Default `60`) | Abrufintervall des Postfachs in Sekunden. |
| `GRUPPEN` | nein | Kommagetrennte Liste von TME-Codes; filtert Einsätze auf bestimmte Gruppen. |
| `DISPLAY_DURATION_MINUTES` | nein (Default `30`) | Dauer, wie lange ein Alarm sichtbar bleibt, bevor die Standardansicht erscheint. |
| `FIRE_DEPARTMENT_NAME` | nein (Default `Willingshausen`) | Anzeigename, der in Kopfzeile und Idle-Ansicht erscheint. |
| `DEFAULT_LATITUDE` / `DEFAULT_LONGITUDE` | nein | Koordinaten für Wetter- und Kartendaten in der Idle-Ansicht, wenn kein Alarm aktiv ist. |
| `DEFAULT_LOCATION_NAME` | nein | Beschriftung der Idle-Ansicht (z. B. Standort der Wache). |
| `NOMINATIM_URL` | nein (Default `https://nominatim.openstreetmap.org/search`) | Basis-URL für die Geokodierung. |
| `WEATHER_URL` | nein (Default `https://api.open-meteo.com/v1/forecast`) | Basis-URL für Wetterabfragen. |
| `WEATHER_PARAMS` | nein | Query-Parameter für die Wetter-API (z. B. welche Felder geladen werden). |
| `HISTORY_FILE` | nein | Pfad zur JSON-Datei, in der Historien-Daten persistiert werden. Standard: `instance/alarm_history.json`. |

Eine befüllte `.env` könnte beispielsweise so aussehen:

```
ALARM_DASHBOARD_IMAP_HOST=imap.mailserver.de
ALARM_DASHBOARD_IMAP_PORT=993
ALARM_DASHBOARD_IMAP_USE_SSL=true
ALARM_DASHBOARD_IMAP_USERNAME=alarm@example.com
ALARM_DASHBOARD_IMAP_PASSWORD=change-me
ALARM_DASHBOARD_IMAP_MAILBOX=INBOX
ALARM_DASHBOARD_IMAP_SEARCH=UNSEEN
ALARM_DASHBOARD_POLL_INTERVAL=60
ALARM_DASHBOARD_GRUPPEN=
ALARM_DASHBOARD_DISPLAY_DURATION_MINUTES=30
ALARM_DASHBOARD_FIRE_DEPARTMENT_NAME=Feuerwehr Beispielstadt
ALARM_DASHBOARD_DEFAULT_LATITUDE=51.2345
ALARM_DASHBOARD_DEFAULT_LONGITUDE=9.8765
ALARM_DASHBOARD_DEFAULT_LOCATION_NAME=Wache Beispielstadt
```

#### Alarmaktivierung über Gruppenfilter

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

## Speicherung von Alarmen und Historie

Eingehende Einsätze werden in der Klasse `AlarmStore` gespeichert
(`alarm_dashboard/storage.py`). Die Komponente hält den zuletzt
eingegangenen Alarm im Speicher bereit, verwaltet eine Historie und
persistiert die Daten optional als JSON-Datei. Standardmäßig wird der
Pfad `instance/alarm_history.json` innerhalb des Flask
`instance`-Verzeichnisses genutzt. Das Verzeichnis liegt außerhalb des
Repositorys, ist beschreibbar und wird beim Anwendungsstart automatisch
angelegt.

Der Speicherort lässt sich über die Konfiguration anpassen:

* Setzen Sie die Umgebungsvariable `ALARM_DASHBOARD_HISTORY_FILE` (z. B.
  in `.env`), um einen absoluten oder relativen Pfad vorzugeben.
* Alternativ kann `history_file` beim Erstellen einer `AppConfig`
  übergeben werden.

Sobald ein eigener Pfad gesetzt ist, schreibt `AlarmStore` die Daten
direkt dorthin. Bei einem Neustart der Anwendung wird die Datei wieder
eingelesen, sodass der letzte Alarm und die Historie erhalten bleiben.

## Entwicklung

* Konfigurationsdateien liegen unter `alarm_dashboard/config.py`.
* Der Mail-Polling-Thread ist in `alarm_dashboard/mail_checker.py`
  implementiert.
* Parsing-Logik befindet sich in `alarm_dashboard/parser.py`.
* Die Flask-App wird in `alarm_dashboard/app.py` erzeugt.
* Statische Assets (CSS/JS) liegen unter `alarm_dashboard/static/`.

### Beispiel-Alarm und Auswertung

Ein typischer Alarm trifft als XML im Format `<INCIDENT>` ein. Das
folgenden Beispiel nutzt vollständig anonymisierte Werte:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<INCIDENT>
  <STICHWORT>F3Y</STICHWORT>
  <ESTICHWORT_1>F3Y</ESTICHWORT_1>
  <ESTICHWORT_2>Personen in Gefahr</ESTICHWORT_2>
  <ENR>7850001123</ENR>
  <FENR>F7850005120</FENR>
  <EBEGINN>24.07.2026 18:42:11</EBEGINN>
  <DIAGNOSE>Brand in Wohngebäudekomplex</DIAGNOSE>
  <EO_BEMERKUNG>Mehrere Anrufe, starke Rauchentwicklung</EO_BEMERKUNG>
  <ORT>Musterstadt</ORT>
  <ORTSTEIL>Nordviertel</ORTSTEIL>
  <STRASSE>Wehrgasse</STRASSE>
  <OBJEKT>Hausnummernblock 12-16</OBJEKT>
  <UNTEROBJEKT>Aufgang C</UNTEROBJEKT>
  <ORTSZUSATZ>Rückseite über Innenhof</ORTSZUSATZ>
  <GMA></GMA>
  <HAUSNUMMER>14</HAUSNUMMER>
  <KOORDINATE_LAT>51.245678</KOORDINATE_LAT>
  <KOORDINATE_LON>9.845321</KOORDINATE_LON>
  <KOORDINATE_UTM>32UNB1234567890</KOORDINATE_UTM>
  <EOZUSATZ>Anfahrt über Haupttor, Schlüssel im Depot</EOZUSATZ>
  <INFOTEXT>Bewohner werden evakuiert</INFOTEXT>
  <INFEKTION></INFEKTION>
  <ANFAHRTSHINWEIS>Zufahrt über Ringstraße</ANFAHRTSHINWEIS>
  <AAO>LF Musterstadt 1;DLK Musterstadt;ELW Musterstadt</AAO>
  <EINSATZMASSNAHMEN>
    <FME>
      <BEZEICHNUNG>MUS Zugführung (FME M120)</BEZEICHNUNG><AUSFUE_ZEIT>20260724184410</AUSFUE_ZEIT>
      <BEZEICHNUNG>MUS Löschzug (FME M118)</BEZEICHNUNG><AUSFUE_ZEIT>20260724184410</AUSFUE_ZEIT>
    </FME>
    <TME>
      <BEZEICHNUNG>MUS Nord 1 (TME MUS11)</BEZEICHNUNG><AUSFUE_ZEIT>20260724184430</AUSFUE_ZEIT>
      <BEZEICHNUNG>MUS Innenstadt (TME MUS05)</BEZEICHNUNG><AUSFUE_ZEIT>20260724184502</AUSFUE_ZEIT>
    </TME>
  </EINSATZMASSNAHMEN>
</INCIDENT>
```

Der Parser ordnet die Felder wie folgt zu und stellt sie im Dashboard dar:

* **Alarm-Header** – `ESTICHWORT_1` liefert die Überschrift. Ein
  vorhandenes `ESTICHWORT_2` wird als Untertitel eingeblendet. `EBEGINN`
  erscheint als Zeitstempel neben dem Stichwort.
* **Detailkarte und Adresse** – `ORT`, `ORTSTEIL`, `STRASSE`,
  `HAUSNUMMER`, `OBJEKT` und `ORTSZUSATZ` bilden den Adressblock unterhalb
  der Karte. `KOORDINATE_LAT`/`KOORDINATE_LON` positionieren den Marker
  und dienen der Wetterabfrage. Liegen keine Koordinaten vor, wird anhand
  der Adressdaten geokodiert.
* **Diagnose & Hinweise** – `DIAGNOSE`, `EO_BEMERKUNG`, `INFOTEXT` und
  `EOZUSATZ` erscheinen in den hervorgehobenen Textboxen. `EO_BEMERKUNG`
  wird rot markiert, um kritische Zusatzinfos hervorzuheben.
* **AAO & Einheiten** – `AAO` speist die Liste der alarmierten Fahrzeuge
  in der rechten Spalte. Die Abschnitte `<FME>` und `<TME>` werden
  einzeln aufgeführt; optional filtert `ALARM_DASHBOARD_GRUPPEN` auf
  bestimmte TME-Codes. Anzeige erfolgt in den Tabellen „Funkmeldeempfänger“
  und „Telefonmeldeempfänger“.
* **Historie & API** – `ENR`/`FENR` sowie sämtliche Kerninformationen
  werden persistent gespeichert und erscheinen in der Einsatzhistorie
  (`/history`) sowie in den API-Endpunkten (`/api/alarm`, `/api/history`).

Fehlen einzelne Felder, bleiben die entsprechenden Bereiche leer bzw.
werden mit `-` gekennzeichnet. Liegen Koordinaten vor, wird keine
zusätzliche Geokodierung mehr benötigt.

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

Das Design kann an eigene Bedürfnisse angepasst werden:

1. **Feuerwehrname konfigurieren** – Hinterlegen Sie den gewünschten Namen
   über `ALARM_DASHBOARD_FIRE_DEPARTMENT_NAME` in Ihrer `.env`. Der Wert
   erscheint prominent in der Kopfzeile sowie in der Standardansicht.
2. **Wappen oder Logo austauschen** – Ersetzen Sie die Datei
   `alarm_dashboard/static/img/crest.png` durch ein eigenes Bild (PNG mit
   transparentem Hintergrund empfohlen). Verwenden Sie entweder denselben
   Dateinamen oder passen Sie in `alarm_dashboard/app.py` den Pfad im Aufruf
   `url_for("static", filename="img/crest.png")` an, falls Sie einen anderen
   Dateinamen nutzen möchten.
3. **Farbschema anpassen** – Die zentralen Farben sind als CSS-Variablen in
   `alarm_dashboard/static/css/dashboard.css` definiert (Abschnitt `:root`
   für den Alarmmodus, `body.mode-idle` für die Standardansicht). Weitere
   Ansichten verwenden `history.css` und `mobile.css`. Durch Anpassen der
   Variablen `--accent`, `--background`, `--surface` usw. lässt sich das
   Erscheinungsbild schnell auf die eigenen Hausfarben abstimmen.

## Option: Betrieb auf dem Raspberry Pi

* Aktivieren Sie den Autostart der Flask-App via `systemd`-Service.
* Nutzen Sie `chromium-browser --kiosk http://<server-ip>:8000` oder
  `firefox --kiosk` auf dem Raspberry Pi, wenn dieser als Anzeige-Client
  dient.
* Stellen Sie sicher, dass die Geräte im gleichen LAN sind und der Server
  ausgehende Verbindungen zu IMAP, Nominatim und Open-Meteo aufbauen darf.
* Aus Sicherheitsgründen sollten keine Portweiterleitungen ins Internet
  eingerichtet werden.

## Lizenz

Dieses Projekt steht unter der MIT-Lizenz.
