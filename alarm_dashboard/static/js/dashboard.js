const map = L.map('map', {
    zoomControl: false
}).setView([51.1657, 10.4515], 6);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);

let marker = null;

const alarmView = document.getElementById('alarm-view');
const idleView = document.getElementById('idle-view');
const mapSection = document.getElementById('map-section');
const timestampEl = document.getElementById('timestamp');
const idleTimeEl = document.getElementById('idle-time');
const idleDateEl = document.getElementById('idle-date');
const idleWeatherEl = document.getElementById('idle-weather');
const alarmTimeEl = document.getElementById('alarm-time');
const idleLastAlarmEl = document.getElementById('idle-last-alarm');
const keywordSecondaryEl = document.getElementById('keyword-secondary');
const diagnosisEl = document.getElementById('diagnosis');
const remarkEl = document.getElementById('remark');
const locationTownEl = document.getElementById('location-town');
const locationVillageEl = document.getElementById('location-village');
const locationStreetEl = document.getElementById('location-street');
const locationAdditionalEl = document.getElementById('location-additional');

function setMode(mode) {
    if (mode === 'alarm') {
        alarmView.classList.remove('hidden');
        mapSection.classList.remove('hidden');
        idleView.classList.add('hidden');
        setTimeout(() => {
            map.invalidateSize();
        }, 200);
    } else {
        alarmView.classList.add('hidden');
        mapSection.classList.add('hidden');
        idleView.classList.remove('hidden');
    }
}

function updateWeather(weather) {
    const container = document.getElementById('weather');
    container.innerHTML = '<h3>Wetter am Einsatzort</h3>';
    if (!weather) {
        container.innerHTML += '<p>Keine Daten verfügbar</p>';
        return;
    }
    const details = document.createElement('div');
    details.classList.add('weather-details');
    details.innerHTML = `
        <p><strong>Temperatur:</strong> ${weather.temperature}&nbsp;°C</p>
        <p><strong>Wind:</strong> ${weather.windspeed}&nbsp;km/h</p>
        <p><strong>Richtung:</strong> ${weather.winddirection}&nbsp;°</p>
    `;
    container.appendChild(details);
}

function updateIdleWeather(weather, locationName) {
    idleWeatherEl.innerHTML = '';
    const title = document.createElement('h3');
    title.textContent = 'Aktuelles Wetter';
    idleWeatherEl.appendChild(title);

    if (locationName) {
        const place = document.createElement('div');
        place.classList.add('idle-weather-location');
        place.textContent = locationName;
        idleWeatherEl.appendChild(place);
    }

    if (!weather) {
        const empty = document.createElement('p');
        empty.textContent = 'Keine Daten verfügbar';
        idleWeatherEl.appendChild(empty);
        return;
    }

    const list = document.createElement('div');
    list.classList.add('idle-weather-details');

    const temperature = document.createElement('div');
    temperature.innerHTML = `<strong>Temperatur:</strong> ${weather.temperature}&nbsp;°C`;
    const wind = document.createElement('div');
    wind.innerHTML = `<strong>Wind:</strong> ${weather.windspeed}&nbsp;km/h`;
    const direction = document.createElement('div');
    direction.innerHTML = `<strong>Richtung:</strong> ${weather.winddirection}&nbsp;°`;

    list.appendChild(temperature);
    list.appendChild(wind);
    list.appendChild(direction);
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

function updateMap(coordinates, location) {
    if (!coordinates) {
        return;
    }
    const { lat, lon } = coordinates;
    const latNum = Number(lat);
    const lonNum = Number(lon);
    map.setView([latNum, lonNum], 15);
    if (marker) {
        marker.setLatLng([latNum, lonNum]);
    } else {
        marker = L.marker([latNum, lonNum]).addTo(map);
    }
    marker.bindPopup(location || 'Einsatzort').openPopup();
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
    const locationEl = document.getElementById('location');

    if (data.mode === 'alarm' && alarm) {
        setMode('alarm');
        const entryTime = alarm.timestamp_display || alarm.timestamp || data.received_at;
        const formattedTime = formatTimestamp(alarm.timestamp || data.received_at) || entryTime;
        timestampEl.textContent = formattedTime
            ? `Alarm eingegangen: ${formattedTime}`
            : 'Aktive Alarmierung';
        keywordEl.textContent = alarm.keyword || alarm.subject || '-';
        if (keywordSecondaryEl) {
            keywordSecondaryEl.textContent = alarm.keyword_secondary || '';
            keywordSecondaryEl.classList.toggle('hidden', !alarm.keyword_secondary);
        }
        if (diagnosisEl) {
            diagnosisEl.textContent = alarm.diagnosis || '';
            diagnosisEl.classList.toggle('hidden', !alarm.diagnosis);
        }
        if (remarkEl) {
            remarkEl.textContent = alarm.remark || '';
            remarkEl.classList.toggle('hidden', !alarm.remark);
        }
        updateGroups(alarm.groups);
        locationEl.textContent = alarm.location || '-';
        updateLocationDetails(alarm.location_details || {});
        alarmTimeEl.textContent = formattedTime || '-';

        updateWeather(data.weather);
        updateMap(data.coordinates, alarm.location);
    } else {
        setMode('idle');
        timestampEl.textContent = 'Keine aktuellen Einsätze';
        updateIdleWeather(data.weather, data.location);
        updateIdleLastAlarm(data.last_alarm);
        if (keywordSecondaryEl) {
            keywordSecondaryEl.textContent = '';
            keywordSecondaryEl.classList.add('hidden');
        }
        if (diagnosisEl) {
            diagnosisEl.textContent = '';
            diagnosisEl.classList.add('hidden');
        }
        if (remarkEl) {
            remarkEl.textContent = '';
            remarkEl.classList.add('hidden');
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
