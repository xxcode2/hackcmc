#!/usr/bin/env bash
# Start TWAK MCP REST server in background
# Usage: ./start_twak_mcp.sh [port]
# Default port: 3000

PORT=${1:-3000}
PASSWORD="SentimentSwipe2026!"

echo "Starting TWAK MCP server on port $PORT..."
echo "Auth: Bearer token (HMAC secret from ~/.twak/credentials.json)"
echo ""

# Set HOME explicitly for Windows/git-bash
export HOME="${HOME:-/c/Users/irgir}"
export TWAK_WALLET_PASSWORD="$PASSWORD"

# Kill any existing server on this port
fuser -k ${PORT}/tcp 2>/dev/null || true

# Start the server in background
twak serve --rest --port "$PORT" --password "$PASSWORD" &
SERVER_PID=$!

echo "TWAK MCP server started (PID: $SERVER_PID)"
echo "URL: http://127.0.0.1:$PORT"
echo "Health: GET http://127.0.0.1:$PORT/"
echo "Actions: POST http://127.0.0.1:$PORT/actions/<action>"
echo ""
echo "To stop: kill $SERVER_PID"
echo ""

# Wait for server to start
sleep 3

# Test connection
curl -s -X POST "http://127.0.0.1:$PORT/actions/switch_wallet_mode" \
  -H "Authorization: Bearer $(cat ~/.twak/credentials.json | python3 -c 'import sys,json; print(json.load(sys.stdin)["hmacSecret"])' 2>/dev/null)" \
  -H "Content-Type: application/json" \
  -d '{"mode":"local"}' | python3 -m json.tool 2>/dev/null || echo "Server started (wallet mode test needs credentials)"

echo ""
echo "Server running. PID: $SERVER_PID"