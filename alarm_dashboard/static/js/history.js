/**
 * History page – client-side loading with pagination.
 */

(function () {
    'use strict';

    var PAGE_SIZE = 50;
    var currentOffset = 0;
    var loading = false;

    var tbody = document.getElementById('history-tbody');
    var emptyMsg = document.getElementById('history-empty');
    var loadMoreWrap = document.getElementById('load-more-wrap');
    var loadMoreBtn = document.getElementById('load-more-btn');

    function formatDate(isoString) {
        if (!isoString) { return '–'; }
        try {
            var d = new Date(isoString);
            var day = String(d.getDate()).padStart(2, '0');
            var month = String(d.getMonth() + 1).padStart(2, '0');
            var year = d.getFullYear();
            return day + '.' + month + '.' + year;
        } catch (e) {
            return '–';
        }
    }

    function formatTime(isoString) {
        if (!isoString) { return '–'; }
        try {
            var d = new Date(isoString);
            var hours = String(d.getHours()).padStart(2, '0');
            var minutes = String(d.getMinutes()).padStart(2, '0');
            return hours + ':' + minutes;
        } catch (e) {
            return '–';
        }
    }

    function escapeHtml(str) {
        if (!str) { return ''; }
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function renderEntries(entries) {
        entries.forEach(function (entry) {
            var ts = entry.timestamp || entry.received_at;
            var displayDate = formatDate(ts);
            var displayTime = formatTime(ts);

            var vehicles = entry.aao_groups;
            var vehiclesText = '-';
            if (vehicles) {
                if (Array.isArray(vehicles)) {
                    vehiclesText = vehicles.join(', ') || '-';
                } else {
                    vehiclesText = String(vehicles);
                }
            }

            var descHtml = '';
            if (entry.description) {
                descHtml += '<div class="history-description">' + escapeHtml(entry.description) + '</div>';
            } else {
                descHtml += '<div class="history-description">-</div>';
            }
            if (entry.remark) {
                descHtml += '<div class="history-remark">' + escapeHtml(entry.remark) + '</div>';
            }

            var tr = document.createElement('tr');
            tr.innerHTML =
                '<td data-label="Datum">' + escapeHtml(displayDate) + '</td>' +
                '<td data-label="Uhrzeit">' + escapeHtml(displayTime) + '</td>' +
                '<td data-label="Stichwort">' + escapeHtml(entry.keyword || '-') + '</td>' +
                '<td data-label="Ort">' + escapeHtml(entry.location || '-') + '</td>' +
                '<td data-label="Beschreibung">' + descHtml + '</td>' +
                '<td data-label="Alarmierte Fahrzeuge">' + escapeHtml(vehiclesText) + '</td>';
            tbody.appendChild(tr);
        });
    }

    function loadPage() {
        if (loading) { return; }
        loading = true;
        if (loadMoreBtn) { loadMoreBtn.disabled = true; }

        fetch('/api/history?limit=' + PAGE_SIZE + '&offset=' + currentOffset)
            .then(function (response) {
                if (!response.ok) { throw new Error('HTTP ' + response.status); }
                return response.json();
            })
            .then(function (data) {
                var entries = data.history || [];
                renderEntries(entries);
                currentOffset += entries.length;

                if (currentOffset === 0 && entries.length === 0) {
                    if (emptyMsg) { emptyMsg.style.display = ''; }
                }

                if (entries.length < PAGE_SIZE) {
                    if (loadMoreWrap) { loadMoreWrap.style.display = 'none'; }
                } else {
                    if (loadMoreWrap) { loadMoreWrap.style.display = ''; }
                    if (loadMoreBtn) { loadMoreBtn.disabled = false; }
                }

                loading = false;
            })
            .catch(function (err) {
                console.error('Error loading history:', err);
                loading = false;
                if (loadMoreBtn) { loadMoreBtn.disabled = false; }
            });
    }

    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', loadPage);
    }

    loadPage();
})();
