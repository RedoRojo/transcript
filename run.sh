#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -n "${TRANSCRIPT_PYTHON:-}" ] && [ -x "$TRANSCRIPT_PYTHON" ]; then
    PYTHON_CMD="$TRANSCRIPT_PYTHON"
elif [ -x ".venv/bin/python" ]; then
    PYTHON_CMD=".venv/bin/python"
elif [ -x "venv/bin/python" ]; then
    PYTHON_CMD="venv/bin/python"
else
    echo "Creating virtual environment in .venv..."
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
    PYTHON_CMD=".venv/bin/python"
fi

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
    echo "Warning: ffmpeg/ffprobe not found in PATH. YouTube mode will still work, but local media transcription requires ffmpeg." >&2
fi

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8001}"
export HOST PORT

echo "Starting Transcript server at http://$HOST:$PORT (Python: $PYTHON_CMD)..."
exec "$PYTHON_CMD" app.py
