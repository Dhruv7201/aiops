#!/usr/bin/env bash
set -euo pipefail

echo "=== aiops setup ==="

# Check Python
if ! command -v python3.12 &>/dev/null; then
    echo "Error: Python 3.12 required. Install it first."
    exit 1
fi

# Check uv
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Create venv and install
echo "Creating virtual environment..."
uv venv --python 3.12

echo "Installing aiops with dev dependencies..."
uv pip install -e ".[dev]"

# Optional: install all extras
read -rp "Install all optional dependencies (OCR, YOLO, databases)? [y/N] " install_all
if [[ "$install_all" =~ ^[Yy]$ ]]; then
    uv pip install -e ".[all]"
fi

echo ""
echo "=== Setup complete ==="
echo "Activate with: source .venv/bin/activate"
echo "Or run commands with: uv run aiops --help"
