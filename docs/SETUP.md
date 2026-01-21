# Setup

This project targets Python 3.13.7 for development. The repository includes a helper script to create a local virtual environment.

Prerequisites:
- Python 3.13.7 installed (or an appropriate `python3.13` executable on PATH)
- `git` (optional)

Quick start:

```bash
# Create venv and install runtime+dev deps
./scripts/setup_venv.sh

# Activate
source .venv/bin/activate

# Run tests
pytest
```

If you do not have `python3.13` available, set the `PYTHON` env var to the path of a Python 3.13.7 executable before running the script:

```bash
PYTHON=/usr/bin/python3.13 ./scripts/setup_venv.sh
```

Files created/used:
- `.venv/` — local virtual environment
- `requirements.txt`, `requirements-dev.txt` — dependency lists
