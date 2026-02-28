#!/bin/bash
set -e

echo "=== GradeAI Backend Entrypoint ==="

# --- Run Alembic migrations ---
if [ "$SKIP_MIGRATIONS" != "true" ]; then
    echo "Running database migrations..."
    # Wait briefly for DB to be fully ready (healthcheck covers most of it,
    # but connection pool init can race on first boot)
    for i in 1 2 3 4 5; do
        if alembic upgrade head 2>&1; then
            echo "Migrations completed successfully."
            break
        fi
        echo "Migration attempt $i failed, retrying in 3s..."
        sleep 3
    done
fi

# --- Create default S3 bucket if using MinIO ---
if [ -n "$S3_ENDPOINT_URL" ] && command -v curl &> /dev/null; then
    echo "Ensuring S3 bucket '${S3_BUCKET_NAME:-gradeai-uploads}' exists..."
    curl -sf -o /dev/null -X PUT \
        "${S3_ENDPOINT_URL}/${S3_BUCKET_NAME:-gradeai-uploads}" 2>/dev/null || true
fi

echo "Starting: $@"
exec "$@"
