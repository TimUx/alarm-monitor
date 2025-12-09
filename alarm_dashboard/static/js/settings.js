/**
 * Settings page functionality
 */

(function() {
    'use strict';

    const form = document.getElementById('settings-form');
    const messageEl = document.getElementById('message');
    const cancelBtn = document.getElementById('cancel-btn');

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
        };

        fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
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
                showMessage('Einstellungen erfolgreich gespeichert', 'success');
                // Reload after a short delay to show updated header
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            })
            .catch(error => {
                console.error('Error saving settings:', error);
                showMessage('Fehler beim Speichern: ' + error.message, 'error');
            });
    }

    // Show message
    function showMessage(text, type) {
        messageEl.textContent = text;
        messageEl.className = 'message message--' + type;
        messageEl.style.display = 'block';

        if (type === 'success') {
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
