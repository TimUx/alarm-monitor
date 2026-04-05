#!/usr/bin/env bash
# Download Leaflet 1.9.4 assets for offline use.
# Run this script once after cloning the repository.

set -euo pipefail

LEAFLET_VERSION="1.9.4"
BASE_URL="https://unpkg.com/leaflet@${LEAFLET_VERSION}/dist"
DEST="alarm_dashboard/static/vendor/leaflet"

mkdir -p "${DEST}/images"

echo "Downloading Leaflet ${LEAFLET_VERSION}..."
curl -fsSL "${BASE_URL}/leaflet.css" -o "${DEST}/leaflet.css"
curl -fsSL "${BASE_URL}/leaflet.js" -o "${DEST}/leaflet.js"

# Download marker images
for img in marker-icon.png marker-icon-2x.png marker-shadow.png; do
    curl -fsSL "${BASE_URL}/images/${img}" -o "${DEST}/images/${img}"
done

echo "Leaflet ${LEAFLET_VERSION} downloaded to ${DEST}"
