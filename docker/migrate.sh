#!/usr/bin/env bash
# Run Alembic migrations against the production database.
# Uses the current ADMIN_IMAGE from .env.prod.
set -euo pipefail

cd "$(dirname "$0")"

ENV_FILE=".env.prod"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "!!! $ENV_FILE not found."
    exit 1
fi

ADMIN_IMAGE=$(grep "^ADMIN_IMAGE=" "$ENV_FILE" | cut -d'=' -f2-)

if [[ -z "$ADMIN_IMAGE" ]]; then
    echo "!!! ADMIN_IMAGE is not set in $ENV_FILE"
    exit 1
fi

echo ">>> Pulling admin image (if missing)..."
docker pull "$ADMIN_IMAGE" >/dev/null 2>&1 || true

echo ">>> Running alembic upgrade head..."
docker run --rm --env-file "$ENV_FILE" "$ADMIN_IMAGE" alembic upgrade head

echo ">>> Migrations complete."
