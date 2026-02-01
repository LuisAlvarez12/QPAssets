#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Image Compressor Pro - Launch Script
# ═══════════════════════════════════════════════════════════════════════════════
#
# This script activates the virtual environment and launches the Image Compressor.
#
# Usage:
#   ./run_compressor.sh
#
# ═══════════════════════════════════════════════════════════════════════════════

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Navigate to project directory
cd "$SCRIPT_DIR"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    echo "Installing dependencies..."
    pip install -r requirements.txt --quiet
else
    source .venv/bin/activate
fi

# Run the image compressor
python image_compressor.py
