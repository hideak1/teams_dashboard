#!/bin/bash
# Team Dashboard — one-click install
# Usage: bash scripts/install.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Team Dashboard Install ==="

# 1. Python venv + deps
echo "[1/3] Setting up Python environment..."
cd "$PROJECT_DIR"
if [ ! -d ".venv" ]; then
  uv venv .venv
fi
source .venv/bin/activate
uv pip install fastapi uvicorn pydantic websockets

# 2. Build frontend
echo "[2/3] Building frontend..."
cd "$PROJECT_DIR/frontend"
if command -v bun &>/dev/null; then
  bun install --frozen-lockfile 2>/dev/null || bun install
  bun run build
elif command -v npm &>/dev/null; then
  npm install
  npm run build
else
  echo "WARNING: Neither bun nor npm found. Frontend not built."
  echo "         Install Node.js or Bun, then run: cd frontend && npm install && npm run build"
fi

# 3. Register hooks
echo "[3/3] Registering hooks..."
cd "$PROJECT_DIR"
python3 scripts/register_hooks.py

echo ""
echo "=== Install complete! ==="
echo "Start the dashboard:"
echo "  cd $PROJECT_DIR && source .venv/bin/activate && python -m team_dashboard.server"
echo ""
echo "Then open: http://localhost:3741"
