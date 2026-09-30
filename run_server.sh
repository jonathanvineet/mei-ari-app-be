#!/usr/bin/env bash
# Usage: bash run_server.sh [port] [host]
# Defaults to 0.0.0.0 so the mobile app on the same network can reach the API.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$ROOT_DIR/meiaribe"
VENV_DIR="$ROOT_DIR/.venv"
PORT="${1:-8000}"
HOST="${2:-0.0.0.0}"

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install -r "$ROOT_DIR/requirements.txt"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  echo "No .env found. Copy .env.example to .env and set GOOGLE_GEMINI_API_KEY." >&2
fi

cd "$PROJECT_DIR"

python manage.py migrate
python manage.py check

exec python manage.py runserver "${HOST}:${PORT}"
