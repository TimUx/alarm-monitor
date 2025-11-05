const mobileMapEl = document.getElementById('mobile-map');
let mobileMap = null;
let mobileMarker = null;

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

function createMobileWeatherItem(label, value, fallback = '–') {
    const item = document.createElement('li');
    const labelSpan = document.createElement('span');
    labelSpan.textContent = label;
    const valueStrong = document.createElement('strong');
    valueStrong.textContent = value ?? fallback;
    item.appendChild(labelSpan);
    item.appendChild(valueStrong);
    return item;
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

if (mobileMapEl) {
    mobileMap = L.map('mobile-map', {
        zoomControl: false,
    }).setView([51.1657, 10.4515], 6);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(mobileMap);
}

const mobileAlarmView = document.getElementById('mobile-alarm-view');
const mobileIdleView = document.getElementById('mobile-idle-view');
const mobileMapSection = document.getElementById('mobile-map-section');
const mobileWeatherCard = document.getElementById('mobile-weather-card');
const mobileTimestamp = document.getElementById('mobile-timestamp');
const mobileIdleTime = document.getElementById('mobile-idle-time');
const mobileIdleDate = document.getElementById('mobile-idle-date');
const mobileIdleWeather = document.getElementById('mobile-idle-weather');
const mobileAlarmTime = document.getElementById('mobile-alarm-time');
const mobileLastAlarm = document.getElementById('mobile-last-alarm');
const mobileKeywordSecondary = document.getElementById('mobile-keyword-secondary');
const mobileDiagnosis = document.getElementById('mobile-diagnosis');
const mobileRemark = document.getElementById('mobile-remark');
const mobileLocationTown = document.getElementById('mobile-location-town');
const mobileLocationVillage = document.getElementById('mobile-location-village');
const mobileLocationStreet = document.getElementById('mobile-location-street');
const mobileLocationAdditional = document.getElementById('mobile-location-additional');
const mobileNavigationButton = document.getElementById('mobile-navigation-button');

function setMobileMode(mode) {
    if (mode === 'alarm') {
        mobileAlarmView.classList.remove('hidden');
        mobileWeatherCard.classList.remove('hidden');
        mobileMapSection.classList.remove('hidden');
        mobileIdleView.classList.add('hidden');
        if (mobileMap) {
            setTimeout(() => {
                mobileMap.invalidateSize();
            }, 200);
        }
    } else {
        mobileAlarmView.classList.add('hidden');
        mobileWeatherCard.classList.add('hidden');
        mobileMapSection.classList.add('hidden');
        mobileIdleView.classList.remove('hidden');
    }
}

function updateMobileWeather(weather) {
    const container = document.getElementById('mobile-weather');
    container.innerHTML = '';
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

    const list = document.createElement('ul');
    list.classList.add('mobile-weather-list');

    const temperatureText = formatTemperature(Number(weather.temperature)) ?? '–';
    const windSpeedText = formatWindSpeed(Number(weather.windspeed)) ?? '–';
    const windInfo = describeWindDirection(Number(weather.winddirection));
    const directionText = windInfo
        ? `${windInfo.abbr} (${windInfo.label})`
        : formatMeasurement(Number(weather.winddirection), '°');

    const temperatureItem = createMobileWeatherItem('Temperatur', temperatureText);
    const windItem = createMobileWeatherItem('Wind', windSpeedText);
    const directionItem = createMobileWeatherItem('Richtung', directionText);
    if (windInfo) {
        const degreesText = formatDegrees(windInfo.degrees);
        if (degreesText) {
            directionItem.title = `≈ ${degreesText}`;
        }
    }

    list.appendChild(temperatureItem);
    list.appendChild(windItem);
    list.appendChild(directionItem);

    collectPrecipitationDetails(weather).forEach((entry) => {
        const item = createMobileWeatherItem(entry.label, entry.value);
        list.appendChild(item);
    });

    container.appendChild(list);
}

function updateMobileIdleWeather(weather, locationName) {
    mobileIdleWeather.innerHTML = '';
    const title = document.createElement('h3');
    title.textContent = 'Aktuelles Wetter';
    mobileIdleWeather.appendChild(title);

    if (locationName) {
        const place = document.createElement('div');
        place.classList.add('idle-weather-location');
        place.textContent = locationName;
        mobileIdleWeather.appendChild(place);
    }

    if (!weather) {
        const empty = document.createElement('p');
        empty.textContent = 'Keine Daten verfügbar';
        mobileIdleWeather.appendChild(empty);
        return;
    }

    const summary = createWeatherSummaryElement(weather);
    if (summary) {
        mobileIdleWeather.appendChild(summary);
    }

    const list = document.createElement('div');
    list.classList.add('idle-weather-details');

    const temperatureText = formatTemperature(Number(weather.temperature)) ?? '–';
    const windSpeedText = formatWindSpeed(Number(weather.windspeed)) ?? '–';
    const windInfo = describeWindDirection(Number(weather.winddirection));
    const directionText = windInfo
        ? `${windInfo.abbr} (${windInfo.label})`
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

    mobileIdleWeather.appendChild(list);
}

function updateMobileMap(coordinates, location) {
    if (!mobileMap || !coordinates) {
        return;
    }
    const { lat, lon } = coordinates;
    const latNum = Number(lat);
    const lonNum = Number(lon);
    mobileMap.setView([latNum, lonNum], 15);
    if (mobileMarker) {
        mobileMarker.setLatLng([latNum, lonNum]);
    } else {
        mobileMarker = L.marker([latNum, lonNum]).addTo(mobileMap);
    }
    mobileMarker.bindPopup(location || 'Einsatzort').openPopup();
}

function updateMobileClock() {
    const now = new Date();
    mobileIdleTime.textContent = now.toLocaleTimeString('de-DE', {
        hour: '2-digit',
        minute: '2-digit',
    });
    mobileIdleDate.textContent = now.toLocaleDateString('de-DE', {
        weekday: 'long',
        day: '2-digit',
        month: 'long',
        year: 'numeric',
    });
}

setInterval(updateMobileClock, 1000);
updateMobileClock();

async function fetchMobileAlarm() {
    const response = await fetch('/api/mobile/alarm');
    if (!response.ok) {
        throw new Error('API request failed');
    }
    return response.json();
}

function updateMobileDashboard(data) {
    const alarm = data.alarm;
    const keywordEl = document.getElementById('mobile-keyword');
    const locationEl = document.getElementById('mobile-location');

    if (data.mode === 'alarm' && alarm) {
        setMobileMode('alarm');
        const entryTime = alarm.timestamp_display || alarm.timestamp || data.received_at;
        const formattedTime =
            formatMobileTimestamp(alarm.timestamp || data.received_at) || entryTime;
        mobileTimestamp.textContent = formattedTime
            ? `Alarm eingegangen: ${formattedTime}`
            : 'Aktive Alarmierung';
        keywordEl.textContent = alarm.keyword || alarm.subject || '-';
        if (mobileKeywordSecondary) {
            mobileKeywordSecondary.textContent = alarm.keyword_secondary || '';
            mobileKeywordSecondary.classList.toggle('hidden', !alarm.keyword_secondary);
        }
        if (mobileDiagnosis) {
            mobileDiagnosis.textContent = alarm.diagnosis || 'Keine Beschreibung';
        }
        if (mobileRemark) {
            mobileRemark.textContent = alarm.remark || '';
            mobileRemark.classList.toggle('hidden', !alarm.remark);
        }
        updateMobileGroups(alarm.groups);
        locationEl.textContent = alarm.location || '-';
        updateMobileLocationDetails(alarm.location_details || {});
        mobileAlarmTime.textContent = formattedTime || '-';

        updateMobileWeather(data.weather);
        updateMobileMap(data.coordinates, alarm.location);
        updateMobileNavigation(data.coordinates, alarm.location, alarm.location_details);
    } else {
        setMobileMode('idle');
        mobileTimestamp.textContent = 'Keine aktuellen Einsätze';
        updateMobileIdleWeather(data.weather, data.location);
        updateMobileLastAlarm(data.last_alarm);
        if (mobileKeywordSecondary) {
            mobileKeywordSecondary.textContent = '';
            mobileKeywordSecondary.classList.add('hidden');
        }
        if (mobileDiagnosis) {
            mobileDiagnosis.textContent = 'Warte auf Einsatzdaten...';
        }
        if (mobileRemark) {
            mobileRemark.textContent = '';
            mobileRemark.classList.add('hidden');
        }
        updateMobileGroups(null);
        updateMobileLocationDetails({});
        updateMobileNavigation(null);
    }
}

async function pollMobile() {
    try {
        const data = await fetchMobileAlarm();
        updateMobileDashboard(data);
    } catch (error) {
        console.error('Failed to refresh mobile dashboard', error);
    } finally {
        setTimeout(pollMobile, 15000);
    }
}

pollMobile();

function formatMobileTimestamp(value) {
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
            minute: '2-digit',
        });
    }
    return value;
}

function updateMobileLastAlarm(info) {
    if (!mobileLastAlarm) {
        return;
    }

    mobileLastAlarm.innerHTML = '<h3>Letzter Einsatz</h3>';

    if (!info) {
        const empty = document.createElement('p');
        empty.textContent = 'Keine Einsätze vorhanden';
        mobileLastAlarm.appendChild(empty);
        return;
    }

    const keyword = info.keyword || 'Unbekannter Einsatz';
    const timestamp =
        formatMobileTimestamp(info.timestamp || info.received_at) ||
        info.timestamp_display ||
        info.timestamp ||
        info.received_at;
    const location = info.location;

    const keywordEl = document.createElement('p');
    keywordEl.innerHTML = `<strong>${keyword}</strong>`;
    mobileLastAlarm.appendChild(keywordEl);

    if (location) {
        const locationEl = document.createElement('p');
        locationEl.textContent = location;
        mobileLastAlarm.appendChild(locationEl);
    }

    if (timestamp) {
        const timeEl = document.createElement('p');
        timeEl.textContent = timestamp;
        mobileLastAlarm.appendChild(timeEl);
    }
}

function updateMobileGroups(groups) {
    const list = document.getElementById('mobile-groups');
    if (!list) {
        return;
    }

    list.innerHTML = '';

    if (!groups) {
        const empty = document.createElement('li');
        empty.textContent = '-';
        list.appendChild(empty);
        return;
    }

    const entries = Array.isArray(groups) ? groups : String(groups).split(/;|\n/);
    entries
        .map((entry) => entry.trim())
        .filter((entry) => entry.length > 0)
        .forEach((entry) => {
            const li = document.createElement('li');
            li.textContent = entry;
            list.appendChild(li);
        });

    if (!list.hasChildNodes()) {
        const emptyFallback = document.createElement('li');
        emptyFallback.textContent = '-';
        list.appendChild(emptyFallback);
    }
}

function updateMobileNavigation(coordinates, location, details) {
    if (!mobileNavigationButton) {
        return;
    }

    const url = buildMobileNavigationUrl(coordinates, location, details);
    if (url) {
        mobileNavigationButton.href = url;
        mobileNavigationButton.classList.remove('hidden');
    } else {
        mobileNavigationButton.removeAttribute('href');
        mobileNavigationButton.classList.add('hidden');
    }
}

function buildMobileNavigationUrl(coordinates, location, details) {
    const userAgent = (navigator.userAgent || '').toLowerCase();
    const prefersAppleMaps = /iphone|ipad|ipod|mac/.test(userAgent);

    if (coordinates && coordinates.lat !== undefined && coordinates.lon !== undefined) {
        const lat = Number(coordinates.lat);
        const lon = Number(coordinates.lon);
        if (!Number.isNaN(lat) && !Number.isNaN(lon)) {
            const destination = `${lat.toFixed(6)},${lon.toFixed(6)}`;
            return prefersAppleMaps
                ? `http://maps.apple.com/?daddr=${encodeURIComponent(destination)}`
                : `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(destination)}`;
        }
    }

    const parts = [];
    if (location) {
        parts.push(location);
    }
    if (details) {
        const detailParts = [
            details.street,
            details.additional,
            details.object,
            details.village,
            details.town,
        ];
        detailParts.forEach((part) => {
            if (part) {
                parts.push(part);
            }
        });
    }
    const query = parts.map((part) => String(part).trim()).filter(Boolean).join(', ');
    if (!query) {
        return null;
    }
    return prefersAppleMaps
        ? `http://maps.apple.com/?daddr=${encodeURIComponent(query)}`
        : `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(query)}`;
}

function updateMobileLocationDetails(details) {
    if (mobileLocationTown) {
        mobileLocationTown.textContent = details?.town || '-';
    }
    if (mobileLocationVillage) {
        mobileLocationVillage.textContent = details?.village || '-';
    }
    if (mobileLocationStreet) {
        mobileLocationStreet.textContent = details?.street || '-';
    }
    if (mobileLocationAdditional) {
        mobileLocationAdditional.textContent =
            details?.additional || details?.object || '-';
    }
}
