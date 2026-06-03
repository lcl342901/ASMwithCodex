#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICE_ROOT="${AAO_SERVICE_ROOT:-/Users/chenglin/aao-simulator-service}"
FRONTEND_DIR="$SERVICE_ROOT/frontend"
BACKEND_HEALTH_URL="${AAO_BACKEND_HEALTH_URL:-http://127.0.0.1:8000/api/health}"
FRONTEND_BASE_URL="${AAO_FRONTEND_BASE_URL:-http://127.0.0.1:4173}"

cd "$PROJECT_ROOT"

echo "Checking frontend module syntax..."
perl -0ne 'print "$1\n" if /<script type="module">\n([\s\S]*?)\n\s*<\/script>/m' frontend/3d-process/wwtp-3d.html | node --check --input-type=module -
node --check frontend/asm-platform/app.js
node --check frontend/3d-process/wwtp-animation.js
node --check frontend/3d-process/wwtp-simulation-mapping.js
node --check frontend/3d-process/wwtp-visual-config.js
node --check frontend/3d-process/wwtp-scene-utils.js

echo "Checking backend tests..."
if [[ -x "$SERVICE_ROOT/.venv/bin/python" ]]; then
  "$SERVICE_ROOT/.venv/bin/python" -m unittest backend.test_model
else
  python3 -m unittest backend.test_model
fi

echo "Checking expected local frontend files..."
for file in \
  frontend/asm-platform/index.html \
  frontend/asm-platform/app.js \
  frontend/asm-platform/styles.css \
  frontend/asm-platform/sample-data.csv \
  frontend/3d-process/wwtp-3d.html \
  frontend/3d-process/underground-line-3d.html \
  frontend/3d-process/wwtp-animation.js \
  frontend/3d-process/wwtp-simulation-mapping.js \
  frontend/3d-process/wwtp-visual-config.js \
  frontend/3d-process/wwtp-scene-utils.js; do
  test -f "$PROJECT_ROOT/$file"
done

if [[ -d "$FRONTEND_DIR" ]]; then
  echo "Checking service frontend copy..."
  for file in \
    asm-platform/index.html \
    asm-platform/app.js \
    asm-platform/styles.css \
    asm-platform/sample-data.csv \
    3d-process/wwtp-3d.html \
    3d-process/underground-line-3d.html \
    3d-process/wwtp-animation.js \
    3d-process/wwtp-simulation-mapping.js \
    3d-process/wwtp-visual-config.js \
    3d-process/wwtp-scene-utils.js; do
    test -f "$FRONTEND_DIR/$file"
  done
fi

echo "Checking running services..."
curl -fsS "$BACKEND_HEALTH_URL" >/dev/null
curl -fsSI "$FRONTEND_BASE_URL/asm-platform/index.html" >/dev/null
curl -fsSI "$FRONTEND_BASE_URL/3d-process/wwtp-3d.html" >/dev/null
curl -fsSI "$FRONTEND_BASE_URL/3d-process/underground-line-3d.html" >/dev/null
curl -fsSI "$FRONTEND_BASE_URL/3d-process/wwtp-animation.js" >/dev/null
curl -fsSI "$FRONTEND_BASE_URL/3d-process/wwtp-simulation-mapping.js" >/dev/null
curl -fsSI "$FRONTEND_BASE_URL/3d-process/wwtp-visual-config.js" >/dev/null
curl -fsSI "$FRONTEND_BASE_URL/3d-process/wwtp-scene-utils.js" >/dev/null

echo "P7 engineering verification passed."
