let map = null;
let marker = null;
let mapWarningLogged = false;

const WIND_DIRECTIONS = [
    { abbr: 'N', label: 'Nord' },
    { abbr: 'NNO', label: 'Nord-Nordost' },
    { abbr: 'NO', label: 'Nordost' },
    { abbr: 'ONO', label: 'Ost-Nordost' },
    { abbr: 'O', label: 'Ost' },
    { abbr: 'OSO', label: 'Ost-Südost' },
    { abbr: 'SO', label: 'Südost' },
    { abbr: 'SSO', label: 'Süd-Südost' },
    { abbr: 'S', label: 'Süd' },
    { abbr: 'SSW', label: 'Süd-Südwest' },
    { abbr: 'SW', label: 'Südwest' },
    { abbr: 'WSW', label: 'West-Südwest' },
    { abbr: 'W', label: 'West' },
    { abbr: 'WNW', label: 'West-Nordwest' },
    { abbr: 'NW', label: 'Nordwest' },
    { abbr: 'NNW', label: 'Nord-Nordwest' },
];

const WEATHER_CODE_MAP = [
    { codes: [0], icon: '☀️', label: 'Klarer Himmel' },
    { codes: [1, 2], icon: '🌤️', label: 'Überwiegend sonnig' },
    { codes: [3], icon: '☁️', label: 'Bedeckt' },
    { codes: [45, 48], icon: '🌫️', label: 'Nebel' },
    { codes: [51, 53, 55], icon: '🌦️', label: 'Nieselregen' },
    { codes: [56, 57], icon: '🌧️', label: 'Gefrierender Nieselregen' },
    { codes: [61, 63, 65], icon: '🌧️', label: 'Regen' },
    { codes: [66, 67], icon: '🌨️', label: 'Gefrierender Regen' },
    { codes: [71, 73, 75, 77], icon: '❄️', label: 'Schneefall' },
    { codes: [80, 81, 82], icon: '🌦️', label: 'Regenschauer' },
    { codes: [85, 86], icon: '❄️', label: 'Schneeschauer' },
    { codes: [95], icon: '⛈️', label: 'Gewitter' },
    { codes: [96, 99], icon: '⛈️', label: 'Gewitter mit Hagel' },
];

function ensureMap() {
    if (map) {
        return true;
    }
    if (typeof window.L === 'undefined') {
        if (!mapWarningLogged) {
            console.warn('Leaflet library not available, map will be disabled. Ensure the Leaflet assets can be loaded (internet connection, CDN access).');
            mapWarningLogged = true;
        }
        return false;
    }
    map = window.L.map('map', {
        zoomControl: false
    }).setView([51.1657, 10.4515], 6);

    window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    return true;
}

function isValidNumber(value) {
    return typeof value === 'number' && Number.isFinite(value);
}

function formatMeasurement(value, unit, options = {}) {
    if (!isValidNumber(value)) {
        return null;
    }
    const appendUnit = (formattedValue) => {
        if (!unit) {
            return formattedValue;
        }
        if (unit === '%') {
            return `${formattedValue}\u00A0%`;
        }
        if (unit === '°') {
            return `${formattedValue}°`;
        }
        return `${formattedValue}\u00A0${unit}`;
    };
    if (value === 0) {
        const zeroText = '0';
        return appendUnit(zeroText);
    }

    const formatOptions = {
        maximumFractionDigits: options.maximumFractionDigits,
        minimumFractionDigits: options.minimumFractionDigits,
    };

    if (formatOptions.maximumFractionDigits === undefined) {
        formatOptions.maximumFractionDigits = value < 1 ? 2 : 1;
    }

    if (formatOptions.minimumFractionDigits === undefined) {
        formatOptions.minimumFractionDigits = value < 1 ? 1 : 0;
    }

    const formatted = value.toLocaleString('de-DE', formatOptions);
    return appendUnit(formatted);
}

function formatTemperature(value) {
    return formatMeasurement(value, '°C', {
        maximumFractionDigits: 1,
        minimumFractionDigits: 1,
    });
}

function formatWindSpeed(value) {
    return formatMeasurement(value, 'km/h', {
        maximumFractionDigits: 1,
        minimumFractionDigits: 0,
    });
}

function formatPrecipitationAmount(value, unit) {
    const normalizedUnit = unit || 'mm';
    const options = value < 1
        ? { maximumFractionDigits: 2, minimumFractionDigits: 1 }
        : { maximumFractionDigits: 1, minimumFractionDigits: 0 };
    return formatMeasurement(value, normalizedUnit, options);
}

function formatProbability(value, unit) {
    const normalizedUnit = unit || '%';
    return formatMeasurement(value, normalizedUnit, {
        maximumFractionDigits: 0,
        minimumFractionDigits: 0,
    });
}

function formatDegrees(value) {
    if (!isValidNumber(value)) {
        return null;
    }
    const normalized = ((value % 360) + 360) % 360;
    return `${Math.round(normalized)}°`;
}

function describeWindDirection(value) {
    if (!isValidNumber(value)) {
        return null;
    }
    const normalized = ((value % 360) + 360) % 360;
    const index = Math.round(normalized / 22.5) % WIND_DIRECTIONS.length;
    const direction = WIND_DIRECTIONS[index];
    return {
        ...direction,
        degrees: normalized,
    };
}

function describeWeatherCode(code) {
    if (!isValidNumber(code)) {
        return null;
    }
    const rounded = Math.round(code);
    const entry = WEATHER_CODE_MAP.find((item) => item.codes.includes(rounded));
    if (entry) {
        return {
            icon: entry.icon,
            label: entry.label,
        };
    }
    return {
        icon: '🌡️',
        label: 'Aktuelle Wetterlage',
    };
}

function createWeatherSummaryElement(weather) {
    const info = describeWeatherCode(Number(weather?.weathercode));
    if (!info) {
        return null;
    }
    const summary = document.createElement('div');
    summary.classList.add('weather-summary');
    if (info.icon) {
        const icon = document.createElement('span');
        icon.classList.add('weather-icon');
        icon.setAttribute('aria-hidden', 'true');
        icon.textContent = info.icon;
        summary.appendChild(icon);
    }
    const text = document.createElement('span');
    text.textContent = info.label;
    summary.appendChild(text);
    return summary;
}

function createLabeledValueElement(tagName, label, value, fallback = '–') {
    const element = document.createElement(tagName);
    const strong = document.createElement('strong');
    strong.textContent = `${label}:`;
    element.appendChild(strong);
    const text = document.createTextNode(` ${value ?? fallback}`);
    element.appendChild(text);
    return element;
}

function collectPrecipitationDetails(weather) {
    if (!weather || typeof weather !== 'object') {
        return [];
    }
    const details = [];
    const precipitationAmount = Number(weather.precipitation);
    if (isValidNumber(precipitationAmount)) {
        const precipitationUnit = typeof weather.precipitation_unit === 'string'
            ? weather.precipitation_unit
            : 'mm';
        const formattedPrecipitation = formatPrecipitationAmount(precipitationAmount, precipitationUnit);
        if (formattedPrecipitation) {
            details.push({
                label: 'Niederschlag',
                value: formattedPrecipitation,
            });
        }
    }

    const probability = Number(weather.precipitation_probability);
    if (isValidNumber(probability)) {
        const unit = typeof weather.precipitation_probability_unit === 'string'
            ? weather.precipitation_probability_unit
            : '%';
        const formattedProbability = formatProbability(probability, unit);
        if (formattedProbability) {
            details.push({
                label: 'Niederschlagswahrscheinlichkeit',
                value: formattedProbability,
            });
        }
    }

    return details;
}

ensureMap();

const alarmView = document.getElementById('alarm-view');
const idleView = document.getElementById('idle-view');
const mapPanel = document.getElementById('map-panel');
const mapColumn = document.getElementById('map-column');
const mapElement = document.getElementById('map');
const mapPlaceholder = document.getElementById('map-placeholder');
const alarmLayout = document.getElementById('alarm-layout');
const timestampEl = document.getElementById('timestamp');
const idleTimeEl = document.getElementById('idle-time');
const idleDateEl = document.getElementById('idle-date');
const idleWeatherEl = document.getElementById('idle-weather');
const alarmTimeEl = document.getElementById('alarm-time');
const idleLastAlarmEl = document.getElementById('idle-last-alarm');
const keywordSecondaryEl = document.getElementById('keyword-secondary');
const remarkEl = document.getElementById('remark');
const locationTownEl = document.getElementById('location-town');
const locationVillageEl = document.getElementById('location-village');
const locationStreetEl = document.getElementById('location-street');
const locationAdditionalEl = document.getElementById('location-additional');

function setMode(mode) {
    if (mode === 'alarm') {
        alarmView.classList.remove('hidden');
        idleView.classList.add('hidden');
        if (map) {
            setTimeout(() => {
                map.invalidateSize();
            }, 200);
        }
    } else {
        alarmView.classList.add('hidden');
        idleView.classList.remove('hidden');
        if (mapPanel) {
            mapPanel.classList.add('hidden');
        }
        if (mapColumn) {
            mapColumn.classList.add('hidden');
        }
        if (alarmLayout) {
            alarmLayout.classList.remove('has-map');
        }
    }
}

function updateWeather(weather) {
    const container = document.getElementById('weather');
    container.innerHTML = '';

    const heading = document.createElement('h3');
    heading.textContent = 'Wetter am Einsatzort';
    container.appendChild(heading);

    if (!weather) {
        const empty = document.createElement('p');
        empty.textContent = 'Keine Daten verfügbar';
        container.appendChild(empty);
        return;
    }

    const summary = createWeatherSummaryElement(weather);
    if (summary) {
        container.appendChild(summary);
    }

    const temperatureText = formatTemperature(Number(weather.temperature)) ?? '–';
    const windSpeedText = formatWindSpeed(Number(weather.windspeed)) ?? '–';
    const windInfo = describeWindDirection(Number(weather.winddirection));
    const directionText = windInfo
        ? windInfo.abbr
        : formatMeasurement(Number(weather.winddirection), '°');

    const details = document.createElement('div');
    details.classList.add('weather-details');

    const temperature = createLabeledValueElement('p', 'Temperatur', temperatureText);
    const wind = createLabeledValueElement('p', 'Wind', windSpeedText);
    const direction = createLabeledValueElement('p', 'Richtung', directionText);
    if (windInfo) {
        const degreesText = formatDegrees(windInfo.degrees);
        if (degreesText) {
            direction.title = `≈ ${degreesText}`;
        }
    }

    details.appendChild(temperature);
    details.appendChild(wind);
    details.appendChild(direction);

    collectPrecipitationDetails(weather).forEach((entry) => {
        const element = createLabeledValueElement('p', entry.label, entry.value);
        details.appendChild(element);
    });

    container.appendChild(details);
}

function updateIdleWeather(weather) {
    idleWeatherEl.innerHTML = '';
    const title = document.createElement('h3');
    title.textContent = 'Aktuelles Wetter';
    idleWeatherEl.appendChild(title);

    if (!weather) {
        const empty = document.createElement('p');
        empty.textContent = 'Keine Daten verfügbar';
        idleWeatherEl.appendChild(empty);
        return;
    }

    const summary = createWeatherSummaryElement(weather);
    if (summary) {
        idleWeatherEl.appendChild(summary);
    }

    const list = document.createElement('div');
    list.classList.add('idle-weather-details');

    const temperatureText = formatTemperature(Number(weather.temperature)) ?? '–';
    const windSpeedText = formatWindSpeed(Number(weather.windspeed)) ?? '–';
    const windInfo = describeWindDirection(Number(weather.winddirection));
    const directionText = windInfo
        ? windInfo.abbr
        : formatMeasurement(Number(weather.winddirection), '°');

    const temperature = createLabeledValueElement('div', 'Temperatur', temperatureText);
    const wind = createLabeledValueElement('div', 'Wind', windSpeedText);
    const direction = createLabeledValueElement('div', 'Richtung', directionText);
    if (windInfo) {
        const degreesText = formatDegrees(windInfo.degrees);
        if (degreesText) {
            direction.title = `≈ ${degreesText}`;
        }
    }

    list.appendChild(temperature);
    list.appendChild(wind);
    list.appendChild(direction);

    collectPrecipitationDetails(weather).forEach((entry) => {
        const element = createLabeledValueElement('div', entry.label, entry.value);
        list.appendChild(element);
    });

    idleWeatherEl.appendChild(list);
}

function updateIdleClock() {
    const now = new Date();
    const time = now.toLocaleTimeString('de-DE', {
        hour: '2-digit',
        minute: '2-digit'
    });
    const date = now.toLocaleDateString('de-DE', {
        weekday: 'long',
        day: '2-digit',
        month: 'long',
        year: 'numeric'
    });
    idleTimeEl.textContent = time;
    idleDateEl.textContent = date;
}

setInterval(updateIdleClock, 1000);
updateIdleClock();

function formatTimestamp(value) {
    if (!value) {
        return null;
    }
    const parsed = new Date(value);
    if (!Number.isNaN(parsed.getTime())) {
        return parsed.toLocaleString('de-DE', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
    return value;
}

function updateGroups(groups) {
    const groupsEl = document.getElementById('groups');
    if (!groupsEl) {
        return;
    }

    groupsEl.innerHTML = '';

    if (!groups) {
        const empty = document.createElement('li');
        empty.textContent = '-';
        groupsEl.appendChild(empty);
        return;
    }

    const entries = Array.isArray(groups) ? groups : String(groups).split(/;|\n/);
    entries
        .map((entry) => entry.trim())
        .filter((entry) => entry.length > 0)
        .forEach((entry) => {
            const li = document.createElement('li');
            li.textContent = entry;
            groupsEl.appendChild(li);
        });

    if (!groupsEl.hasChildNodes()) {
        const emptyFallback = document.createElement('li');
        emptyFallback.textContent = '-';
        groupsEl.appendChild(emptyFallback);
    }
}

function updateLocationDetails(details) {
    const mapping = [
        [locationTownEl, details?.town],
        [locationVillageEl, details?.village],
        [locationStreetEl, details?.street],
        [locationAdditionalEl, details?.additional || details?.object],
    ];

    mapping.forEach(([element, value]) => {
        if (!element) {
            return;
        }
        element.textContent = value && value.length > 0 ? value : '-';
    });
}

function updateIdleLastAlarm(info) {
    if (!idleLastAlarmEl) {
        return;
    }

    idleLastAlarmEl.innerHTML = '<h3>Letzter Einsatz</h3>';

    if (!info) {
        const empty = document.createElement('p');
        empty.textContent = 'Keine Einsätze vorhanden';
        idleLastAlarmEl.appendChild(empty);
        return;
    }

    const keyword = info.keyword || 'Unbekannter Einsatz';
    const timestamp =
        formatTimestamp(info.timestamp || info.received_at) ||
        info.timestamp_display ||
        info.timestamp ||
        info.received_at;
    const location = info.location;

    const keywordEl = document.createElement('p');
    keywordEl.innerHTML = `<strong>${keyword}</strong>`;
    idleLastAlarmEl.appendChild(keywordEl);

    if (location) {
        const locationEl = document.createElement('p');
        locationEl.textContent = location;
        idleLastAlarmEl.appendChild(locationEl);
    }

    if (timestamp) {
        const timeEl = document.createElement('p');
        timeEl.textContent = timestamp;
        idleLastAlarmEl.appendChild(timeEl);
    }
}

function resolveCoordinates(primary, fallbackLat, fallbackLon) {
    if (primary && primary.lat !== undefined && primary.lon !== undefined) {
        return primary;
    }

    if (fallbackLat != null && fallbackLon != null) {
        return {
            lat: fallbackLat,
            lon: fallbackLon,
        };
    }

    return null;
}

function showMapPlaceholder(message) {
    if (!mapPanel) {
        return;
    }
    if (mapPlaceholder) {
        mapPlaceholder.textContent = message;
        mapPlaceholder.classList.remove('hidden');
    }
    if (mapElement) {
        mapElement.classList.add('hidden');
    }
    if (marker && typeof marker.remove === 'function') {
        marker.remove();
    }
    marker = null;
}

function showMapContent() {
    if (mapPlaceholder) {
        mapPlaceholder.classList.add('hidden');
    }
    if (mapElement) {
        mapElement.classList.remove('hidden');
    }
}

function updateMap(coordinates, location) {
    if (!mapPanel) {
        return;
    }

    mapPanel.classList.remove('hidden');
    if (mapColumn) {
        mapColumn.classList.remove('hidden');
    }
    if (alarmLayout) {
        alarmLayout.classList.add('has-map');
    }

    if (!coordinates) {
        showMapPlaceholder('Keine Koordinaten verfügbar.');
        return;
    }

    const { lat, lon } = coordinates;
    const latNum = Number(lat);
    const lonNum = Number(lon);
    if (!Number.isFinite(latNum) || !Number.isFinite(lonNum)) {
        showMapPlaceholder('Übermittelte Koordinaten sind ungültig.');
        return;
    }

    if (!ensureMap()) {
        showMapPlaceholder('Kartendienst derzeit nicht verfügbar. Bitte Internetverbindung sowie Zugriff auf Leaflet- und OpenStreetMap-Ressourcen prüfen.');
        return;
    }

    showMapContent();
    map.setView([latNum, lonNum], 15);
    if (marker) {
        marker.setLatLng([latNum, lonNum]);
    } else if (window.L) {
        marker = window.L.marker([latNum, lonNum]).addTo(map);
    }
    if (!marker) {
        return;
    }
    marker.bindPopup(location || 'Einsatzort').openPopup();
    setTimeout(() => {
        map.invalidateSize();
    }, 150);
}

async function fetchAlarm() {
    const response = await fetch('/api/alarm');
    if (!response.ok) {
        throw new Error('API request failed');
    }
    return response.json();
}

function updateDashboard(data) {
    const alarm = data.alarm;
    const keywordEl = document.getElementById('keyword');

    if (data.mode === 'alarm' && alarm) {
        setMode('alarm');
        const entryTime = alarm.timestamp_display || alarm.timestamp || data.received_at;
        const formattedTime = formatTimestamp(alarm.timestamp || data.received_at) || entryTime;
        if (timestampEl) {
            timestampEl.textContent = formattedTime
                ? `Alarm eingegangen: ${formattedTime}`
                : 'Aktive Alarmierung';
            timestampEl.classList.remove('hidden');
        }
        const village = alarm.location_details?.village;
        const keywordText = alarm.keyword || alarm.subject || '-';
        const separator = keywordText.includes(' – ') ? ' – ' : ' - ';
        keywordEl.textContent = village ? `${keywordText}${separator}${village}` : keywordText;
        if (keywordSecondaryEl) {
            keywordSecondaryEl.textContent = alarm.keyword_secondary || '';
            keywordSecondaryEl.classList.toggle('hidden', !alarm.keyword_secondary);
        }
        if (remarkEl) {
            remarkEl.textContent = alarm.remark || '';
            remarkEl.classList.toggle('hidden', !alarm.remark);
        }
        updateGroups(alarm.aao_groups || alarm.groups);
        updateLocationDetails(alarm.location_details || {});
        alarmTimeEl.textContent = formattedTime || '-';

        updateWeather(data.weather);
        const coordinates = resolveCoordinates(
            data.coordinates,
            alarm.latitude,
            alarm.longitude,
        );
        updateMap(coordinates, alarm.location);
    } else {
        setMode('idle');
        if (timestampEl) {
            timestampEl.textContent = 'Keine aktuellen Einsätze';
            timestampEl.classList.remove('hidden');
        }
        updateIdleWeather(data.weather);
        updateIdleLastAlarm(data.last_alarm);
        if (keywordSecondaryEl) {
            keywordSecondaryEl.textContent = '';
            keywordSecondaryEl.classList.add('hidden');
        }
        if (remarkEl) {
            remarkEl.textContent = '';
            remarkEl.classList.add('hidden');
        }
        if (mapPanel) {
            mapPanel.classList.add('hidden');
        }
        if (mapColumn) {
            mapColumn.classList.add('hidden');
        }
        if (alarmLayout) {
            alarmLayout.classList.remove('has-map');
        }
        updateGroups(null);
        updateLocationDetails({});
    }
}

async function poll() {
    try {
        const data = await fetchAlarm();
        updateDashboard(data);
    } catch (error) {
        console.error('Failed to refresh dashboard', error);
    } finally {
        setTimeout(poll, 15000);
    }
}

poll();
