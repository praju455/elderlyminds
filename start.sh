#!/bin/bash
# Default start script for Render
# This script starts the API Gateway service by default.
# If you need to start a different service, you should either:
# 1. Update this script.
# 2. Use the "Blueprint" feature with render.yaml.
# 3. Explicitly set the "Start Command" in the Render dashboard.

echo "Starting Bhumi Gateway service..."
uvicorn gateway.main:app --host 0.0.0.0 --port $PORT
