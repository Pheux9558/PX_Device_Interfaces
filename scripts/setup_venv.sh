#!/usr/bin/env bash
# Create and activate a Python 3.13.7 virtual environment in `.venv` and install dev deps.
set -euo pipefail

PYTHON=${PYTHON:-python3.13}
VENV_DIR=".venv"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "${PYTHON} not found. Install Python 3.13.7 or set PYTHON env to a suitable python executable." >&2
  exit 2
fi

echo "Creating venv in $VENV_DIR using $PYTHON"
$PYTHON -m venv "$VENV_DIR"
echo "Activating venv and upgrading pip"
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip

if [ -f requirements.txt ]; then
  echo "Installing runtime requirements"
  pip install -r requirements.txt
fi

if [ -f requirements-dev.txt ]; then
  echo "Installing dev requirements"
  pip install -r requirements-dev.txt
fi

echo "Done. Activate with: source $VENV_DIR/bin/activate"
