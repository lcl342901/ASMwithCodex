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
USER_ID="$(id -u)"
SERVICE_DOMAIN="gui/$USER_ID"
HEALTH_URL="http://127.0.0.1:8000/api/health"

echo "Project: $PROJECT_ROOT"
echo "Service: $SERVICE_ROOT"

if [[ ! -f "$LAUNCH_AGENT_SOURCE" ]]; then
  echo "Missing LaunchAgent template: $LAUNCH_AGENT_SOURCE" >&2
  exit 1
fi

mkdir -p "$SERVICE_ROOT" "$LAUNCH_AGENT_DIR"

echo "Syncing backend code..."
rsync -a --delete "$PROJECT_ROOT/backend/" "$SERVICE_ROOT/backend/"

if [[ ! -x "$SERVICE_ROOT/.venv/bin/python" ]]; then
  echo "Creating service virtual environment..."
  python3 -m venv "$SERVICE_ROOT/.venv"
fi

echo "Installing backend dependencies..."
"$SERVICE_ROOT/.venv/bin/pip" install -r "$SERVICE_ROOT/backend/requirements.txt"

echo "Installing LaunchAgent..."
cp "$LAUNCH_AGENT_SOURCE" "$LAUNCH_AGENT_TARGET"

if launchctl print "$SERVICE_DOMAIN/$SERVICE_LABEL" >/dev/null 2>&1; then
  echo "Restarting loaded service..."
  launchctl kickstart -k "$SERVICE_DOMAIN/$SERVICE_LABEL"
else
  echo "Loading service..."
  launchctl bootstrap "$SERVICE_DOMAIN" "$LAUNCH_AGENT_TARGET"
  launchctl kickstart -k "$SERVICE_DOMAIN/$SERVICE_LABEL"
fi

echo "Checking backend health..."
for attempt in {1..20}; do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    echo "Backend is healthy: $HEALTH_URL"
    exit 0
  fi
  sleep 0.5
done

echo "Backend did not become healthy. Check logs:" >&2
echo "  /private/tmp/aao-fastapi.log" >&2
echo "  /private/tmp/aao-fastapi.err.log" >&2
exit 1
