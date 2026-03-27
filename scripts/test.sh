#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

(
  cd "$ROOT_DIR/backend"
  if [[ -d .venv ]]; then
    source .venv/bin/activate
  fi
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest tests -q
)

(
  cd "$ROOT_DIR/frontend"
  npm run lint
  npm run build
)
