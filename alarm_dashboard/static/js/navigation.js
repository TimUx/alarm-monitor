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
let userMarker = null;
let geolocationWatchId = null;
let navigationInstructions = [];
let currentInstructionIndex = 0;
let activeDestination = null;
let activeStart = null;
let navigationCompleted = false;
const navigationConfig = window.navigationConfig || {};
const configuredStart = navigationConfig.defaultStart || null;
const orsApiKey =
    typeof navigationConfig.orsApiKey === 'string' && navigationConfig.orsApiKey.trim().length > 0
        ? navigationConfig.orsApiKey.trim()
        : null;
const instructionDistanceTrigger = Number(navigationConfig.instructionDistanceTrigger) || 60;

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
    if (!orsApiKey) {
        throw new Error('Der OpenRouteService API-Schlüssel ist nicht konfiguriert.');
    }

    const body = {
        coordinates: [
            [start.lon, start.lat],
            [destination.lon, destination.lat],
        ],
        instructions: true,
        language: 'de',
    };

    const response = await fetch(
        'https://api.openrouteservice.org/v2/directions/driving-car?geometry_format=geojson',
        {
            method: 'POST',
            headers: {
                Authorization: orsApiKey,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(body),
        },
    );

    let data = null;
    try {
        data = await response.json();
    } catch (parseError) {
        if (response.ok) {
            throw new Error('Antwort des Routing-Dienstes konnte nicht gelesen werden.');
        }
    }

    if (!response.ok) {
        const message =
            (data && (data.error?.message || data.message || data.error)) ||
            'Die Route konnte nicht berechnet werden.';
        throw new Error(message);
    }

    if (!data || !Array.isArray(data.routes) || data.routes.length === 0) {
        throw new Error('Für die Strecke wurde keine Route gefunden.');
    }

    const route = data.routes[0];
    const coordinates = Array.isArray(route.geometry?.coordinates)
        ? route.geometry.coordinates.map((pair) =>
              window.L?.latLng ? window.L.latLng(pair[1], pair[0]) : { lat: pair[1], lng: pair[0] },
          )
        : [];
    if (coordinates.length === 0) {
        throw new Error('Die Route enthält keine Geometrie.');
    }

    const segment = Array.isArray(route.segments) ? route.segments[0] : null;
    const stepsSource = segment && Array.isArray(segment.steps) ? segment.steps : [];
    const steps = stepsSource
        .filter((step) => typeof step.instruction === 'string' && step.instruction.trim().length > 0)
        .map((step) => {
            const indices = Array.isArray(step.way_points) ? step.way_points : [];
            const waypointIndex = indices.length > 0 ? indices[0] : 0;
            const anchor = coordinates[Math.min(Math.max(waypointIndex, 0), coordinates.length - 1)];
            return {
                text: step.instruction.trim(),
                latlng: anchor,
                distance: Number(step.distance) || 0,
            };
        });

    const summaryDistance =
        typeof route.summary?.distance === 'number'
            ? route.summary.distance
            : typeof segment?.distance === 'number'
            ? segment.distance
            : 0;
    const summaryDuration =
        typeof route.summary?.duration === 'number'
            ? route.summary.duration
            : typeof segment?.duration === 'number'
            ? segment.duration
            : 0;

    return {
        coordinates,
        distance: summaryDistance,
        duration: summaryDuration,
        steps,
    };
}

function updateRouteOnMap(start, destination, route) {
    const map = ensureLeafletMap();
    if (!map) {
        throw new Error('Kartendienst ist derzeit nicht verfügbar.');
    }

    clearMapMessage();

    if (routeLayer) {
        map.removeLayer(routeLayer);
    }
    if (startMarker) {
        map.removeLayer(startMarker);
    }
    if (destinationMarker) {
        map.removeLayer(destinationMarker);
    }
    if (userMarker) {
        map.removeLayer(userMarker);
        userMarker = null;
    }

    const coordinates = Array.isArray(route.coordinates) ? route.coordinates : [];
    if (coordinates.length === 0) {
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
        title: 'Startpunkt',
    }).addTo(map);
    destinationMarker = window.L.marker([destination.lat, destination.lon], {
        title: 'Einsatzort',
    }).addTo(map);

    const bounds = routeLayer.getBounds();
    if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [32, 32] });
    }

    activeStart = start;
    activeDestination = destination;

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
    if (userMarker) {
        map.removeLayer(userMarker);
        userMarker = null;
    }

    destinationMarker = window.L.marker([destination.lat, destination.lon], {
        title: 'Einsatzort',
    }).addTo(map);
    map.setView([destination.lat, destination.lon], 16);
    activeDestination = destination;
    activeStart = null;
    navigationInstructions = [];
    currentInstructionIndex = 0;
    navigationCompleted = false;
    return true;
}

function speak(text) {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
        return;
    }
    const trimmed = typeof text === 'string' ? text.trim() : '';
    if (!trimmed) {
        return;
    }
    window.speechSynthesis.cancel();
    const utterance = new window.SpeechSynthesisUtterance(trimmed);
    utterance.lang = 'de-DE';
    window.speechSynthesis.speak(utterance);
}

function completeNavigation() {
    if (navigationCompleted) {
        return;
    }
    navigationCompleted = true;
    setStatus('✅ Ziel erreicht. Gute Fahrt!');
    speak('Ziel erreicht. Gute Fahrt.');
    stopGpsTracking();
}

function updateInstructionGuidance(positionLatLng) {
    const map = ensureLeafletMap();
    if (!map || navigationInstructions.length === 0) {
        return;
    }
    if (navigationCompleted) {
        return;
    }

    if (currentInstructionIndex >= navigationInstructions.length) {
        completeNavigation();
        return;
    }

    const nextStep = navigationInstructions[currentInstructionIndex];
    const distance = map.distance(positionLatLng, nextStep.latlng);

    if (distance <= instructionDistanceTrigger) {
        setStatus(`➡️ ${nextStep.text}`);
        speak(nextStep.text);
        currentInstructionIndex += 1;
        if (currentInstructionIndex >= navigationInstructions.length) {
            completeNavigation();
        }
        return;
    }

    const roundedDistance = Math.max(1, Math.round(distance));
    setStatus(`🚗 Nächste Anweisung in ${roundedDistance}\u00A0m – ${nextStep.text}`);
}

function handleGeolocationSuccess(position) {
    const map = ensureLeafletMap();
    if (!map) {
        return;
    }
    const latlng = window.L.latLng(position.coords.latitude, position.coords.longitude);

    if (userMarker) {
        userMarker.setLatLng(latlng);
    } else {
        userMarker = window.L.marker(latlng, { title: 'Eigene Position' }).addTo(map);
    }

    map.setView(latlng, Math.max(map.getZoom() || 0, 15), { animate: true });
    updateInstructionGuidance(latlng);
}

function handleGeolocationError(error) {
    const message =
        typeof error?.message === 'string' && error.message
            ? `❌ Standortfehler: ${error.message}`
            : '❌ Standort konnte nicht bestimmt werden.';
    setStatus(message, 'error');
}

function startGpsTracking() {
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
        setStatus('❌ GPS wird von diesem Gerät nicht unterstützt.', 'error');
        return;
    }
    if (geolocationWatchId !== null) {
        navigator.geolocation.clearWatch(geolocationWatchId);
        geolocationWatchId = null;
    }
    geolocationWatchId = navigator.geolocation.watchPosition(handleGeolocationSuccess, handleGeolocationError, {
        enableHighAccuracy: true,
        maximumAge: 1000,
        timeout: 10000,
    });
}

function stopGpsTracking() {
    if (typeof navigator === 'undefined' || !navigator.geolocation) {
        return;
    }
    if (geolocationWatchId !== null) {
        navigator.geolocation.clearWatch(geolocationWatchId);
        geolocationWatchId = null;
    }
}

async function initializeNavigation() {
    let destinationCoordinates = null;
    try {
        setStatus('Einsatzdaten werden geladen …');
        showMapMessage('Karte wird vorbereitet …');
        const data = await fetchAlarm();

        if (!data || data.mode !== 'alarm' || !data.alarm) {
            const idleMessage = 'Aktuell liegt kein Einsatz zur Navigation vor.';
            if (targetEl) {
                targetEl.textContent = idleMessage;
            }
            if (destinationEl) {
                destinationEl.textContent = '–';
            }
            setStatus(idleMessage, 'error');
            showMapMessage(idleMessage);
            stopGpsTracking();
            return;
        }

        const alarm = data.alarm;
        const locationText = describeAlarmLocation(alarm) || 'Einsatzort unbekannt';
        const keyword = alarm.keyword || alarm.subject || 'Aktueller Einsatz';
        const separator = keyword.includes(' – ') ? ' – ' : ' – ';
        if (targetEl) {
            targetEl.textContent = `${keyword}${separator}${locationText}`;
        }
        if (destinationEl) {
            destinationEl.textContent = locationText;
        }

        destinationCoordinates = resolveCoordinates(
            data.coordinates,
            alarm.latitude,
            alarm.longitude,
        );
        if (!destinationCoordinates) {
            const message = 'Für den aktuellen Einsatz stehen keine Navigationskoordinaten zur Verfügung.';
            setStatus(message, 'error');
            showMapMessage(message);
            stopGpsTracking();
            return;
        }

        const startCoordinates = resolveCoordinates(configuredStart);
        if (!startCoordinates) {
            const message = 'Es ist kein fester Startpunkt für die Navigation konfiguriert.';
            setStatus(message, 'error');
            showMapMessage(message);
            stopGpsTracking();
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
        if (destinationEl) {
            const formattedDestination = formatCoordinatePair(destinationCoordinates);
            destinationEl.textContent =
                locationText && locationText !== 'Einsatzort unbekannt'
                    ? `${locationText} (${formattedDestination})`
                    : formattedDestination;
        }

        setStatus('Berechne Route …');
        const route = await requestRoute(startCoordinates, destinationCoordinates);

        navigationInstructions = Array.isArray(route.steps) ? route.steps : [];
        currentInstructionIndex = 0;
        navigationCompleted = false;

        updateRouteOnMap(startCoordinates, destinationCoordinates, route);

        if (navigationInstructions.length === 0) {
            setStatus('Navigation gestartet. Folge der Karte zum Ziel.');
        } else {
            setStatus('Route berechnet. Warte auf GPS …');
        }
        speak('Navigation gestartet.');
        startGpsTracking();
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
        navigationInstructions = [];
        currentInstructionIndex = 0;
        navigationCompleted = false;
        stopGpsTracking();
    }
}

if (typeof window !== 'undefined') {
    window.addEventListener('beforeunload', stopGpsTracking);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeNavigation);
} else {
    initializeNavigation();
}
