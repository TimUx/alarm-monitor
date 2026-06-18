#!/bin/sh
set -e

# Bind-mounted ./instance may be owned by the host user; ensure appuser can write.
if [ -d /app/instance ]; then
    chown -R appuser:appuser /app/instance
fi

exec runuser -u appuser -- "$@"
