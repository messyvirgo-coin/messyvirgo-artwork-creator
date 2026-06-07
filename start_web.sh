#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  echo "No .venv found. Complete one-time setup first (see README.md):" >&2
  echo "  python3 -m venv .venv" >&2
  echo "  source .venv/bin/activate" >&2
  echo "  pip install -e ." >&2
  echo "  cp .env.example .env   # add OPENROUTER_API_KEY=..." >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if [[ ! -f .env ]]; then
  echo "Warning: no .env file. Copy .env.example and set OPENROUTER_API_KEY." >&2
fi

if command -v mvac >/dev/null 2>&1; then
  exec mvac web "$@"
else
  exec python3 -m mv_artwork_creator web "$@"
fi
