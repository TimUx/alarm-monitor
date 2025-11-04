const mobileMapEl = document.getElementById('mobile-map');
let mobileMap = null;
let mobileMarker = null;

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
    const list = document.createElement('ul');
    list.classList.add('mobile-weather-list');
    list.innerHTML = `
        <li><span>Temperatur</span><strong>${weather.temperature}&nbsp;°C</strong></li>
        <li><span>Wind</span><strong>${weather.windspeed}&nbsp;km/h</strong></li>
        <li><span>Richtung</span><strong>${weather.winddirection}&nbsp;°</strong></li>
    `;
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

    const list = document.createElement('div');
    list.classList.add('idle-weather-details');
    list.innerHTML = `
        <div><strong>Temperatur:</strong> ${weather.temperature}&nbsp;°C</div>
        <div><strong>Wind:</strong> ${weather.windspeed}&nbsp;km/h</div>
        <div><strong>Richtung:</strong> ${weather.winddirection}&nbsp;°</div>
    `;
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
