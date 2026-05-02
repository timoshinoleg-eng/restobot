#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"

ADMIN_TAG="${1:-}"
PUBLIC_TAG="${2:-}"

if [[ -z "$ADMIN_TAG" || -z "$PUBLIC_TAG" ]]; then
    echo "Usage: $0 <admin-image> <public-image>"
    echo "Example: $0 cr.yandex/xxx/restobot-admin:v1.2.3 cr.yandex/xxx/restobot-public:v1.2.3"
    exit 1
fi

# ─── Ensure keys exist before sed ───────────────────────────────────
for key in ADMIN_IMAGE PUBLIC_IMAGE; do
    if ! grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        echo "${key}=" >> "$ENV_FILE"
    fi
done

# ─── Save current tags for rollback ─────────────────────────────────
> .rollback.env
for key in ADMIN_IMAGE PUBLIC_IMAGE; do
    grep "^${key}=" "$ENV_FILE" >> .rollback.env || true
done

# ─── Update tags ────────────────────────────────────────────────────
sed -i "s|^ADMIN_IMAGE=.*|ADMIN_IMAGE=${ADMIN_TAG}|" "$ENV_FILE"
sed -i "s|^PUBLIC_IMAGE=.*|PUBLIC_IMAGE=${PUBLIC_TAG}|" "$ENV_FILE"

# ─── Pull only mutable services (skip caddy pinned image) ───────────
echo ">>> Pulling images..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" pull admin public

echo ">>> Starting containers..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --remove-orphans

# ─── Wait for health (up to ~90s) ───────────────────────────────────
echo ">>> Waiting for healthchecks..."

is_healthy() {
    local svc=$1
    local status
    status=$(docker inspect --format='{{.State.Health.Status}}' "restobot-${svc}-1" 2>/dev/null || true)
    [[ "$status" == "healthy" ]]
}

MAX_WAIT=90
WAITED=0
while (( WAITED < MAX_WAIT )); do
    if is_healthy admin && is_healthy public; then
        echo ">>> Verifying proxy ingress through Caddy..."
        sleep 2
        if curl -fsS http://localhost/admin/health >/dev/null 2>&1 && \
           curl -fsS http://localhost/widget/health >/dev/null 2>&1; then
            echo ">>> Deploy successful (healthy after ${WAITED}s, proxy ingress OK)."
            exit 0
        fi
        echo "!!! Proxy ingress check failed (Caddy or rewrite issue)."
        break
    fi
    sleep 5
    WAITED=$((WAITED + 5))
done

echo "!!! Deploy FAILED. Rolling back..."
./rollback.sh
exit 1
