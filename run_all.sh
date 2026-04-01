#!/bin/bash
# Mac/Linux equivalent of run_all.ps1

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements.txt

echo "Starting microservices..."

# Run each service in the background
uvicorn services.ai_service.main:app --port 8001 &
P1=$!
uvicorn services.data_service.main:app --port 8002 &
P2=$!
uvicorn services.alerts_service.main:app --port 8003 &
P3=$!
uvicorn services.scheduler_service.main:app --port 8004 &
P4=$!
uvicorn gateway.main:app --port 8010 &
P5=$!

echo ""
echo "Gateway:  http://127.0.0.1:8010/health"
echo "AI:       http://127.0.0.1:8001/health"
echo "Data:     http://127.0.0.1:8002/health"
echo "Alerts:   http://127.0.0.1:8003/health"
echo "Scheduler http://127.0.0.1:8004/health"
echo ""
echo "Frontend should use VITE_API_BASE=http://127.0.0.1:8010"
echo ""
echo "Press Ctrl+C to stop all services!"

# Trap Ctrl+C to cleanly kill all background processes
trap "echo 'Shutting down services...'; kill $P1 $P2 $P3 $P4 $P5; exit" SIGINT SIGTERM

# Wait indefinitely for user to press Ctrl+C
wait
