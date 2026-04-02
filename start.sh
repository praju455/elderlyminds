#!/bin/bash

set -euo pipefail

echo "Starting Bhumi backend stack as a single service..."
python -m services.serve_all
