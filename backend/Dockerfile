FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages/equicast/ packages/equicast/
COPY backend/ backend/

WORKDIR /app/backend
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["uv", "run", "gunicorn", "equicast_api.wsgi:application", "--bind", "0.0.0.0:8000"]
