#!/bin/bash

set -euo pipefail

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements.txt

echo "Starting backend stack as a single local process group..."
echo ""
echo "Gateway:   http://127.0.0.1:8010/health"
echo "AI:        http://127.0.0.1:8001/health"
echo "Data:      http://127.0.0.1:8002/health"
echo "Alerts:    http://127.0.0.1:8003/health"
echo "Scheduler: http://127.0.0.1:8004/health"
echo ""
echo "Frontend should use VITE_API_BASE=http://127.0.0.1:8010"
echo ""

python -m services.serve_all
