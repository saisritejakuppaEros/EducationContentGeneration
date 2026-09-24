#!/usr/bin/env bash
# Serve timeline editor locally and optionally expose via Cloudflare quick tunnel.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8765}"
BIND="${BIND:-127.0.0.1}"

if ! curl -sf "http://${BIND}:${PORT}/" >/dev/null 2>&1; then
  echo "Starting HTTP server on http://${BIND}:${PORT}/"
  cd "$DIR"
  python3 -m http.server "$PORT" --bind "$BIND" &
  SERVER_PID=$!
  sleep 0.5
  trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT
else
  echo "Server already listening on http://${BIND}:${PORT}/"
fi

echo ""
echo "Cursor remote: open the Ports panel → Forward port ${PORT} → Open in Browser"
echo "  (On your laptop that becomes http://localhost:${PORT}/)"
echo ""

if command -v cloudflared >/dev/null 2>&1; then
  echo "Public tunnel (cloudflared):"
  exec cloudflared tunnel --url "http://${BIND}:${PORT}"
fi

CF="${TMPDIR:-/tmp}/cloudflared"
if [[ ! -x "$CF" ]]; then
  echo "Downloading cloudflared for a public URL..."
  curl -fsSL -o "$CF" "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64"
  chmod +x "$CF"
fi

echo "Public tunnel (cloudflared):"
exec "$CF" tunnel --url "http://${BIND}:${PORT}"
