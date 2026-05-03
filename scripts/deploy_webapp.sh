#!/usr/bin/env bash
set -euo pipefail

# Deploy webapp frontend on the VM.
# Run this ON THE VM (not locally) after DNS points app.chatbot24.su to 51.250.91.143.

REPO_DIR="/opt/restobot"
WEBAPP_DIR="$REPO_DIR/frontend/webapp"

echo "=== Building frontend ==="
cd "$WEBAPP_DIR"
if ! command -v npm &> /dev/null; then
    echo "ERROR: npm not found. Install Node.js 20+ first."
    exit 1
fi
npm ci
npm run build

echo "=== Restarting Caddy ==="
cd "$REPO_DIR"
docker compose -f docker-compose.prod.yml --env-file .env.prod restart caddy

echo "=== Smoke checks ==="
sleep 2

# Check that SPA routes return 200 and contain root mount
for path in /demo/menu /demo/order; do
    status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost${path}")
    if [ "$status" != "200" ]; then
        echo "FAIL: localhost${path} returned ${status}"
        exit 1
    fi
    echo "OK: localhost${path} -> 200"
done

# Check API health
for path in /admin/health /widget/health; do
    status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost${path}")
    if [ "$status" != "200" ]; then
        echo "FAIL: localhost${path} returned ${status}"
        exit 1
    fi
    echo "OK: localhost${path} -> 200"
done

echo "=== WebApp deploy complete ==="
