#!/usr/bin/env bash
set -e

echo "=== MindRead Environment Startup ==="

# Check for .env
if [ ! -f .env ]; then
    echo "WARNING: .env file not found. Creating template..."
    echo 'GROQ_API_KEY=your_key_here' > .env
    echo "Set GROQ_API_KEY in .env before running."
    exit 1
fi

# Load env vars
export $(grep -v '^#' .env | xargs)

if [ -z "$GROQ_API_KEY" ] || [ "$GROQ_API_KEY" = "your_key_here" ]; then
    echo "ERROR: GROQ_API_KEY not set in .env"
    exit 1
fi

echo "Groq API key: ${GROQ_API_KEY:0:8}..."

# Check dependencies
if ! python -c "import fastapi" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt -q
fi

echo "Starting MindRead environment server on port 7860..."
uvicorn server.main:app --host 0.0.0.0 --port 7860 --reload
