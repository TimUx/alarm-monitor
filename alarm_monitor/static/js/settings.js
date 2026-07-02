/**
 * Settings page functionality
 */

(function() {
    'use strict';

    const form = document.getElementById('settings-form');
    const messageEl = document.getElementById('message');
    const cancelBtn = document.getElementById('cancel-btn');
    const submitBtn = form ? form.querySelector('button[type="submit"]') : null;
    const hdmiEnabledEl = document.getElementById('hdmi_cec_enabled');
    const hdmiFieldsWrap = document.querySelector('.hdmi-cec-fields');
    const hdmiStatusEl = document.getElementById('hdmi-cec-status');
    const hdmiSchedulesEl = document.getElementById('hdmi-cec-schedules');
    const hdmiAddScheduleBtn = document.getElementById('hdmi-cec-add-schedule');

    const WEEKDAYS = [
        { value: 0, label: 'Montag' },
        { value: 1, label: 'Dienstag' },
        { value: 2, label: 'Mittwoch' },
        { value: 3, label: 'Donnerstag' },
        { value: 4, label: 'Freitag' },
        { value: 5, label: 'Samstag' },
        { value: 6, label: 'Sonntag' },
    ];

    let hdmiSchedules = [];

    function updateHdmiFieldsVisibility() {
        if (!hdmiFieldsWrap || !hdmiEnabledEl) { return; }
        hdmiFieldsWrap.style.display = hdmiEnabledEl.checked ? '' : 'none';
    }

    function updateHdmiStatus(data) {
        if (!hdmiStatusEl) { return; }
        const enabled = Boolean(data.hdmi_cec_enabled);
        const available = Boolean(data.hdmi_cec_client_available);
        const path = data.hdmi_cec_client_path || '/usr/bin/cec-client';

        if (!enabled) {
            hdmiStatusEl.textContent = 'HDMI-CEC ist deaktiviert.';
            hdmiStatusEl.className = 'hdmi-cec-status';
            return;
        }

        if (available) {
            hdmiStatusEl.textContent = 'cec-client verfügbar: ' + path;
            hdmiStatusEl.className = 'hdmi-cec-status hdmi-cec-status--ok';
        } else {
            hdmiStatusEl.textContent =
                'cec-client nicht gefunden oder nicht ausführbar: ' + path +
                ' – Paket cec-utils/libcec auf dem Host installieren.';
            hdmiStatusEl.className = 'hdmi-cec-status hdmi-cec-status--warn';
        }
    }

    function createScheduleRow(schedule, index) {
        const row = document.createElement('div');
        row.className = 'hdmi-cec-schedule-row';
        row.dataset.index = String(index);

        const weekdaySelect = document.createElement('select');
        weekdaySelect.className = 'hdmi-cec-schedule-weekday';
        WEEKDAYS.forEach((day) => {
            const option = document.createElement('option');
            option.value = String(day.value);
            option.textContent = day.label;
            if (Number(schedule.weekday) === day.value) {
                option.selected = true;
            }
            weekdaySelect.appendChild(option);
        });

        const startInput = document.createElement('input');
        startInput.type = 'time';
        startInput.className = 'hdmi-cec-schedule-start';
        startInput.value = schedule.start_time || '18:45';
        startInput.required = true;

        const endInput = document.createElement('input');
        endInput.type = 'time';
        endInput.className = 'hdmi-cec-schedule-end';
        endInput.value = schedule.end_time || '21:30';
        endInput.required = true;

        const labelInput = document.createElement('input');
        labelInput.type = 'text';
        labelInput.className = 'hdmi-cec-schedule-label';
        labelInput.placeholder = 'z.B. Übungsdienst';
        labelInput.value = schedule.label || '';

        const enabledLabel = document.createElement('label');
        enabledLabel.className = 'form-checkbox';
        const enabledInput = document.createElement('input');
        enabledInput.type = 'checkbox';
        enabledInput.className = 'hdmi-cec-schedule-enabled';
        enabledInput.checked = schedule.enabled !== false;
        const enabledText = document.createElement('span');
        enabledText.textContent = 'Aktiv';
        enabledLabel.appendChild(enabledInput);
        enabledLabel.appendChild(enabledText);

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'btn btn-secondary hdmi-cec-schedule-remove';
        removeBtn.textContent = 'Entfernen';
        removeBtn.addEventListener('click', () => {
            hdmiSchedules.splice(index, 1);
            renderHdmiSchedules();
        });

        row.appendChild(weekdaySelect);
        row.appendChild(startInput);
        row.appendChild(endInput);
        row.appendChild(labelInput);
        row.appendChild(enabledLabel);
        row.appendChild(removeBtn);
        return row;
    }

    function renderHdmiSchedules() {
        if (!hdmiSchedulesEl) { return; }
        hdmiSchedulesEl.innerHTML = '';
        hdmiSchedules.forEach((schedule, index) => {
            hdmiSchedulesEl.appendChild(createScheduleRow(schedule, index));
        });
    }

    function collectHdmiSchedules() {
        if (!hdmiSchedulesEl) { return []; }
        const rows = hdmiSchedulesEl.querySelectorAll('.hdmi-cec-schedule-row');
        const schedules = [];
        rows.forEach((row) => {
            const weekday = row.querySelector('.hdmi-cec-schedule-weekday');
            const start = row.querySelector('.hdmi-cec-schedule-start');
            const end = row.querySelector('.hdmi-cec-schedule-end');
            const label = row.querySelector('.hdmi-cec-schedule-label');
            const enabled = row.querySelector('.hdmi-cec-schedule-enabled');
            if (!weekday || !start || !end) { return; }
            schedules.push({
                enabled: enabled ? enabled.checked : true,
                weekday: Number(weekday.value),
                start_time: start.value,
                end_time: end.value,
                label: label ? label.value.trim() : '',
            });
        });
        return schedules;
    }

    // Load current settings on page load
    function loadSettings() {
        fetch('/api/settings')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to load settings');
                }
                return response.json();
            })
            .then(data => {
                document.getElementById('fire_department_name').value = data.fire_department_name || '';
                document.getElementById('default_latitude').value = data.default_latitude || '';
                document.getElementById('default_longitude').value = data.default_longitude || '';
                document.getElementById('default_location_name').value = data.default_location_name || '';
                const showLastAlarmEl = document.getElementById('show_last_alarm');
                if (showLastAlarmEl) {
                    showLastAlarmEl.checked = data.show_last_alarm !== false;
                }
                const mockWarningsEl = document.getElementById('dwd_warnings_mock');
                if (mockWarningsEl) {
                    mockWarningsEl.checked = Boolean(data.dwd_warnings_mock);
                }
                const warningsMinLevelEl = document.getElementById('warnings_min_level');
                if (warningsMinLevelEl) {
                    warningsMinLevelEl.value = String(data.warnings_min_level || 3);
                }
                document.getElementById('activation_groups').value = data.activation_groups || '';
                const calendarEl = document.getElementById('calendar_urls');
                if (calendarEl) { calendarEl.value = data.calendar_urls || ''; }
                const ntfyUrlEl = document.getElementById('ntfy_topic_url');
                if (ntfyUrlEl) { ntfyUrlEl.value = data.ntfy_topic_url || ''; }
                const ntfyIntervalEl = document.getElementById('ntfy_poll_interval');
                if (ntfyIntervalEl) { ntfyIntervalEl.value = data.ntfy_poll_interval || ''; }
                const msgTtlEl = document.getElementById('message_default_ttl_minutes');
                if (msgTtlEl) { msgTtlEl.value = data.message_default_ttl_minutes || ''; }

                const hdmiEnabled = document.getElementById('hdmi_cec_enabled');
                if (hdmiEnabled) {
                    hdmiEnabled.checked = Boolean(data.hdmi_cec_enabled);
                }
                const hdmiClientPath = document.getElementById('hdmi_cec_client_path');
                if (hdmiClientPath) {
                    hdmiClientPath.value = data.hdmi_cec_client_path || '/usr/bin/cec-client';
                }
                const hdmiDeviceAddress = document.getElementById('hdmi_cec_device_address');
                if (hdmiDeviceAddress) {
                    hdmiDeviceAddress.value = data.hdmi_cec_device_address ?? 0;
                }
                const hdmiIdleMinutes = document.getElementById('hdmi_cec_idle_standby_minutes');
                if (hdmiIdleMinutes) {
                    hdmiIdleMinutes.value = data.hdmi_cec_idle_standby_minutes || 30;
                }
                const hdmiWakeOnAlarm = document.getElementById('hdmi_cec_wake_on_alarm');
                if (hdmiWakeOnAlarm) {
                    hdmiWakeOnAlarm.checked = data.hdmi_cec_wake_on_alarm !== false;
                }
                const hdmiStandbyOnIdle = document.getElementById('hdmi_cec_standby_on_idle');
                if (hdmiStandbyOnIdle) {
                    hdmiStandbyOnIdle.checked = data.hdmi_cec_standby_on_idle !== false;
                }

                hdmiSchedules = Array.isArray(data.hdmi_cec_schedules) ? data.hdmi_cec_schedules : [];
                renderHdmiSchedules();
                updateHdmiFieldsVisibility();
                updateHdmiStatus(data);
            })
            .catch(error => {
                console.error('Error loading settings:', error);
                showMessage('Fehler beim Laden der Einstellungen', 'error');
            });
    }

    // Save settings
    function saveSettings(event) {
        event.preventDefault();

        const formData = new FormData(form);
        const settings = {
            fire_department_name: formData.get('fire_department_name'),
            default_latitude: formData.get('default_latitude'),
            default_longitude: formData.get('default_longitude'),
            default_location_name: formData.get('default_location_name'),
            activation_groups: formData.get('activation_groups'),
            calendar_urls: formData.get('calendar_urls') || '',
            ntfy_topic_url: formData.get('ntfy_topic_url') || '',
            ntfy_poll_interval: formData.get('ntfy_poll_interval') || '',
            message_default_ttl_minutes: formData.get('message_default_ttl_minutes') || '',
            dwd_warnings_mock: formData.get('dwd_warnings_mock') === 'on',
            show_last_alarm: formData.get('show_last_alarm') === 'on',
            warnings_min_level: formData.get('warnings_min_level') || '3',
            hdmi_cec_enabled: formData.get('hdmi_cec_enabled') === 'on',
            hdmi_cec_client_path: formData.get('hdmi_cec_client_path') || '/usr/bin/cec-client',
            hdmi_cec_device_address: formData.get('hdmi_cec_device_address') || '0',
            hdmi_cec_idle_standby_minutes: formData.get('hdmi_cec_idle_standby_minutes') || '30',
            hdmi_cec_wake_on_alarm: formData.get('hdmi_cec_wake_on_alarm') === 'on',
            hdmi_cec_standby_on_idle: formData.get('hdmi_cec_standby_on_idle') === 'on',
            hdmi_cec_schedules: collectHdmiSchedules(),
        };
        const password = formData.get('settings_password') || '';

        // Client-side validation
        if (!settings.fire_department_name || settings.fire_department_name.trim() === '') {
            showMessage('Feuerwehr-Name ist erforderlich', 'error', false);
            return;
        }

        // Validate coordinates if provided
        if (settings.default_latitude || settings.default_longitude) {
            const lat = parseFloat(settings.default_latitude);
            const lon = parseFloat(settings.default_longitude);

            if (settings.default_latitude && isNaN(lat)) {
                showMessage('Breitengrad muss eine Zahl sein', 'error', false);
                return;
            }

            if (settings.default_longitude && isNaN(lon)) {
                showMessage('Längengrad muss eine Zahl sein', 'error', false);
                return;
            }

            // Check if both are provided
            if ((settings.default_latitude && !settings.default_longitude) || 
                (!settings.default_latitude && settings.default_longitude)) {
                showMessage('Bitte beide Koordinaten angeben oder beide leer lassen', 'error', false);
                return;
            }

            // Validate ranges
            if (settings.default_latitude && (lat < -90 || lat > 90)) {
                showMessage('Breitengrad muss zwischen -90 und 90 liegen', 'error', false);
                return;
            }

            if (settings.default_longitude && (lon < -180 || lon > 180)) {
                showMessage('Längengrad muss zwischen -180 und 180 liegen', 'error', false);
                return;
            }
        }

        if (settings.hdmi_cec_enabled) {
            const idleMinutes = parseInt(settings.hdmi_cec_idle_standby_minutes, 10);
            if (isNaN(idleMinutes) || idleMinutes < 1) {
                showMessage('HDMI Standby Idle-Zeit muss mindestens 1 Minute sein', 'error', false);
                return;
            }
            const deviceAddress = parseInt(settings.hdmi_cec_device_address, 10);
            if (isNaN(deviceAddress) || deviceAddress < 0 || deviceAddress > 15) {
                showMessage('HDMI CEC-Geräteadresse muss zwischen 0 und 15 liegen', 'error', false);
                return;
            }
            for (const schedule of settings.hdmi_cec_schedules) {
                if (!schedule.start_time || !schedule.end_time) {
                    showMessage('Bitte Start- und Endzeit für alle HDMI-Zeitfenster angeben', 'error', false);
                    return;
                }
            }
        }

        if (submitBtn) { submitBtn.disabled = true; }

        fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Settings-Password': password,
                'X-CSRF-Token': document.querySelector('meta[name="csrf-token"]')
                    ? document.querySelector('meta[name="csrf-token"]').getAttribute('content')
                    : '',
            },
            body: JSON.stringify(settings),
        })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        throw new Error(data.error || 'Failed to save settings');
                    });
                }
                return response.json();
            })
            .then(data => {
                if (submitBtn) { submitBtn.disabled = false; }
                showMessage('Gespeichert ✓', 'success', true);
                // Reload after a short delay to show updated header
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            })
            .catch(error => {
                if (submitBtn) { submitBtn.disabled = false; }
                console.error('Error saving settings:', error);
                showMessage('Fehler beim Speichern: ' + error.message, 'error', false);
            });
    }

    // Show message
    function showMessage(text, type, autoDismiss) {
        messageEl.textContent = '';
        messageEl.className = 'message message--' + type;
        messageEl.style.display = 'block';

        const span = document.createElement('span');
        span.textContent = text;
        messageEl.appendChild(span);

        if (type === 'error' && !autoDismiss) {
            const retryBtn = document.createElement('button');
            retryBtn.type = 'button';
            retryBtn.textContent = 'Erneut versuchen';
            retryBtn.className = 'message__retry-btn';
            retryBtn.addEventListener('click', () => {
                messageEl.style.display = 'none';
                form.dispatchEvent(new Event('submit'));
            });
            messageEl.appendChild(retryBtn);
        }

        if (autoDismiss) {
            setTimeout(() => {
                messageEl.style.display = 'none';
            }, 3000);
        }
    }

    // Cancel and go back
    function cancel() {
        window.location.href = '/';
    }

    // Event listeners
    form.addEventListener('submit', saveSettings);
    cancelBtn.addEventListener('click', cancel);
    if (hdmiEnabledEl) {
        hdmiEnabledEl.addEventListener('change', updateHdmiFieldsVisibility);
    }
    if (hdmiAddScheduleBtn) {
        hdmiAddScheduleBtn.addEventListener('click', () => {
            hdmiSchedules.push({
                enabled: true,
                weekday: 1,
                start_time: '18:45',
                end_time: '21:30',
                label: 'Übungsdienst',
            });
            renderHdmiSchedules();
        });
    }

    // Load settings on page load
    loadSettings();
})();

// ---------------------------------------------------------------------------
// Logo upload
// ---------------------------------------------------------------------------

(function () {
    'use strict';

    const fileInput = document.getElementById('logo-file-input');
    const fileNameEl = document.getElementById('logo-file-name');
    const uploadBtn = document.getElementById('logo-upload-btn');
    const resetBtn = document.getElementById('logo-reset-btn');
    const previewImg = document.getElementById('logo-preview');
    const messageEl = document.getElementById('logo-message');

    if (!fileInput || !uploadBtn || !resetBtn) { return; }

    function getPassword() {
        const pwField = document.getElementById('settings_password');
        return pwField ? pwField.value : '';
    }

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    function showMessage(text, type, autoDismiss) {
        messageEl.textContent = text;
        messageEl.className = 'message message--' + type;
        messageEl.style.display = 'block';
        if (autoDismiss) {
            setTimeout(() => { messageEl.style.display = 'none'; }, 3000);
        }
    }

    fileInput.addEventListener('change', function () {
        fileNameEl.textContent = fileInput.files.length > 0
            ? fileInput.files[0].name
            : 'Keine Datei ausgewählt';
    });

    uploadBtn.addEventListener('click', function () {
        const password = getPassword();
        if (!password) {
            showMessage('Bitte zuerst das Einstellungs-Passwort eingeben.', 'error', false);
            return;
        }
        if (!fileInput.files || fileInput.files.length === 0) {
            showMessage('Bitte eine Bilddatei auswählen.', 'error', false);
            return;
        }

        const formData = new FormData();
        formData.append('logo', fileInput.files[0]);

        uploadBtn.disabled = true;

        fetch('/api/settings/logo', {
            method: 'POST',
            headers: {
                'X-Settings-Password': password,
                'X-CSRF-Token': getCsrfToken(),
            },
            body: formData,
        })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        throw new Error(data.error || 'Upload fehlgeschlagen');
                    });
                }
                return response.json();
            })
            .then(() => {
                uploadBtn.disabled = false;
                showMessage('Logo erfolgreich hochgeladen ✓', 'success', true);
                // Refresh the preview by appending a timestamp to bust the cache.
                previewImg.src = '/api/logo?t=' + Date.now();
                fileInput.value = '';
                fileNameEl.textContent = 'Keine Datei ausgewählt';
            })
            .catch(error => {
                uploadBtn.disabled = false;
                showMessage('Fehler: ' + error.message, 'error', false);
            });
    });

    resetBtn.addEventListener('click', function () {
        const password = getPassword();
        if (!password) {
            showMessage('Bitte zuerst das Einstellungs-Passwort eingeben.', 'error', false);
            return;
        }

        resetBtn.disabled = true;

        fetch('/api/settings/logo', {
            method: 'DELETE',
            headers: {
                'X-Settings-Password': password,
                'X-CSRF-Token': getCsrfToken(),
            },
        })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(data => {
                        throw new Error(data.error || 'Zurücksetzen fehlgeschlagen');
                    });
                }
                return response.json();
            })
            .then(() => {
                resetBtn.disabled = false;
                showMessage('Standard-Logo wiederhergestellt ✓', 'success', true);
                previewImg.src = '/api/logo?t=' + Date.now();
            })
            .catch(error => {
                resetBtn.disabled = false;
                showMessage('Fehler: ' + error.message, 'error', false);
            });
    });
}());

// Hide bottom navigation in browser fullscreen mode (F11 or Fullscreen API)
(function () {
    function updateFullscreen() {
        const isFullscreen = !!document.fullscreenElement ||
            !!document.webkitFullscreenElement ||
            window.outerHeight === screen.height;
        document.body.classList.toggle('is-fullscreen', isFullscreen);
    }
    document.addEventListener('fullscreenchange', updateFullscreen);
    document.addEventListener('webkitfullscreenchange', updateFullscreen);
    window.addEventListener('resize', updateFullscreen);
    updateFullscreen();
}());
