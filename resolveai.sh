#!/usr/bin/env bash
# ResolveAI launcher.
#
# With no arguments this drives the systemd service (recommended): it survives
# terminal close and restarts on reboot. Pass a PORT to instead run a one-off
# foreground server on that port (useful for a second instance / quick test).
#
# Usage:
#   resolveai              -> ensure the systemd service is running on :8000
#   resolveai start        -> start the service
#   resolveai stop         -> stop the service
#   resolveai restart      -> restart the service
#   resolveai status       -> service state + health check
#   resolveai logs         -> follow the service log
#   resolveai 9000         -> one-off foreground server on :9000 (Ctrl+C to stop)
#
# Env vars honored: RESOLVEAI_MODEL, RESOLVEAI_API_KEY, RESOLVEAI_DB, GROQ_API_KEY
set -euo pipefail

# Resolve the app directory relative to this script's location.
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNIT="resolveai.service"
PORT_DEFAULT=8000

url_for() { echo "http://localhost:$1"; }

health() {
    local port="${1:-$PORT_DEFAULT}" code
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$(url_for "$port")/health" || true)
    [ "$code" = "200" ]
}

show_status() {
    local state
    state=$(systemctl is-active "$UNIT" 2>/dev/null || true)
    echo "Service : $state ($(systemctl is-enabled "$UNIT" 2>/dev/null || echo unknown) at boot)"
    if [ "$state" = "active" ]; then
        if health "$PORT_DEFAULT"; then
            echo "Health  : OK  ->  $(url_for "$PORT_DEFAULT")"
        else
            echo "Health  : FAILED (service is up but /health did not answer)"
        fi
    fi
}

case "${1:-}" in
    start)
        systemctl start "$UNIT"
        sleep 2; show_status
        ;;
    stop)
        systemctl stop "$UNIT"
        echo "Stopped."
        ;;
    restart)
        systemctl restart "$UNIT"
        sleep 2; show_status
        ;;
    status)
        show_status
        ;;
    logs)
        journalctl -u "$UNIT" -f
        ;;
    "" )
        # Default: make sure the service is up, then report where to go.
        if [ "$(systemctl is-active "$UNIT" 2>/dev/null || true)" != "active" ]; then
            echo "Starting the ResolveAI service..."
            systemctl start "$UNIT"
            sleep 3
        fi
        if health "$PORT_DEFAULT"; then
            echo "ResolveAI is running  ->  $(url_for "$PORT_DEFAULT")"
        else
            echo "Service is up but /health is not answering. Recent log:"
            journalctl -u "$UNIT" --no-pager -n 15
            exit 1
        fi
        ;;
    *[!0-9]*)
        echo "Unknown command: $1" >&2
        echo "Usage: resolveai [start|stop|restart|status|logs|PORT]" >&2
        exit 2
        ;;
    *)
        # Numeric argument: run a one-off foreground server on that port.
        PORT="$1"
        cd "$APP_DIR"
        # Prefer the systemd runtime; fall back to the portable .venv that
        # setup.sh builds (used on Windows/macOS and plain dev machines).
        if [ -x /opt/resolveai-venv/bin/python ]; then
            PY=/opt/resolveai-venv/bin/python
        elif [ -x "$APP_DIR/.venv/bin/python" ]; then
            PY="$APP_DIR/.venv/bin/python"
        else
            echo "No runtime found. Run: bash $APP_DIR/setup.sh" >&2
            exit 1
        fi
        echo "Starting a one-off ResolveAI on $(url_for "$PORT")  (Ctrl+C to stop)"
        exec "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
        ;;
esac