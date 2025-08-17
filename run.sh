#!/bin/bash
# Cognitex Run Script

echo "Starting Cognitex..."

# Check if venv exists and activate it
if [ -d "venv" ]; then
    source venv/bin/activate
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
else
    # Try running with user-installed packages
    export PATH="$HOME/.local/bin:$PATH"
    python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
fi