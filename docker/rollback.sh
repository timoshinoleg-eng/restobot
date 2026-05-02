#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"
ROLLBACK_FILE=".rollback.env"

if [[ ! -f "$ROLLBACK_FILE" ]]; then
    echo "!!! No rollback snapshot found. Manual recovery required."
    exit 1
fi

echo ">>> Restoring previous image tags..."
while IFS= read -r line; do
    key="${line%%=*}"
    sed -i "s|^${key}=.*|${line}|" "$ENV_FILE"
done < "$ROLLBACK_FILE"

echo ">>> Pulling previous images (if missing)..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" pull admin public

echo ">>> Re-deploying previous version..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --remove-orphans

echo ">>> Rollback complete."
