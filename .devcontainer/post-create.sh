#!/bin/bash
set -euo pipefail

echo "==> Installing Python backend dependencies..."
cd /workspace/backend
uv pip install --system -r pyproject.toml
# Dev tools — mirrors backend/Dockerfile dev stage
uv pip install --system ruff mypy pytest pytest-asyncio httpx

echo "==> Installing frontend dependencies..."
cd /workspace/frontend && npm install

echo "==> Installing admin frontend dependencies..."
cd /workspace/admin-frontend && npm install

echo "==> Applying Alembic migrations..."
cd /workspace/backend
alembic upgrade head

echo ""
echo "Dev container ready. Available commands:"
echo "  Backend:  cd /workspace/backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
echo "  Frontend: cd /workspace/frontend && npm run dev -- --host 0.0.0.0 --port 5173"
echo "  Admin:    cd /workspace/admin-frontend && npm run dev -- --host 0.0.0.0 --port 5174"
echo "  Tests:    cd /workspace/backend && pytest"
