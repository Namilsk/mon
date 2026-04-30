#!/bin/bash

set -e

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

./venv/bin/pip install -q -r requirements.txt

# Generate secrets if not set
export JWT_SECRET=${JWT_SECRET:-$(openssl rand -hex 32)}
export ADMIN_PASSWORD=${ADMIN_PASSWORD:-$(openssl rand -base64 12)}
export FLASK_SECRET_KEY=${FLASK_SECRET_KEY:-$(openssl rand -hex 32)}

echo ""
echo "╔════════════════════════════════════╗"
echo "║      Server Monitor (Local)          ║"
echo "╚════════════════════════════════════╝"
echo ""
echo "Credentials:"
echo "  Username: admin"
echo "  Password: $ADMIN_PASSWORD"
echo ""
echo "Starting services..."
echo ""

# Run central server in background
echo "[+] Starting central server..."
python central/app.py &
CENTRAL_PID=$!

sleep 2

# Run node agent
echo "[+] Starting node agent..."
export NODE_ID=${NODE_ID:-local-node}
export CENTRAL_URL=http://localhost:5000
export POLL_INTERVAL=${POLL_INTERVAL:-5}
python node/agent.py &
AGENT_PID=$!

echo ""
echo "════════════════════════════════════"
echo "Server Monitor running!"
echo "Dashboard: http://localhost:5000"
echo "════════════════════════════════════"
echo ""
echo "Press Ctrl+C to stop"

function cleanup() {
    echo ""
    echo "Shutting down..."
    kill $AGENT_PID 2>/dev/null || true
    kill $CENTRAL_PID 2>/dev/null || true
    exit 0
}

trap cleanup INT TERM

wait
