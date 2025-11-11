const mapCanvas = document.getElementById('navigation-map');
const statusEl = document.getElementById('navigation-status');
const targetEl = document.getElementById('navigation-target');
const startEl = document.getElementById('navigation-start');
const destinationEl = document.getElementById('navigation-destination');
const distanceEl = document.getElementById('navigation-distance');
const durationEl = document.getElementById('navigation-duration');

let mapInstance = null;
let routeLayer = null;
let startMarker = null;
let destinationMarker = null;
const navigationConfig = window.navigationConfig || {};
const configuredStart = navigationConfig.defaultStart || null;

function setStatus(message, type = 'info') {
    if (!statusEl) {
        return;
    }
    statusEl.textContent = message || '';
    statusEl.classList.toggle('navigation-status--error', type === 'error');
    if (message) {
        statusEl.classList.remove('hidden');
        statusEl.setAttribute('aria-hidden', 'false');
    } else {
        statusEl.classList.add('hidden');
        statusEl.setAttribute('aria-hidden', 'true');
    }
}

function showMapMessage(message) {
    if (!mapCanvas) {
        return;
    }
    mapCanvas.textContent = message;
    mapCanvas.classList.add('navigation-map--message');
    mapCanvas.setAttribute('aria-hidden', 'false');
}

function clearMapMessage() {
    if (!mapCanvas) {
        return;
    }
    mapCanvas.textContent = '';
    mapCanvas.classList.remove('navigation-map--message');
    mapCanvas.removeAttribute('aria-hidden');
}

function ensureLeafletMap() {
    if (!mapCanvas || typeof window === 'undefined') {
        return null;
    }
    if (mapInstance) {
        return mapInstance;
    }
    if (!window.L || typeof window.L.map !== 'function') {
        return null;
    }

    clearMapMessage();
    mapInstance = window.L.map(mapCanvas, {
        zoomControl: true,
        attributionControl: true,
    });
    window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkende',
        maxZoom: 19,
    }).addTo(mapInstance);
    window.setTimeout(() => {
        mapInstance.invalidateSize();
    }, 250);
    return mapInstance;
}

function formatCoordinatePair(coords) {
    if (!coords) {
        return '–';
    }
    const lat = Number(coords.lat);
    const lon = Number(coords.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        return '–';
    }
    const formattedLat = lat.toFixed(5);
    const formattedLon = lon.toFixed(5);
    if (typeof coords.accuracy === 'number' && Number.isFinite(coords.accuracy)) {
        const accuracy = Math.round(coords.accuracy);
        return `${formattedLat}°, ${formattedLon}° (±${accuracy}\u00A0m)`;
    }
    return `${formattedLat}°, ${formattedLon}°`;
}

function formatDistance(meters) {
    if (!Number.isFinite(meters) || meters <= 0) {
        return '–';
    }
    if (meters < 950) {
        return `${Math.round(meters)}\u00A0m`;
    }
    const kilometers = meters / 1000;
    return `${kilometers.toLocaleString('de-DE', {
        maximumFractionDigits: kilometers < 10 ? 1 : 0,
    })}\u00A0km`;
}

function formatDuration(seconds) {
    if (!Number.isFinite(seconds) || seconds <= 0) {
        return '–';
    }
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) {
        return `${minutes}\u00A0Min`;
    }
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    if (remainingMinutes === 0) {
        return `${hours}\u00A0Std`;
    }
    return `${hours}\u00A0Std ${remainingMinutes}\u00A0Min`;
}

function describeAlarmLocation(alarm) {
    if (!alarm) {
        return null;
    }
    if (typeof alarm.location === 'string' && alarm.location.trim().length > 0) {
        return alarm.location.trim();
    }
    const details = alarm.location_details;
    if (!details || typeof details !== 'object') {
        return null;
    }
    const parts = [];
    ['street', 'additional', 'object', 'village', 'town'].forEach((key) => {
        const value = details[key];
        if (typeof value === 'string') {
            const trimmed = value.trim();
            if (trimmed.length > 0 && !parts.includes(trimmed)) {
                parts.push(trimmed);
            }
        }
    });
    if (parts.length === 0) {
        return null;
    }
    return parts.join(', ');
}

function resolveCoordinates(coordinates, fallbackLat, fallbackLon) {
    const candidates = [];
    if (coordinates && coordinates.lat != null && coordinates.lon != null) {
        candidates.push({ lat: coordinates.lat, lon: coordinates.lon });
    }
    if (fallbackLat != null && fallbackLon != null) {
        candidates.push({ lat: fallbackLat, lon: fallbackLon });
    }
    for (const entry of candidates) {
        const lat = Number(entry.lat);
        const lon = Number(entry.lon);
        if (Number.isFinite(lat) && Number.isFinite(lon)) {
            return { lat, lon };
        }
    }
    return null;
}

function fetchAlarm() {
    return fetch('/api/alarm').then((response) => {
        if (!response.ok) {
            throw new Error('Alarmdaten konnten nicht geladen werden.');
        }
        return response.json();
    });
}

async function requestRoute(start, destination) {
    const baseUrl = 'https://router.project-osrm.org/route/v1/driving/';
    const query = `${start.lon},${start.lat};${destination.lon},${destination.lat}`;
    const params = '?overview=full&geometries=geojson';
    const response = await fetch(`${baseUrl}${query}${params}`);
    if (!response.ok) {
        throw new Error('Die Route konnte nicht berechnet werden.');
    }
    const data = await response.json();
    if (!data || data.code !== 'Ok' || !Array.isArray(data.routes) || data.routes.length === 0) {
        throw new Error('Für die Strecke wurde keine Route gefunden.');
    }
    return data.routes[0];
}

function updateRouteOnMap(start, destination, route) {
    const map = ensureLeafletMap();
    if (!map) {
        throw new Error('Kartendienst ist derzeit nicht verfügbar.');
    }

    if (routeLayer) {
        map.removeLayer(routeLayer);
    }
    if (startMarker) {
        map.removeLayer(startMarker);
    }
    if (destinationMarker) {
        map.removeLayer(destinationMarker);
    }

    const coordinates = route.geometry?.coordinates?.map((pair) => [pair[1], pair[0]]);
    if (!coordinates || coordinates.length === 0) {
        throw new Error('Die Route enthält keine Geometrie.');
    }

    routeLayer = window.L.polyline(coordinates, {
        color: '#c1121f',
        weight: 6,
        opacity: 0.85,
        lineJoin: 'round',
        lineCap: 'round',
    }).addTo(map);

    startMarker = window.L.marker([start.lat, start.lon], {
        title: 'Aktueller Standort',
    }).addTo(map);
    destinationMarker = window.L.marker([destination.lat, destination.lon], {
        title: 'Einsatzort',
    }).addTo(map);

    const bounds = routeLayer.getBounds();
    if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [32, 32] });
    }

    if (distanceEl) {
        distanceEl.textContent = formatDistance(route.distance);
    }
    if (durationEl) {
        durationEl.textContent = formatDuration(route.duration);
    }
}

function showDestinationOnly(destination) {
    const map = ensureLeafletMap();
    if (!map) {
        return false;
    }

    if (routeLayer) {
        map.removeLayer(routeLayer);
        routeLayer = null;
    }
    if (startMarker) {
        map.removeLayer(startMarker);
        startMarker = null;
    }
    if (destinationMarker) {
        map.removeLayer(destinationMarker);
    }

    destinationMarker = window.L.marker([destination.lat, destination.lon], {
        title: 'Einsatzort',
    }).addTo(map);
    map.setView([destination.lat, destination.lon], 16);
    return true;
}

async function initializeNavigation() {
    let destinationCoordinates = null;
    try {
        setStatus('Einsatzdaten werden geladen …');
        showMapMessage('Karte wird vorbereitet …');
        const data = await fetchAlarm();

        if (!data || data.mode !== 'alarm' || !data.alarm) {
            const idleMessage = 'Aktuell liegt kein Einsatz zur Navigation vor.';
            targetEl.textContent = idleMessage;
            destinationEl.textContent = '–';
            setStatus(idleMessage, 'error');
            showMapMessage(idleMessage);
            return;
        }

        const alarm = data.alarm;
        const locationText = describeAlarmLocation(alarm) || 'Einsatzort unbekannt';
        const keyword = alarm.keyword || alarm.subject || 'Aktueller Einsatz';
        const separator = keyword.includes(' – ') ? ' – ' : ' – ';
        targetEl.textContent = `${keyword}${separator}${locationText}`;
        destinationEl.textContent = locationText;

        destinationCoordinates = resolveCoordinates(
            data.coordinates,
            alarm.latitude,
            alarm.longitude,
        );
        if (!destinationCoordinates) {
            const message = 'Für den aktuellen Einsatz stehen keine Navigationskoordinaten zur Verfügung.';
            setStatus(message, 'error');
            showMapMessage(message);
            return;
        }

        const startCoordinates = resolveCoordinates(configuredStart);
        if (!startCoordinates) {
            const message = 'Es ist kein fester Startpunkt für die Navigation konfiguriert.';
            setStatus(message, 'error');
            showMapMessage(message);
            return;
        }
        if (startEl) {
            const label =
                configuredStart && typeof configuredStart.label === 'string'
                    ? configuredStart.label.trim()
                    : '';
            const formattedCoordinates = formatCoordinatePair(startCoordinates);
            startEl.textContent = label ? `${label} (${formattedCoordinates})` : formattedCoordinates;
        }

        setStatus('Berechne Route …');
        const route = await requestRoute(startCoordinates, destinationCoordinates);
        updateRouteOnMap(startCoordinates, destinationCoordinates, route);
        setStatus('Route bereit. Gute Fahrt!');
    } catch (error) {
        console.error('Navigation konnte nicht geladen werden', error);
        const message = error instanceof Error ? error.message : 'Navigation konnte nicht geladen werden.';
        setStatus(message, 'error');
        let fallbackShown = false;
        if (destinationCoordinates) {
            try {
                fallbackShown = showDestinationOnly(destinationCoordinates);
            } catch (mapError) {
                console.error('Fallback navigation map failed', mapError);
                fallbackShown = false;
            }
        }
        if (!fallbackShown) {
            showMapMessage(message);
        }
        if (distanceEl) {
            distanceEl.textContent = '–';
        }
        if (durationEl) {
            durationEl.textContent = '–';
        }
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeNavigation);
} else {
    initializeNavigation();
}
