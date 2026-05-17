#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVICE_ROOT="${AAO_SERVICE_ROOT:-/Users/chenglin/aao-simulator-service}"
LAUNCH_AGENT_DIR="/Users/chenglin/Library/LaunchAgents"
LAUNCH_AGENT_NAME="com.asmwithcodex.backend.plist"
LAUNCH_AGENT_SOURCE="$PROJECT_ROOT/deploy/$LAUNCH_AGENT_NAME"
LAUNCH_AGENT_TARGET="$LAUNCH_AGENT_DIR/$LAUNCH_AGENT_NAME"
SERVICE_LABEL="com.asmwithcodex.backend"
FRONTEND_DIR="$SERVICE_ROOT/frontend"
FRONTEND_LAUNCH_AGENT_NAME="com.asmwithcodex.frontend.plist"
FRONTEND_LAUNCH_AGENT_SOURCE="$PROJECT_ROOT/deploy/$FRONTEND_LAUNCH_AGENT_NAME"
FRONTEND_LAUNCH_AGENT_TARGET="$LAUNCH_AGENT_DIR/$FRONTEND_LAUNCH_AGENT_NAME"
FRONTEND_SERVICE_LABEL="com.asmwithcodex.frontend"
USER_ID="$(id -u)"
SERVICE_DOMAIN="gui/$USER_ID"
HEALTH_URL="http://127.0.0.1:8000/api/health"
FRONTEND_URL="http://127.0.0.1:4173/index.html"

echo "Project: $PROJECT_ROOT"
echo "Service: $SERVICE_ROOT"

if [[ ! -f "$LAUNCH_AGENT_SOURCE" ]]; then
  echo "Missing LaunchAgent template: $LAUNCH_AGENT_SOURCE" >&2
  exit 1
fi
if [[ ! -f "$FRONTEND_LAUNCH_AGENT_SOURCE" ]]; then
  echo "Missing frontend LaunchAgent template: $FRONTEND_LAUNCH_AGENT_SOURCE" >&2
  exit 1
fi

mkdir -p "$SERVICE_ROOT" "$FRONTEND_DIR" "$LAUNCH_AGENT_DIR"

echo "Syncing backend code..."
rsync -a --delete "$PROJECT_ROOT/backend/" "$SERVICE_ROOT/backend/"

echo "Syncing frontend files..."
rsync -a --delete \
  "$PROJECT_ROOT/index.html" \
  "$PROJECT_ROOT/app.js" \
  "$PROJECT_ROOT/styles.css" \
  "$PROJECT_ROOT/sample-data.csv" \
  "$FRONTEND_DIR/"

if [[ ! -x "$SERVICE_ROOT/.venv/bin/python" ]]; then
  echo "Creating service virtual environment..."
  python3 -m venv "$SERVICE_ROOT/.venv"
fi

echo "Installing backend dependencies..."
"$SERVICE_ROOT/.venv/bin/pip" install -r "$SERVICE_ROOT/backend/requirements.txt"

echo "Installing LaunchAgent..."
cp "$LAUNCH_AGENT_SOURCE" "$LAUNCH_AGENT_TARGET"
cp "$FRONTEND_LAUNCH_AGENT_SOURCE" "$FRONTEND_LAUNCH_AGENT_TARGET"

if launchctl print "$SERVICE_DOMAIN/$SERVICE_LABEL" >/dev/null 2>&1; then
  echo "Restarting loaded service..."
  launchctl kickstart -k "$SERVICE_DOMAIN/$SERVICE_LABEL"
else
  echo "Loading service..."
  launchctl bootstrap "$SERVICE_DOMAIN" "$LAUNCH_AGENT_TARGET"
  launchctl kickstart -k "$SERVICE_DOMAIN/$SERVICE_LABEL"
fi

if launchctl print "$SERVICE_DOMAIN/$FRONTEND_SERVICE_LABEL" >/dev/null 2>&1; then
  echo "Restarting loaded frontend service..."
  launchctl kickstart -k "$SERVICE_DOMAIN/$FRONTEND_SERVICE_LABEL"
else
  echo "Loading frontend service..."
  launchctl bootstrap "$SERVICE_DOMAIN" "$FRONTEND_LAUNCH_AGENT_TARGET"
  launchctl kickstart -k "$SERVICE_DOMAIN/$FRONTEND_SERVICE_LABEL"
fi

echo "Checking backend health..."
for attempt in {1..20}; do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "Backend is healthy: $HEALTH_URL"
    break
  fi
  if [[ "$attempt" == "20" ]]; then
    echo "Backend did not become healthy. Check logs:" >&2
    echo "  /private/tmp/aao-fastapi.log" >&2
    echo "  /private/tmp/aao-fastapi.err.log" >&2
    exit 1
  fi
  sleep 0.5
done

echo "Checking frontend health..."
for attempt in {1..20}; do
  if curl -fsS "$FRONTEND_URL" >/dev/null 2>&1; then
    echo "Frontend is healthy: $FRONTEND_URL"
    exit 0
  fi
  sleep 0.5
done

echo "Frontend did not become healthy. Check logs:" >&2
echo "  /private/tmp/aao-frontend.log" >&2
echo "  /private/tmp/aao-frontend.err" >&2
exit 1
