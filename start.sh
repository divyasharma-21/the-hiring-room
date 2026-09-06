#!/usr/bin/env bash
# Start The Hiring Room (backend + frontend)
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "▶ Starting backend on :8000 ..."
cd "$ROOT/backend"
if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

echo "▶ Starting frontend on :5173 ..."
cd "$ROOT/frontend"
npm run dev -- --host 0.0.0.0 --port 5173 &
FRONTEND_PID=$!

echo ""
echo "  The Hiring Room is running"
echo "  Frontend  →  http://localhost:5173"
echo "  API docs  →  http://localhost:8000/docs"
echo "  Health    →  http://localhost:8000/api/health"
echo ""
echo "  Press Ctrl+C to stop both."
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
