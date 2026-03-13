FROM python:3.13-slim AS base

WORKDIR /app

# Install uv
RUN pip install uv

# Install into system Python (no venv needed in containers)
ENV UV_SYSTEM_PYTHON=1

# Copy dependency files first (layer caching)
COPY pyproject.toml ./

# Install project dependencies only (no self-install, no dev deps)
RUN uv pip install -r pyproject.toml

# Copy application code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


FROM base AS dev

# Dev tools — ruff, mypy, pytest, httpx (for API tests)
RUN uv pip install ruff mypy pytest pytest-asyncio httpx
