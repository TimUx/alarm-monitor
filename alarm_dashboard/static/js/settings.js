/**
 * Settings page functionality
 */

(function() {
    'use strict';

    const form = document.getElementById('settings-form');
    const messageEl = document.getElementById('message');
    const cancelBtn = document.getElementById('cancel-btn');
    const submitBtn = form ? form.querySelector('button[type="submit"]') : null;

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
                document.getElementById('activation_groups').value = data.activation_groups || '';
                const calendarEl = document.getElementById('calendar_urls');
                if (calendarEl) { calendarEl.value = data.calendar_urls || ''; }
                const ntfyUrlEl = document.getElementById('ntfy_topic_url');
                if (ntfyUrlEl) { ntfyUrlEl.value = data.ntfy_topic_url || ''; }
                const ntfyIntervalEl = document.getElementById('ntfy_poll_interval');
                if (ntfyIntervalEl) { ntfyIntervalEl.value = data.ntfy_poll_interval || ''; }
                const msgTtlEl = document.getElementById('message_default_ttl_minutes');
                if (msgTtlEl) { msgTtlEl.value = data.message_default_ttl_minutes || ''; }
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
