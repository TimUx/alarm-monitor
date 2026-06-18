/**
 * @fileoverview Alarm Monitor – main dashboard controller.
 *
 * @typedef {Object} AlarmPayload
 * @property {string} mode - 'alarm' | 'idle'
 * @property {Object|null} alarm - Raw alarm data object or null in idle mode.
 * @property {{lat: number, lon: number}|null} coordinates - Geocoded coordinates or null.
 * @property {WeatherData|null} weather - Current weather data or null.
 * @property {string|null} received_at - ISO 8601 timestamp when the alarm was received.
 *
 * @typedef {Object} WeatherData
 * @property {number} weathercode - WMO weather code.
 * @property {number} temperature - Temperature in °C.
 * @property {number} windspeed - Wind speed in km/h.
 * @property {number} winddirection - Wind direction in degrees.
 * @property {number} [precipitation] - Precipitation in mm.
 * @property {number} [precipitation_probability] - Precipitation probability in %.
 */

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

const MAP_DEFAULT_ZOOM = 17;

const ACTIVE_ALARM_STORAGE_KEY = 'alarm-monitor.active-alarm';
const DEFAULT_DISPLAY_DURATION_MINUTES = 30;

/**
 * Read the alarm display duration from the data attribute on the body element.
 * @returns {number|null} Duration in minutes or null if not set/invalid.
 */
function readDisplayDurationMinutes() {
    if (!document || !document.body) {
        return null;
    }

    const raw = document.body.dataset
        ? document.body.dataset.alarmDisplayMinutes
        : null;

    if (!raw) {
        return null;
    }

    const parsed = Number(raw);
    if (!Number.isFinite(parsed) || parsed <= 0) {
        return null;
    }

    return parsed;
}

/**
 * Resolve the alarm display duration in milliseconds.
 * @returns {number} Display duration in milliseconds.
 */
function resolveDisplayDurationMs() {
    const minutes = readDisplayDurationMinutes()
        ?? DEFAULT_DISPLAY_DURATION_MINUTES;
    const normalized = Number.isFinite(minutes) && minutes > 0
        ? minutes
        : DEFAULT_DISPLAY_DURATION_MINUTES;
    return Math.max(1, Math.floor(normalized)) * 60 * 1000;
}

const ALARM_DISPLAY_DURATION_MS = resolveDisplayDurationMs();

function getPersistentStorage() {
    try {
        if (typeof window === 'undefined' || !window.localStorage) {
            return null;
        }

        const testKey = `${ACTIVE_ALARM_STORAGE_KEY}::test`;
        window.localStorage.setItem(testKey, '1');
        window.localStorage.removeItem(testKey);
        return window.localStorage;
    } catch (error) {
        return null;
    }
}

const persistentStorage = getPersistentStorage();

function computeAlarmExpiryTimestamp(payload) {
    const candidates = [
        payload?.received_at,
        payload?.alarm?.timestamp,
        payload?.alarm?.timestamp_display,
    ];

    for (let index = 0; index < candidates.length; index += 1) {
        const value = candidates[index];
        if (!value) {
            continue;
        }

        const parsed = new Date(value);
        const time = parsed.getTime();
        if (!Number.isNaN(time)) {
            return time + ALARM_DISPLAY_DURATION_MS;
        }
    }

    return Date.now() + ALARM_DISPLAY_DURATION_MS;
}

function persistActiveAlarm(payload) {
    if (!persistentStorage || !payload || payload.mode !== 'alarm') {
        return;
    }

    try {
        const serialized = JSON.stringify({
            data: payload,
            expiresAt: computeAlarmExpiryTimestamp(payload),
            storedAt: Date.now(),
        });
        persistentStorage.setItem(ACTIVE_ALARM_STORAGE_KEY, serialized);
    } catch (error) {
        // Ignore storage failures (e.g. private browsing, quota exceeded)
    }
}

function clearActiveAlarmCache() {
    if (!persistentStorage) {
        return;
    }

    try {
        persistentStorage.removeItem(ACTIVE_ALARM_STORAGE_KEY);
    } catch (error) {
        // Ignore storage failures
    }
}

function loadActiveAlarmFromCache() {
    if (!persistentStorage) {
        return null;
    }

    try {
        const raw = persistentStorage.getItem(ACTIVE_ALARM_STORAGE_KEY);
        if (!raw) {
            return null;
        }

        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== 'object') {
            persistentStorage.removeItem(ACTIVE_ALARM_STORAGE_KEY);
            return null;
        }

        const { expiresAt, data } = parsed;
        if (!Number.isFinite(expiresAt) || expiresAt <= Date.now()) {
            persistentStorage.removeItem(ACTIVE_ALARM_STORAGE_KEY);
            return null;
        }

        if (!data || typeof data !== 'object' || data.mode !== 'alarm') {
            persistentStorage.removeItem(ACTIVE_ALARM_STORAGE_KEY);
            return null;
        }

        return data;
    } catch (error) {
        try {
            persistentStorage.removeItem(ACTIVE_ALARM_STORAGE_KEY);
        } catch (removeError) {
            // Ignore nested failures
        }
        return null;
    }
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
                label: 'Niederschlags-Wahrsch.',
                value: formattedProbability,
            });
        }
    }

    return details;
}

function getRootFontSize() {
    const root = document.documentElement;
    if (!root) {
        return 16;
    }
    const size = parseFloat(window.getComputedStyle(root).fontSize);
    return Number.isFinite(size) ? size : 16;
}

function parseSpacingValue(value) {
    const parsed = Number.parseFloat(value);
    return Number.isFinite(parsed) ? parsed : 0;
}

function calculateHeadlineAvailableWidth(element) {
    if (!element) {
        return 0;
    }

    const container = element.parentElement;
    if (!container) {
        return 0;
    }

    const header = container.closest('.alarm-header');
    if (!header) {
        return container.clientWidth;
    }

    const headerStyles = window.getComputedStyle(header);
    let availableWidth = header.clientWidth;

    if (!Number.isFinite(availableWidth) || availableWidth <= 0) {
        availableWidth = container.clientWidth;
    }

    const timeEl = header.querySelector('.alarm-time');
    if (timeEl && timeEl !== element) {
        const timeRect = timeEl.getBoundingClientRect();
        if (timeRect && Number.isFinite(timeRect.width)) {
            const timeStyles = window.getComputedStyle(timeEl);
            const marginLeft = parseSpacingValue(timeStyles.marginLeft);
            const marginRight = parseSpacingValue(timeStyles.marginRight);
            availableWidth -= timeRect.width + marginLeft + marginRight;
        }
    }

    if (availableWidth > 0 && timeEl) {
        const gap = parseSpacingValue(headerStyles.columnGap || headerStyles.gap);
        availableWidth -= gap;
    }

    if (!Number.isFinite(availableWidth) || availableWidth <= 0) {
        return Math.max(1, container.clientWidth);
    }

    const containerWidth = container.clientWidth;
    if (Number.isFinite(containerWidth) && containerWidth > 0) {
        return Math.max(1, Math.min(containerWidth, availableWidth));
    }

    return Math.max(1, availableWidth);
}

function fitHeadlineToContainer(element) {
    if (!element) {
        return;
    }

    const container = element.parentElement;
    if (!container) {
        return;
    }

    const previousInlineSize = element.style.fontSize;
    element.style.fontSize = '';

    const containerWidth = calculateHeadlineAvailableWidth(element);
    if (containerWidth < 1) {
        element.style.fontSize = previousInlineSize;
        return;
    }

    const storedMaxFontSize = Number(element.dataset.maxFontSize);
    const computedFontSize = parseFloat(window.getComputedStyle(element).fontSize);
    const maxFontSize = Number.isFinite(storedMaxFontSize)
        ? Math.max(storedMaxFontSize, computedFontSize)
        : computedFontSize;

    if (!Number.isFinite(maxFontSize)) {
        element.style.fontSize = previousInlineSize;
        return;
    }

    const storedMinFontSize = Number(element.dataset.minFontSize);
    const minFontSize = Number.isFinite(storedMinFontSize)
        ? storedMinFontSize
        : getRootFontSize() * 1.3;
    const normalizedMinFontSize = Math.min(minFontSize, maxFontSize);

    element.dataset.maxFontSize = String(maxFontSize);
    element.dataset.minFontSize = String(normalizedMinFontSize);

    let fontSize = maxFontSize;
    element.style.fontSize = `${fontSize}px`;

    const maxIterations = 25;
    const tolerance = 0.5;
    let iterations = 0;

    while (iterations < maxIterations && element.scrollWidth - containerWidth > tolerance) {
        const ratio = containerWidth / element.scrollWidth;
        const proposedFontSize = Math.max(normalizedMinFontSize, Math.floor(fontSize * ratio));
        if (proposedFontSize === fontSize) {
            if (fontSize <= normalizedMinFontSize) {
                break;
            }
            fontSize = Math.max(normalizedMinFontSize, fontSize - 1);
        } else {
            fontSize = proposedFontSize;
        }
        element.style.fontSize = `${fontSize}px`;
        iterations += 1;
    }
}

function requestKeywordResize() {
    requestAlarmViewFit();
}

const alarmView = document.getElementById('alarm-view');
const idleView = document.getElementById('idle-view');
const appMainEl = document.querySelector('.app-main');
const mapPanel = document.getElementById('map-panel');
const mapColumn = document.getElementById('map-column');
const mapCanvas = document.getElementById('map-canvas');
const alarmLayout = document.getElementById('alarm-layout');
const navigationNavItem = document.getElementById('nav-navigation');
const timestampEl = document.getElementById('timestamp');
const idleTimeEl = document.getElementById('idle-time');
const idleDateEl = document.getElementById('idle-date');
const idleHeaderWeatherEl = document.getElementById('idle-header-weather');
const headerWeatherEl = document.getElementById('header-weather');
const alarmTimeEl = document.getElementById('alarm-time');
const idleLastAlarmEl = document.getElementById('idle-last-alarm');
const idleCalendarEl = document.getElementById('idle-calendar');
const idleWarningsSideEl = document.getElementById('idle-warnings-side');
const idleMessagesEl = document.getElementById('idle-messages');
const idleMessagesListEl = document.getElementById('idle-messages-list');
const keywordHeadingEl = document.getElementById('keyword');
const alarmDetailsListEl = document.getElementById('alarm-details-list');
const locationTownEl = document.getElementById('location-town');
const locationVillageEl = document.getElementById('location-village');
const locationStreetEl = document.getElementById('location-street');
const locationAdditionalEl = document.getElementById('location-additional');

let navigationTarget = null;
let leafletMapInstance = null;
let leafletIncidentMarker = null;
let leafletStationMarker = null;
let alarmExpiryTimer = null;
let idleCalendarEventsCache = [];
let idleCalendarRenderScheduled = false;
let idleCalendarConfigured = false;
let idleWarningsCache = null;
let idleShowLastAlarm = true;
let idleSidePanelShowWarnings = false;
let idleSidePanelTimer = null;
let currentDashboardMode = null;

const IDLE_CALENDAR_MAX_ROWS = 6;
const IDLE_CALENDAR_MIN_COLUMN_WIDTH = 320;
const IDLE_SIDE_ROTATION_MS = 30000;
const IDLE_FIT_MIN_SCALE = 0.35;
const IDLE_FIT_HEADER_BLEND = 0.28;
const IDLE_FIT_OVERFLOW_TOLERANCE = 2;

let idleViewFitScheduled = false;

function applyIdleFitScales(contentScale, options = {}) {
    if (!idleView) {
        return;
    }

    const clampedContent = Math.max(IDLE_FIT_MIN_SCALE, Math.min(1, contentScale));
    const derivedHeader = 1 - (1 - clampedContent) * IDLE_FIT_HEADER_BLEND;
    const headerScale = options.forceHeaderScale != null
        ? Math.max(IDLE_FIT_MIN_SCALE, Math.min(1, options.forceHeaderScale))
        : derivedHeader;

    idleView.style.setProperty('--idle-fit', clampedContent.toFixed(4));
    idleView.style.setProperty('--idle-header-fit', headerScale.toFixed(4));
}

function measureIdleViewOverflow() {
    if (!idleView) {
        return 0;
    }

    return idleView.scrollHeight - idleView.clientHeight;
}

function idleViewContentFits() {
    return measureIdleViewOverflow() <= IDLE_FIT_OVERFLOW_TOLERANCE;
}

function fitIdleView() {
    if (!idleView || idleView.classList.contains('hidden') || !document.body.classList.contains('mode-idle')) {
        return;
    }

    applyIdleFitScales(1);

    if (idleViewContentFits()) {
        return;
    }

    let low = IDLE_FIT_MIN_SCALE;
    let high = 1;
    let best = IDLE_FIT_MIN_SCALE;

    for (let iteration = 0; iteration < 14; iteration += 1) {
        const candidate = (low + high) / 2;
        applyIdleFitScales(candidate);
        if (idleViewContentFits()) {
            best = candidate;
            low = candidate;
        } else {
            high = candidate;
        }
    }

    applyIdleFitScales(best);

    if (!idleViewContentFits()) {
        applyIdleFitScales(best, { forceHeaderScale: best });
    }
}

function requestIdleViewFit() {
    if (!idleView) {
        return;
    }

    if (idleViewFitScheduled) {
        return;
    }

    idleViewFitScheduled = true;
    window.requestAnimationFrame(() => {
        idleViewFitScheduled = false;
        fitIdleView();
    });
}

const ALARM_FIT_MIN_SCALE = 0.35;
const ALARM_FIT_HEADER_BLEND = 0.28;

let alarmViewFitScheduled = false;

function resetAlarmHeadlineFitState() {
    if (!keywordHeadingEl) {
        return;
    }

    keywordHeadingEl.style.fontSize = '';
    delete keywordHeadingEl.dataset.maxFontSize;
    delete keywordHeadingEl.dataset.minFontSize;
}

function applyAlarmFitScales(contentScale, options = {}) {
    if (!alarmView) {
        return;
    }

    const clampedContent = Math.max(ALARM_FIT_MIN_SCALE, Math.min(1, contentScale));
    const derivedHeader = 1 - (1 - clampedContent) * ALARM_FIT_HEADER_BLEND;
    const headerScale = options.forceHeaderScale != null
        ? Math.max(ALARM_FIT_MIN_SCALE, Math.min(1, options.forceHeaderScale))
        : derivedHeader;

    alarmView.style.setProperty('--alarm-fit', clampedContent.toFixed(4));
    alarmView.style.setProperty('--alarm-header-fit', headerScale.toFixed(4));
}

function applyAlarmFitWithHeadline(contentScale, options = {}) {
    applyAlarmFitScales(contentScale, options);
    resetAlarmHeadlineFitState();
    fitHeadlineToContainer(keywordHeadingEl);
    layoutAlarmInfoGrids();
}

function measureAlarmViewOverflow() {
    if (!alarmView) {
        return 0;
    }

    return alarmView.scrollHeight - alarmView.clientHeight;
}

function alarmViewContentFits() {
    return measureAlarmViewOverflow() <= IDLE_FIT_OVERFLOW_TOLERANCE;
}

function invalidateAlarmMapSize() {
    if (leafletMapInstance && typeof leafletMapInstance.invalidateSize === 'function') {
        window.requestAnimationFrame(() => {
            leafletMapInstance.invalidateSize();
        });
    }
}

function fitAlarmView() {
    if (!alarmView || alarmView.classList.contains('hidden') || !document.body.classList.contains('mode-alarm')) {
        return;
    }

    applyAlarmFitWithHeadline(1);

    if (alarmViewContentFits()) {
        invalidateAlarmMapSize();
        return;
    }

    let low = ALARM_FIT_MIN_SCALE;
    let high = 1;
    let best = ALARM_FIT_MIN_SCALE;

    for (let iteration = 0; iteration < 14; iteration += 1) {
        const candidate = (low + high) / 2;
        applyAlarmFitWithHeadline(candidate);
        if (alarmViewContentFits()) {
            best = candidate;
            low = candidate;
        } else {
            high = candidate;
        }
    }

    applyAlarmFitWithHeadline(best);

    if (!alarmViewContentFits()) {
        applyAlarmFitWithHeadline(best, { forceHeaderScale: best });
    }

    invalidateAlarmMapSize();
}

function requestAlarmViewFit() {
    if (!alarmView) {
        return;
    }

    if (alarmViewFitScheduled) {
        return;
    }

    alarmViewFitScheduled = true;
    window.requestAnimationFrame(() => {
        alarmViewFitScheduled = false;
        fitAlarmView();
    });
}

function scheduleAlarmExpiry(payload) {
    clearAlarmExpiryTimer();
    const expiresAt = computeAlarmExpiryTimestamp(payload);
    const delay = expiresAt - Date.now();
    if (delay > 0) {
        alarmExpiryTimer = setTimeout(function () {
            poll();
        }, delay);
    } else {
        poll();
    }
}

function clearAlarmExpiryTimer() {
    if (alarmExpiryTimer !== null) {
        clearTimeout(alarmExpiryTimer);
        alarmExpiryTimer = null;
    }
}

const cachedActiveAlarm = loadActiveAlarmFromCache();
if (cachedActiveAlarm) {
    updateDashboard(cachedActiveAlarm);
}

function normalizeNavigationLabel(value) {
    if (value === null || value === undefined) {
        return '';
    }
    const text = typeof value === 'string' ? value : String(value);
    return text.replace(/\s+/g, ' ').trim();
}

function deriveNavigationLabel(alarm) {
    if (!alarm || typeof alarm !== 'object') {
        return '';
    }

    const details = typeof alarm.location_details === 'object' && alarm.location_details !== null
        ? alarm.location_details
        : {};

    const street = normalizeNavigationLabel(details.street);
    const houseNumber = normalizeNavigationLabel(details.house_number);
    const locality = normalizeNavigationLabel(
        [
            details.village,
            details.town,
            details.city,
            details.municipality,
            details.county,
        ].find((part) => typeof part === 'string' && part.trim().length > 0) || '',
    );

    let label = '';
    if (street) {
        label = houseNumber ? `${street} ${houseNumber}` : street;
    }

    if (label && locality) {
        label = `${label}, ${locality}`;
    } else if (!label && locality) {
        label = locality;
    }

    if (!label && typeof alarm.location === 'string') {
        label = normalizeNavigationLabel(alarm.location);
    }

    if (!label && typeof alarm.keyword === 'string') {
        label = normalizeNavigationLabel(alarm.keyword);
    }

    return label;
}

function setNavigationTarget(coordinates, label) {
    if (!navigationNavItem) {
        navigationTarget = null;
        return;
    }

    if (!coordinates || !hasValidCoordinates(coordinates)) {
        navigationTarget = null;
        delete navigationNavItem.dataset.lat;
        delete navigationNavItem.dataset.lon;
        delete navigationNavItem.dataset.label;
        return;
    }

    const lat = Number(coordinates.lat);
    const lon = Number(coordinates.lon);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        navigationTarget = null;
        return;
    }

    const normalizedLabel = normalizeNavigationLabel(label) || 'Einsatzort';
    navigationTarget = {
        lat,
        lon,
        label: normalizedLabel,
    };

    navigationNavItem.dataset.lat = lat.toString();
    navigationNavItem.dataset.lon = lon.toString();
    navigationNavItem.dataset.label = normalizedLabel;
}

function openNavigationApp() {
    if (!navigationTarget) {
        return;
    }

    const { lat, lon, label } = navigationTarget;
    const latString = lat.toFixed(6);
    const lonString = lon.toFixed(6);
    const coordinateText = `${latString},${lonString}`;
    const userAgent = (navigator.userAgent || '').toLowerCase();
    const encodedLabel = encodeURIComponent(label);

    if (/iphone|ipad|ipod|macintosh/.test(userAgent)) {
        window.location.href = `maps://?daddr=${latString},${lonString}&dirflg=d`;
        return;
    }

    if (/android/.test(userAgent)) {
        window.location.href = `geo:${latString},${lonString}?q=${latString},${lonString}(${encodedLabel})`;
        return;
    }

    const fallbackUrl = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(coordinateText)}`;
    window.open(fallbackUrl, '_blank', 'noopener');
}

if (navigationNavItem) {
    navigationNavItem.addEventListener('click', (event) => {
        if (!navigationTarget) {
            return;
        }
        event.preventDefault();
        if (typeof navigationNavItem.blur === 'function') {
            navigationNavItem.blur();
        }
        openNavigationApp();
    });
}

function hasValidCoordinates(coords) {
    if (!coords) {
        return false;
    }
    const lat = Number(coords.lat);
    const lon = Number(coords.lon);
    return Number.isFinite(lat) && Number.isFinite(lon);
}

function setNavigationAvailability(isAvailable) {
    if (!navigationNavItem) {
        return;
    }
    navigationNavItem.classList.toggle('hidden', !isAvailable);
    navigationNavItem.setAttribute('aria-disabled', isAvailable ? 'false' : 'true');
    if (navigationNavItem instanceof HTMLButtonElement) {
        navigationNavItem.disabled = !isAvailable;
    }
    if (!isAvailable) {
        navigationNavItem.blur();
    }
}

function setMode(mode) {
    const enteringIdle = mode === 'idle' && currentDashboardMode !== 'idle';
    currentDashboardMode = mode;

    if (mode === 'alarm') {
        alarmView.classList.remove('hidden');
        idleView.classList.add('hidden');
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

    if (document.body) {
        const isAlarm = mode === 'alarm';
        document.body.classList.toggle('mode-alarm', isAlarm);
        document.body.classList.toggle('mode-idle', !isAlarm);
    }

    if (mode === 'idle') {
        if (enteringIdle) {
            idleSidePanelShowWarnings = false;
            if (idleShowLastAlarm) {
                startIdleSidePanelRotation();
            } else {
                stopIdleSidePanelRotation();
            }
        }
        updateIdleSidePanelVisibility();
        requestIdleViewFit();
    } else {
        stopIdleSidePanelRotation();
        requestAlarmViewFit();
    }
}

function createHeaderWeatherChip(icon, value) {
    const chip = document.createElement('span');
    chip.classList.add('header-weather-chip');
    const iconEl = document.createElement('span');
    iconEl.setAttribute('aria-hidden', 'true');
    iconEl.textContent = icon;
    const textEl = document.createElement('span');
    textEl.textContent = value;
    chip.appendChild(iconEl);
    chip.appendChild(textEl);
    return chip;
}

function updateHeaderWeather(weather) {
    if (!headerWeatherEl) {
        return;
    }
    headerWeatherEl.innerHTML = '';

    if (!weather) {
        headerWeatherEl.classList.add('hidden');
        return;
    }

    const info = describeWeatherCode(Number(weather?.weathercode));

    const main = document.createElement('div');
    main.classList.add('header-weather-main');
    if (info?.icon) {
        const icon = document.createElement('span');
        icon.classList.add('header-weather-icon');
        icon.setAttribute('aria-hidden', 'true');
        icon.textContent = info.icon;
        main.appendChild(icon);
    }
    const tempSpan = document.createElement('span');
    tempSpan.textContent = formatTemperature(Number(weather.temperature)) ?? '–';
    main.appendChild(tempSpan);
    headerWeatherEl.appendChild(main);

    const chips = document.createElement('div');
    chips.classList.add('header-weather-chips');

    const windSpeedText = formatWindSpeed(Number(weather.windspeed)) ?? '–';
    const windInfo = describeWindDirection(Number(weather.winddirection));
    const windValue = windInfo ? `${windSpeedText} ${windInfo.abbr}` : windSpeedText;
    chips.appendChild(createHeaderWeatherChip('🌬️', windValue));

    const precipProb = Number(weather.precipitation_probability);
    if (isValidNumber(precipProb)) {
        const unit = typeof weather.precipitation_probability_unit === 'string'
            ? weather.precipitation_probability_unit
            : '%';
        const probText = formatProbability(precipProb, unit);
        if (probText) {
            chips.appendChild(createHeaderWeatherChip('💧', probText));
        }
    }

    headerWeatherEl.appendChild(chips);
    headerWeatherEl.classList.remove('hidden');
}

function createIdleHeaderWeatherChip(icon, value) {
    const chip = document.createElement('span');
    chip.classList.add('idle-header-weather-chip');
    const iconEl = document.createElement('span');
    iconEl.setAttribute('aria-hidden', 'true');
    iconEl.textContent = icon;
    const textEl = document.createElement('span');
    textEl.textContent = value;
    chip.appendChild(iconEl);
    chip.appendChild(textEl);
    return chip;
}

function updateIdleHeaderWeather(weather) {
    if (!idleHeaderWeatherEl) {
        return;
    }
    idleHeaderWeatherEl.innerHTML = '';

    if (!weather) {
        idleHeaderWeatherEl.classList.add('hidden');
        requestIdleViewFit();
        return;
    }

    const info = describeWeatherCode(Number(weather?.weathercode));

    const main = document.createElement('div');
    main.classList.add('idle-header-weather-main');
    if (info?.icon) {
        const icon = document.createElement('span');
        icon.classList.add('idle-header-weather-icon');
        icon.setAttribute('aria-hidden', 'true');
        icon.textContent = info.icon;
        main.appendChild(icon);
    }
    const tempSpan = document.createElement('span');
    tempSpan.textContent = formatTemperature(Number(weather.temperature)) ?? '–';
    main.appendChild(tempSpan);
    idleHeaderWeatherEl.appendChild(main);

    const chips = document.createElement('div');
    chips.classList.add('idle-header-weather-chips');

    const windSpeedText = formatWindSpeed(Number(weather.windspeed)) ?? '–';
    const windInfo = describeWindDirection(Number(weather.winddirection));
    const windValue = windInfo ? `${windSpeedText} ${windInfo.abbr}` : windSpeedText;
    chips.appendChild(createIdleHeaderWeatherChip('🌬️', windValue));

    const precipProb = Number(weather.precipitation_probability);
    if (isValidNumber(precipProb)) {
        const unit = typeof weather.precipitation_probability_unit === 'string'
            ? weather.precipitation_probability_unit
            : '%';
        const probText = formatProbability(precipProb, unit);
        if (probText) {
            chips.appendChild(createIdleHeaderWeatherChip('💧', probText));
        }
    }

    idleHeaderWeatherEl.appendChild(chips);
    idleHeaderWeatherEl.classList.remove('hidden');
    requestIdleViewFit();
}

function updateIdleCalendar(calendarData) {
    if (calendarData && typeof calendarData === 'object' && !Array.isArray(calendarData)) {
        idleCalendarConfigured = Boolean(calendarData.configured);
        idleCalendarEventsCache = Array.isArray(calendarData.events) ? calendarData.events : [];
    } else {
        idleCalendarEventsCache = Array.isArray(calendarData) ? calendarData : [];
    }
    requestIdleCalendarRender();
    updateIdleSidePanelVisibility();
    if (document.body && document.body.classList.contains('mode-idle') && idleShowLastAlarm) {
        startIdleSidePanelRotation();
    }
}

function requestIdleCalendarRender() {
    if (idleCalendarRenderScheduled) {
        return;
    }

    idleCalendarRenderScheduled = true;
    window.requestAnimationFrame(() => {
        idleCalendarRenderScheduled = false;
        renderIdleCalendar();
    });
}

function handleIdleCalendarWindowResize() {
    requestIdleCalendarRender();
    requestIdleViewFit();
}

function calculateIdleCalendarColumns() {
    const panel = document.getElementById('idle-side-panel');
    const measureEl = panel || idleCalendarEl;
    if (!measureEl) {
        return 1;
    }

    const availableWidth = Math.max(1, measureEl.getBoundingClientRect().width);
    return Math.max(1, Math.floor(availableWidth / IDLE_CALENDAR_MIN_COLUMN_WIDTH));
}

function renderIdleCalendar() {
    if (!idleCalendarEl) {
        return;
    }

    const events = idleCalendarEventsCache;
    idleCalendarEl.innerHTML = '';
    const title = document.createElement('h3');
    title.textContent = 'Nächste Termine';
    idleCalendarEl.appendChild(title);

    if (!events || events.length === 0) {
        const empty = document.createElement('p');
        empty.textContent = 'Keine Termine verfügbar';
        idleCalendarEl.appendChild(empty);
        updateIdleSidePanelVisibility();
        requestIdleViewFit();
        return;
    }

    const columns = calculateIdleCalendarColumns();
    const maxVisibleEvents = columns * IDLE_CALENDAR_MAX_ROWS;
    const visibleEvents = events.slice(0, maxVisibleEvents);

    const list = document.createElement('ul');
    list.classList.add('idle-calendar-list');
    list.style.setProperty('--idle-calendar-columns', String(columns));

    visibleEvents.forEach((event) => {
        const item = document.createElement('li');
        item.classList.add('idle-calendar-item');

        const dateEl = document.createElement('span');
        dateEl.classList.add('idle-calendar-item-date');
        const start = new Date(event.start);
        dateEl.textContent = start.toLocaleString('de-DE', {
            weekday: 'short',
            day: '2-digit',
            month: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
        });
        item.appendChild(dateEl);

        const titleEl = document.createElement('span');
        titleEl.classList.add('idle-calendar-item-title');
        titleEl.textContent = event.summary || '(kein Titel)';
        item.appendChild(titleEl);

        list.appendChild(item);
    });

    idleCalendarEl.appendChild(list);
    updateIdleSidePanelVisibility();
    requestIdleViewFit();
}

async function fetchCalendarEvents() {
    try {
        const response = await fetch('/api/calendar');
        if (!response.ok) {
            return null;
        }
        const data = await response.json();
        return {
            events: data.events ?? [],
            configured: Boolean(data.configured),
        };
    } catch (error) {
        return null;
    }
}

async function fetchMessages() {
    try {
        const response = await fetch('/api/messages');
        if (!response.ok) {
            return null;
        }
        const data = await response.json();
        return data.messages ?? null;
    } catch (error) {
        return null;
    }
}

function formatMessageTtl(expiresAtIso) {
    if (!expiresAtIso) {
        return null;
    }
    const expiresAt = new Date(expiresAtIso);
    const remainingMs = expiresAt.getTime() - Date.now();
    if (remainingMs <= 0) {
        return null;
    }
    const minutes = Math.floor(remainingMs / 60000);
    if (minutes < 60) {
        return `noch ${minutes}\u00A0Min.`;
    }
    const hours = Math.floor(minutes / 60);
    return `noch ${hours}\u00A0Std.`;
}

function updateIdleMessages(messages) {
    if (!idleMessagesEl || !idleMessagesListEl) {
        return;
    }

    if (!messages || messages.length === 0) {
        idleMessagesEl.classList.add('hidden');
        idleMessagesListEl.innerHTML = '';
        requestIdleViewFit();
        return;
    }

    idleMessagesListEl.innerHTML = '';
    messages.forEach((msg) => {
        const li = document.createElement('li');
        li.classList.add('idle-messages-item');

        const textEl = document.createElement('span');
        textEl.classList.add('idle-messages-item-text');
        textEl.textContent = msg.text || '';
        li.appendChild(textEl);

        if (msg.expires_at) {
            const ttlText = formatMessageTtl(msg.expires_at);
            if (ttlText) {
                const ttlEl = document.createElement('span');
                ttlEl.classList.add('idle-messages-item-ttl');
                ttlEl.textContent = ttlText;
                li.appendChild(ttlEl);
            }
        }

        idleMessagesListEl.appendChild(li);
    });

    idleMessagesEl.classList.remove('hidden');
    requestIdleViewFit();
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

setInterval(() => {
    fetchMessages().then(updateIdleMessages);
}, 60000);

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

function layoutDynamicInfoGrid(container) {
    if (!container) {
        return;
    }

    const count = container.children.length;
    if (count <= 1) {
        container.style.setProperty('--info-grid-cols', '1');
        return;
    }

    const width = container.clientWidth;
    if (width <= 0) {
        return;
    }

    const style = window.getComputedStyle(container);
    const columnGap = Number.parseFloat(style.columnGap) || 0;
    const minColWidth = 7.5 * Number.parseFloat(style.fontSize || '16');
    const maxColsByWidth = Math.max(1, Math.floor((width + columnGap) / (minColWidth + columnGap)));
    const maxCols = Math.min(count, maxColsByWidth);

    const card = container.closest('.meta-card');
    const heading = card ? card.querySelector(':scope > h3') : null;
    const cardStyle = card ? window.getComputedStyle(card) : null;
    const paddingY = cardStyle
        ? Number.parseFloat(cardStyle.paddingTop) + Number.parseFloat(cardStyle.paddingBottom)
        : 0;
    const cardGap = cardStyle ? Number.parseFloat(cardStyle.gap) || 0 : 0;
    const headingHeight = heading ? heading.offsetHeight : 0;
    const availableHeight = card && card.clientHeight > 0
        ? card.clientHeight - paddingY - headingHeight - cardGap
        : Number.POSITIVE_INFINITY;

    let chosenCols = maxCols;
    if (Number.isFinite(availableHeight)) {
        chosenCols = maxCols;
        for (let cols = 1; cols <= maxCols; cols += 1) {
            container.style.setProperty('--info-grid-cols', String(cols));
            if (container.scrollHeight <= availableHeight + 4) {
                chosenCols = cols;
                break;
            }
        }
    }

    container.style.setProperty('--info-grid-cols', String(chosenCols));
}

function layoutAlarmInfoGrids() {
    layoutDynamicInfoGrid(alarmDetailsListEl);
    layoutDynamicInfoGrid(document.getElementById('groups'));
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
        layoutDynamicInfoGrid(groupsEl);
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

    layoutDynamicInfoGrid(groupsEl);
}

function appendAlarmDetailRow(container, label, value) {
    const row = document.createElement('div');
    const dt = document.createElement('dt');
    dt.textContent = label;
    const dd = document.createElement('dd');
    dd.textContent = value;
    row.appendChild(dt);
    row.appendChild(dd);
    container.appendChild(row);
}

function updateAlarmDetails(alarm) {
    if (!alarmDetailsListEl) {
        return;
    }

    alarmDetailsListEl.innerHTML = '';

    if (!alarm) {
        appendAlarmDetailRow(alarmDetailsListEl, 'Info', 'Keine Zusatzinformationen');
        layoutDynamicInfoGrid(alarmDetailsListEl);
        return;
    }

    const keyword = (alarm.keyword || alarm.subject || '').trim();
    const rows = [];

    if (alarm.keyword_secondary) {
        rows.push(['Zusatzstichwort', alarm.keyword_secondary]);
    }
    if (alarm.remark) {
        rows.push(['Hinweis', alarm.remark]);
    }
    if (alarm.diagnosis) {
        rows.push(['Diagnose', alarm.diagnosis]);
    }
    if (alarm.subject && alarm.subject.trim() && alarm.subject.trim() !== keyword) {
        rows.push(['Betreff', alarm.subject]);
    }

    if (rows.length === 0) {
        appendAlarmDetailRow(alarmDetailsListEl, 'Info', 'Keine Zusatzinformationen');
        layoutDynamicInfoGrid(alarmDetailsListEl);
        return;
    }

    rows.forEach(([label, value]) => {
        appendAlarmDetailRow(alarmDetailsListEl, label, value);
    });

    layoutDynamicInfoGrid(alarmDetailsListEl);
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

function formatWarningTimestamp(value) {
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

function hasActiveSevereWarnings(warnings) {
    return Boolean(
        warnings
        && warnings.active
        && Array.isArray(warnings.items)
        && warnings.items.length > 0,
    );
}

function appendIdleLastAlarmContent(container, info) {
    const heading = document.createElement('h3');
    heading.textContent = 'Letzter Einsatz';
    container.appendChild(heading);

    if (!info) {
        const empty = document.createElement('p');
        empty.textContent = 'Keine Einsätze vorhanden';
        container.appendChild(empty);
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
    const strongEl = document.createElement('strong');
    strongEl.textContent = keyword;
    keywordEl.appendChild(strongEl);
    container.appendChild(keywordEl);

    if (location) {
        const locationEl = document.createElement('p');
        locationEl.textContent = location;
        container.appendChild(locationEl);
    }

    if (timestamp) {
        const timeEl = document.createElement('p');
        timeEl.textContent = timestamp;
        container.appendChild(timeEl);
    }
}

function appendWarningsMapLegend(mapWrap, legend) {
    if (!mapWrap || !Array.isArray(legend) || legend.length === 0) {
        return;
    }

    const list = document.createElement('ul');
    list.className = 'idle-warnings-map-legend';
    list.setAttribute('aria-label', 'DWD Warnstufen-Legende');

    legend.forEach((entry) => {
        const item = document.createElement('li');
        item.className = 'idle-warnings-map-legend-item';

        const swatch = document.createElement('span');
        swatch.className = 'idle-warnings-map-legend-swatch';
        swatch.style.backgroundColor = entry.color || '#ccc';
        swatch.setAttribute('aria-hidden', 'true');

        const label = document.createElement('span');
        label.className = 'idle-warnings-map-legend-label';
        label.textContent = entry.label || '';
        if (entry.label) {
            item.title = entry.label;
        }

        item.appendChild(swatch);
        item.appendChild(label);
        list.appendChild(item);
    });

    mapWrap.appendChild(list);
}

function appendIdleActiveWarningsContent(container, warnings) {
    const regionName = warnings?.bundesland?.name;
    const layout = document.createElement('div');
    layout.className = 'idle-warnings-layout';

    const details = document.createElement('div');
    details.className = 'idle-warnings-details';

    if (warnings?.mock) {
        const badge = document.createElement('p');
        badge.className = 'idle-warnings-mock-badge';
        badge.textContent = 'Simulierte Testwarnung';
        details.appendChild(badge);
    }

    warnings.items.forEach((item) => {
        const itemEl = document.createElement('article');
        itemEl.className = 'idle-warnings-item';
        if (item.level) {
            itemEl.classList.add(`idle-warnings-item--level-${item.level}`);
        }

        if (item.headline) {
            const headlineEl = document.createElement('p');
            headlineEl.className = 'idle-warnings-headline';
            const strongEl = document.createElement('strong');
            strongEl.textContent = item.headline;
            headlineEl.appendChild(strongEl);
            itemEl.appendChild(headlineEl);
        }

        if (item.description) {
            const descriptionEl = document.createElement('p');
            descriptionEl.className = 'idle-warnings-description';
            descriptionEl.textContent = item.description;
            itemEl.appendChild(descriptionEl);
        }

        const start = formatWarningTimestamp(item.start);
        const end = formatWarningTimestamp(item.end);
        if (start || end) {
            const validityEl = document.createElement('p');
            validityEl.className = 'idle-warnings-validity';
            validityEl.textContent = start && end
                ? `Gültig von ${start} bis ${end}`
                : (start ? `Gültig ab ${start}` : `Gültig bis ${end}`);
            itemEl.appendChild(validityEl);
        }

        details.appendChild(itemEl);
    });

    layout.appendChild(details);

    if (warnings.map_url) {
        const mapWrap = document.createElement('div');
        mapWrap.className = 'idle-warnings-map';
        const mapFrame = document.createElement('div');
        mapFrame.className = 'idle-warnings-map-frame';
        const mapImg = document.createElement('img');
        mapImg.src = warnings.map_url;
        mapImg.alt = regionName
            ? `DWD Warnkarte ${regionName}`
            : 'DWD Warnkarte';
        mapImg.loading = 'lazy';
        mapImg.addEventListener('load', requestIdleViewFit);
        mapImg.addEventListener('error', requestIdleViewFit);
        mapFrame.appendChild(mapImg);
        mapWrap.appendChild(mapFrame);
        appendWarningsMapLegend(mapWrap, warnings.map_legend);
        layout.appendChild(mapWrap);
        if (mapImg.complete) {
            requestIdleViewFit();
        }
    }

    container.appendChild(layout);
    requestIdleViewFit();
}

function stopIdleSidePanelRotation() {
    if (idleSidePanelTimer !== null) {
        clearInterval(idleSidePanelTimer);
        idleSidePanelTimer = null;
    }
}

function startIdleSidePanelRotation() {
    if (idleSidePanelTimer !== null || !idleCalendarConfigured || !idleShowLastAlarm) {
        return;
    }
    idleSidePanelTimer = setInterval(() => {
        idleSidePanelShowWarnings = !idleSidePanelShowWarnings;
        updateIdleSidePanelVisibility();
    }, IDLE_SIDE_ROTATION_MS);
}

function updateIdleSidePanelVisibility() {
    if (!idleShowLastAlarm) {
        if (idleCalendarEl) {
            idleCalendarEl.classList.toggle('hidden', !idleCalendarConfigured);
        }
        if (idleWarningsSideEl) {
            idleWarningsSideEl.classList.add('hidden');
        }
        if (idleCalendarConfigured) {
            requestIdleCalendarRender();
        }
        requestIdleViewFit();
        return;
    }

    const showWarnings = !idleCalendarConfigured || idleSidePanelShowWarnings;

    if (idleCalendarEl) {
        const hideCalendar = showWarnings || !idleCalendarConfigured;
        idleCalendarEl.classList.toggle('hidden', hideCalendar);
    }

    if (idleWarningsSideEl) {
        idleWarningsSideEl.classList.toggle('hidden', !showWarnings);
    }

    if (!showWarnings && idleCalendarConfigured) {
        requestIdleCalendarRender();
    }

    requestIdleViewFit();
}

function renderIdleWarningsPanel(container, warnings) {
    if (!container) {
        return;
    }

    const activeWarnings = hasActiveSevereWarnings(warnings);
    const regionName = warnings?.bundesland?.name;

    container.classList.toggle('idle-warnings-side--active', activeWarnings);
    container.innerHTML = '';

    const heading = document.createElement('h3');
    heading.textContent = regionName ? `Unwetter ${regionName}` : 'Unwetterwarnung';
    container.appendChild(heading);

    if (activeWarnings) {
        appendIdleActiveWarningsContent(container, warnings);
        return;
    }

    if (warnings != null) {
        const status = document.createElement('p');
        status.textContent = 'Aktuell liegt keine Unwetterwarnung vor.';
        container.appendChild(status);
        requestIdleViewFit();
        return;
    }

    const empty = document.createElement('p');
    empty.textContent = 'Keine Warnungsdaten verfügbar.';
    container.appendChild(empty);
    requestIdleViewFit();
}

function updateIdleWarningsSide(warnings) {
    renderIdleWarningsPanel(idleWarningsSideEl, warnings);
}

function updateIdleLastAlarm(info) {
    if (!idleLastAlarmEl) {
        return;
    }

    idleLastAlarmEl.innerHTML = '';
    appendIdleLastAlarmContent(idleLastAlarmEl, info);
    requestIdleViewFit();
}

function updateIdleMainPanel(lastAlarm, warnings, showLastAlarm) {
    idleWarningsCache = warnings;
    if (showLastAlarm !== undefined) {
        idleShowLastAlarm = showLastAlarm !== false;
    }

    if (idleShowLastAlarm) {
        if (idleLastAlarmEl) {
            idleLastAlarmEl.classList.remove('idle-warnings-side--active');
        }
        updateIdleLastAlarm(lastAlarm);
        updateIdleWarningsSide(warnings);
    } else {
        stopIdleSidePanelRotation();
        renderIdleWarningsPanel(idleLastAlarmEl, warnings);
        if (idleWarningsSideEl) {
            idleWarningsSideEl.classList.remove('idle-warnings-side--active');
            idleWarningsSideEl.innerHTML = '';
            idleWarningsSideEl.classList.add('hidden');
        }
    }

    updateIdleSidePanelVisibility();
    requestIdleCalendarRender();
    requestIdleViewFit();
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

function isLeafletAvailable() {
    return typeof window !== 'undefined'
        && typeof window.L === 'object'
        && typeof window.L.map === 'function';
}

function getFireStationCoords() {
    const config = typeof window !== 'undefined' ? window.dashboardConfig : null;
    if (!config) {
        return null;
    }

    const lat = Number(config.default_latitude);
    const lon = Number(config.default_longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
        return null;
    }

    const label = typeof config.default_location_name === 'string'
        ? config.default_location_name.trim()
        : '';

    return {
        lat,
        lon,
        label: label || 'Feuerwehr',
    };
}

function escapeMapLabel(text) {
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function createMapPinIcon(variant, label) {
    const text = typeof label === 'string' ? label.trim() : '';
    const labelHtml = text
        ? `<span class="map-pin__label">${escapeMapLabel(text)}</span>`
        : '';
    const iconWidth = text ? 120 : 28;
    const iconHeight = text ? 54 : 36;

    return window.L.divIcon({
        className: `map-pin map-pin--${variant}`,
        html: `<div class="map-pin__stack">${labelHtml}<span class="map-pin__head"></span></div>`,
        iconSize: [iconWidth, iconHeight],
        iconAnchor: [iconWidth / 2, iconHeight],
        popupAnchor: [0, -iconHeight + 6],
    });
}

function clearMapMarkers() {
    if (leafletMapInstance && leafletIncidentMarker) {
        leafletMapInstance.removeLayer(leafletIncidentMarker);
    }
    if (leafletMapInstance && leafletStationMarker) {
        leafletMapInstance.removeLayer(leafletStationMarker);
    }
    leafletIncidentMarker = null;
    leafletStationMarker = null;
}

function destroyLeafletMap() {
    clearMapMarkers();
    if (leafletMapInstance) {
        leafletMapInstance.remove();
        leafletMapInstance = null;
    }
}

function showMapPlaceholder(message) {
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

    if (mapCanvas) {
        mapCanvas.textContent = message;
        mapCanvas.classList.add('map-canvas--message');
        mapCanvas.removeAttribute('aria-hidden');
        destroyLeafletMap();
    }

    requestAlarmViewFit();
}

function ensureLeafletMapReady() {
    if (!mapCanvas || !isLeafletAvailable()) {
        return null;
    }

    if (!leafletMapInstance) {
        mapCanvas.textContent = '';
        mapCanvas.classList.remove('map-canvas--message');
        leafletMapInstance = window.L.map(mapCanvas, {
            zoomControl: false,
            attributionControl: true,
        });

        window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>-Mitwirkende',
            maxZoom: 19,
        }).addTo(leafletMapInstance);
    }

    mapCanvas.classList.remove('map-canvas--message');
    return leafletMapInstance;
}

function fitMapToAlarmMarkers(incidentLat, incidentLon) {
    if (!leafletMapInstance) {
        return;
    }

    const station = getFireStationCoords();
    const incidentPoint = window.L.latLng(incidentLat, incidentLon);
    const points = [incidentPoint];

    if (station) {
        const sameLocation = Math.abs(station.lat - incidentLat) < 0.0001
            && Math.abs(station.lon - incidentLon) < 0.0001;
        if (!sameLocation) {
            points.push(window.L.latLng(station.lat, station.lon));
        }
    }

    if (points.length > 1) {
        const bounds = window.L.latLngBounds(points);
        leafletMapInstance.fitBounds(bounds, { padding: [48, 48], maxZoom: 14 });
        return;
    }

    leafletMapInstance.setView([incidentLat, incidentLon], MAP_DEFAULT_ZOOM);
}

function showLeafletMap(lat, lon, locationLabel) {
    const mapInstance = ensureLeafletMapReady();

    if (!mapInstance) {
        showMapPlaceholder('Kartendienst derzeit nicht verfügbar. Bitte Zugriff auf OpenStreetMap prüfen.');
        return;
    }

    clearMapMarkers();

    leafletIncidentMarker = window.L.marker([lat, lon], {
        keyboard: false,
        icon: createMapPinIcon('incident', 'Einsatzort'),
        title: 'Einsatzort',
    }).addTo(mapInstance);

    const station = getFireStationCoords();
    if (station) {
        const sameLocation = Math.abs(station.lat - lat) < 0.0001
            && Math.abs(station.lon - lon) < 0.0001;
        if (!sameLocation) {
            leafletStationMarker = window.L.marker([station.lat, station.lon], {
                keyboard: false,
                icon: createMapPinIcon('station', station.label),
                title: station.label,
            }).addTo(mapInstance);
        }
    }

    fitMapToAlarmMarkers(lat, lon);

    if (mapCanvas) {
        mapCanvas.classList.remove('map-canvas--message');
        mapCanvas.removeAttribute('aria-hidden');
        const label = locationLabel || 'Einsatzort';
        mapCanvas.setAttribute('aria-label', 'Einsatzkarte für ' + label);
    }

    requestAnimationFrame(() => {
        mapInstance.invalidateSize();
        fitMapToAlarmMarkers(lat, lon);
        requestAlarmViewFit();
    });
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

    if (!isLeafletAvailable()) {
        showMapPlaceholder('Kartendienst derzeit nicht verfügbar. Bitte Zugriff auf OpenStreetMap prüfen.');
        return;
    }

    showLeafletMap(latNum, lonNum, location);
    requestAlarmViewFit();
}

/**
 * Fetch the current alarm payload from the API.
 * @returns {Promise<AlarmPayload>} The current alarm or idle payload.
 */
async function fetchAlarm() {
    const response = await fetch('/api/alarm');
    if (!response.ok) {
        throw new Error('API request failed');
    }
    return response.json();
}

/**
 * Update the dashboard UI based on the given alarm payload.
 * @param {AlarmPayload} data - The current alarm or idle payload.
 * @returns {void}
 */
function updateDashboard(data) {
    const alarm = data.alarm;

    if (data.mode === 'alarm' && alarm) {
        persistActiveAlarm(data);
        scheduleAlarmExpiry(data);
        setMode('alarm');
        const entryTime = alarm.timestamp_display || alarm.timestamp || data.received_at;
        const formattedTime = formatTimestamp(alarm.timestamp || data.received_at) || entryTime;
        if (timestampEl) {
            timestampEl.textContent = formattedTime
                ? `Alarm eingegangen: ${formattedTime}`
                : 'Aktive Alarmierung';
            timestampEl.classList.remove('hidden');
        }
        const keywordText = alarm.keyword || alarm.subject || '-';
        if (keywordHeadingEl) {
            keywordHeadingEl.textContent = keywordText;
        }
        updateAlarmDetails(alarm);
        updateGroups(alarm.aao_groups || alarm.groups);
        updateLocationDetails(alarm.location_details || {});
        if (alarmTimeEl) {
            alarmTimeEl.textContent = formattedTime || '-';
        }

        updateHeaderWeather(data.weather);
        const coordinates = resolveCoordinates(
            data.coordinates,
            alarm.latitude,
            alarm.longitude,
        );
        const navigationLabel = deriveNavigationLabel(alarm);
        const navigationAvailable = hasValidCoordinates(coordinates);
        setNavigationTarget(navigationAvailable ? coordinates : null, navigationLabel);
        setNavigationAvailability(navigationAvailable);
        updateMap(coordinates, alarm.location);
        
        // Update participants for the current alarm
        if (alarm.incident_number) {
            startParticipantsPolling(alarm.incident_number);
        }
        requestAlarmViewFit();
    } else {
        clearActiveAlarmCache();
        clearAlarmExpiryTimer();
        setMode('idle');
        setNavigationTarget(null, null);
        setNavigationAvailability(false);
        if (headerWeatherEl) {
            headerWeatherEl.classList.add('hidden');
            headerWeatherEl.innerHTML = '';
        }
        if (timestampEl) {
            timestampEl.textContent = 'Keine aktuellen Einsätze';
            timestampEl.classList.remove('hidden');
        }
        updateIdleHeaderWeather(data.weather);
        updateIdleMainPanel(data.last_alarm, data.warnings, data.show_last_alarm);
        fetchCalendarEvents().then(updateIdleCalendar);
        fetchMessages().then(updateIdleMessages);
        updateAlarmDetails(null);
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
        if (keywordHeadingEl) {
            keywordHeadingEl.textContent = '-';
        }
        
        // Stop participants polling when no alarm
        stopParticipantsPolling();
        hideParticipantsColumn();
        updateParticipantsDisplay(null);
        requestIdleViewFit();
    }

    requestKeywordResize();
}

if (keywordHeadingEl) {
    window.addEventListener('resize', requestKeywordResize);
    requestKeywordResize();
}

if (idleCalendarEl && typeof window.ResizeObserver === 'function') {
    const idleCalendarResizeObserver = new window.ResizeObserver(() => {
        requestIdleCalendarRender();
        requestIdleViewFit();
    });
    idleCalendarResizeObserver.observe(idleCalendarEl);
} else {
    window.addEventListener('resize', handleIdleCalendarWindowResize);
}

if (typeof window.ResizeObserver === 'function') {
    const dashboardViewFitObserver = new window.ResizeObserver(() => {
        requestIdleViewFit();
        requestAlarmViewFit();
    });
    if (appMainEl) {
        dashboardViewFitObserver.observe(appMainEl);
    }
    if (idleView) {
        dashboardViewFitObserver.observe(idleView);
    }
    if (alarmView) {
        dashboardViewFitObserver.observe(alarmView);
    }
} else {
    window.addEventListener('resize', () => {
        requestIdleViewFit();
        requestAlarmViewFit();
    });
}

window.addEventListener('resize', () => {
    requestIdleViewFit();
    requestAlarmViewFit();
});
requestIdleViewFit();
requestAlarmViewFit();

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

// ---------------------------------------------------------------------------
// SSE connection with connection status banner
// ---------------------------------------------------------------------------

/**
 * Create and manage the SSE connection with a connection status banner.
 * The banner is shown when the SSE connection is lost and reloads the page.
 */
(function initSSEConnection() {
    'use strict';

    // Create the connection banner dynamically
    var banner = document.createElement('div');
    banner.id = 'connection-banner';
    banner.textContent = '⚠ Verbindung unterbrochen – Seite wird neu geladen...';
    banner.style.display = 'none';
    document.body.appendChild(banner);

    var reloadTimeout = null;
    var heartbeatTimeout = null;
    var es = null;

    var HEARTBEAT_TIMEOUT_MS = 60000; // 60 seconds without any event
    var RELOAD_DELAY_MS = 10000;      // reload 10 seconds after banner shown

    function showBanner() {
        if (banner.style.display !== 'none') {
            return; // Already shown
        }
        banner.style.display = 'block';
        reloadTimeout = setTimeout(function () {
            window.location.reload();
        }, RELOAD_DELAY_MS);
    }

    function hideBanner() {
        banner.style.display = 'none';
        if (reloadTimeout) {
            clearTimeout(reloadTimeout);
            reloadTimeout = null;
        }
    }

    function resetHeartbeatTimer() {
        if (heartbeatTimeout) {
            clearTimeout(heartbeatTimeout);
        }
        heartbeatTimeout = setTimeout(function () {
            showBanner();
        }, HEARTBEAT_TIMEOUT_MS);
    }

    function connect() {
        if (typeof EventSource === 'undefined') {
            return; // SSE not supported
        }

        es = new EventSource('/api/stream');

        es.onopen = function () {
            hideBanner();
            resetHeartbeatTimer();
        };

        es.onmessage = function (event) {
            hideBanner();
            resetHeartbeatTimer();
            try {
                var data = JSON.parse(event.data);
                if (data && (data.type === 'alarm' || data.type === 'idle' || data.type === 'connected')) {
                    if (data.type === 'alarm' || data.type === 'idle') {
                        updateDashboard(data.type === 'alarm' ? data : { mode: 'idle', alarm: null });
                    }
                }
            } catch (e) {
                // Ignore parse errors
            }
        };

        es.onerror = function () {
            if (es.readyState === EventSource.CLOSED) {
                showBanner();
                if (heartbeatTimeout) {
                    clearTimeout(heartbeatTimeout);
                    heartbeatTimeout = null;
                }
            }
        };
    }

    connect();
})();
const participantsColumn = document.getElementById('participants-column');
const participantsList = document.getElementById('participants-list');
let currentIncidentNumber = null;
let participantsPollInterval = null;

function formatResponderName(firstName, lastName) {
    const lastInitial = lastName ? lastName.charAt(0).toUpperCase() + '.' : '';
    const firstInitial = firstName ? firstName.charAt(0).toUpperCase() + '.' : '';
    if (lastInitial && firstInitial) {
        return `${lastInitial}, ${firstInitial}`;
    }
    return lastInitial || firstInitial || '';
}

function createQualificationBadges(qualifications) {
    const badges = [];
    
    if (qualifications.agt) {
        badges.push('<span class="qualification-badge qualification-badge--agt" title="AGT (Atemschutzgeräteträger)"></span>');
    }
    
    if (qualifications.machinist) {
        badges.push('<span class="qualification-badge qualification-badge--machinist" title="Maschinist"></span>');
    }
    
    if (qualifications.paramedic) {
        badges.push('<span class="qualification-badge qualification-badge--paramedic" title="Sanitäter"></span>');
    }
    
    return badges.join('');
}

function createLeadershipBars(leadershipRole) {
    if (leadershipRole === 'groupLeader') {
        return '<div class="participant-leadership"><span class="leadership-bar"></span></div>';
    } else if (leadershipRole === 'platoonLeader') {
        return '<div class="participant-leadership"><span class="leadership-bar"></span><span class="leadership-bar"></span></div>';
    }
    return '';
}

function renderParticipant(participant) {
    const responder = participant.responder;
    const name = formatResponderName(responder.firstName, responder.lastName);
    const qualificationBadges = createQualificationBadges(responder.qualifications);
    const leadershipBars = createLeadershipBars(responder.leadershipRole);
    
    return `
        <div class="participant-item">
            <div class="participant-name">${name}</div>
            <div class="participant-meta">
                <div class="participant-qualifications">
                    ${qualificationBadges}
                </div>
                ${leadershipBars}
            </div>
        </div>
    `;
}

const MESSENGER_NOT_CONFIGURED = 'messenger_not_configured';

async function fetchParticipants(incidentNumber) {
    // Validate incident number
    if (!incidentNumber || typeof incidentNumber !== 'string') {
        console.error('Invalid incident number');
        return null;
    }
    
    try {
        const response = await fetch(`/api/alarm/participants/${encodeURIComponent(incidentNumber)}`);
        if (!response.ok) {
            if (response.status === 503) {
                // Messenger not configured
                return MESSENGER_NOT_CONFIGURED;
            }
            throw new Error('Failed to fetch participants');
        }
        const data = await response.json();
        return data.participants;
    } catch (error) {
        console.error('Error fetching participants:', error);
        return null;
    }
}

function updateParticipantsDisplay(participants) {
    if (!participantsList) return;
    
    if (!participants || participants.length === 0) {
        participantsList.innerHTML = '<p class="participants-message">Warte auf Rückmeldungen...</p>';
        requestAlarmViewFit();
        return;
    }
    
    const html = participants.map(renderParticipant).join('');
    participantsList.innerHTML = html;
    requestAlarmViewFit();
}

function showParticipantsColumn() {
    if (participantsColumn) {
        participantsColumn.classList.remove('hidden');
    }
    if (alarmLayout) {
        alarmLayout.classList.add('has-participants');
    }
    requestAlarmViewFit();
}

function hideParticipantsColumn() {
    if (participantsColumn) {
        participantsColumn.classList.add('hidden');
    }
    if (alarmLayout) {
        alarmLayout.classList.remove('has-participants');
    }
    requestAlarmViewFit();
}

function stopParticipantsPolling() {
    if (participantsPollInterval) {
        clearInterval(participantsPollInterval);
        participantsPollInterval = null;
    }
    currentIncidentNumber = null;
}

function startParticipantsPolling(incidentNumber) {
    stopParticipantsPolling();
    
    if (!incidentNumber) {
        hideParticipantsColumn();
        return;
    }
    
    currentIncidentNumber = incidentNumber;

    function handleParticipantsResponse(result) {
        if (result === MESSENGER_NOT_CONFIGURED) {
            // Messenger is not configured – hide the column and stop polling
            hideParticipantsColumn();
            stopParticipantsPolling();
            return;
        }
        showParticipantsColumn();
        updateParticipantsDisplay(result);
    }

    // Fetch immediately
    fetchParticipants(incidentNumber).then(handleParticipantsResponse);
    
    // Then poll every 10 seconds
    participantsPollInterval = setInterval(() => {
        if (currentIncidentNumber === incidentNumber) {
            fetchParticipants(incidentNumber).then(handleParticipantsResponse);
        }
    }, 10000);
}

// Clean up on page unload
window.addEventListener('beforeunload', stopParticipantsPolling);

// Hide bottom navigation in browser fullscreen mode (F11, Fullscreen API, or kiosk mode)
(function () {
    var kioskMediaQuery = window.matchMedia
        ? window.matchMedia('(display-mode: fullscreen)')
        : null;

    function updateFullscreen() {
        // Use a small tolerance (2 px) to account for sub-pixel rounding or minor OS
        // UI differences when the browser window occupies the full screen height.
        var isFullscreen =
            !!document.fullscreenElement ||
            !!document.webkitFullscreenElement ||
            window.outerHeight >= screen.height - 2 ||
            (kioskMediaQuery ? kioskMediaQuery.matches : false);
        document.body.classList.toggle('is-fullscreen', isFullscreen);
    }
    document.addEventListener('fullscreenchange', updateFullscreen);
    document.addEventListener('webkitfullscreenchange', updateFullscreen);
    window.addEventListener('resize', updateFullscreen);
    if (kioskMediaQuery && kioskMediaQuery.addEventListener) {
        kioskMediaQuery.addEventListener('change', updateFullscreen);
    }
    updateFullscreen();
}());
