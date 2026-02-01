#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Image Compressor Pro - Launch Script
# ═══════════════════════════════════════════════════════════════════════════════
#
# Usage:
#   cd "compressor app"
#   ./run_compressor.sh
#
# ═══════════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if virtual environment exists, create if not
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    ~/.pyenv/versions/3.10.12/bin/python -m venv .venv
    source .venv/bin/activate
    echo "Installing dependencies..."
    pip install Pillow --quiet
else
    source .venv/bin/activate
fi

echo "Starting Image Compressor Pro..."
echo "Open http://localhost:8080 in your browser"
echo "Press Ctrl+C to stop"
echo ""

python image_compressor.py
