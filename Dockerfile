FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

COPY --from=builder /opt/venv /opt/venv

COPY alarm_monitor ./alarm_monitor
COPY scripts ./scripts
COPY docker-entrypoint.sh /docker-entrypoint.sh

# Download Leaflet vendor assets (JS, CSS, marker images) for offline map rendering
RUN bash scripts/download-leaflet.sh \
    && chmod +x /docker-entrypoint.sh \
    && mkdir -p /app/instance \
    && chown -R appuser:appuser /app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD curl --fail http://localhost:8000/health || exit 1

# IMPORTANT: Use a single worker process to ensure in-process singletons (AlarmStore,
# SSE subscriber list, weather cache) are shared across all request threads.
# Multiple workers would each maintain independent state, causing SSE notifications
# to be lost and store reads to be inconsistent across worker processes.
# Operators may override ALARM_MONITOR_GUNICORN_WORKERS/THREADS if they know what
# they are doing (e.g. behind a sticky-session load balancer).
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD gunicorn \
    --bind 0.0.0.0:8000 \
    --workers "${ALARM_MONITOR_GUNICORN_WORKERS:-${ALARM_DASHBOARD_GUNICORN_WORKERS:-1}}" \
    --threads "${ALARM_MONITOR_GUNICORN_THREADS:-${ALARM_DASHBOARD_GUNICORN_THREADS:-8}}" \
    --worker-class gthread \
    "alarm_monitor.app:create_app()"
