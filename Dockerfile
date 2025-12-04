FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alarm_dashboard ./alarm_dashboard

# Create instance directory for persistence and set ownership
RUN mkdir -p /app/instance && chown -R appuser:appuser /app

# Switch to non-root user for security
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD curl --fail http://localhost:8000/health || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "alarm_dashboard.app:create_app()", "--workers", "2", "--threads", "4", "--worker-class", "gthread"]
