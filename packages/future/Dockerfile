FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages/datafeed/ packages/datafeed/
COPY packages/metrics/ packages/metrics/
COPY packages/future/ packages/future/

WORKDIR /app/packages/future
RUN uv sync --frozen --no-dev

ENTRYPOINT ["uv", "run", "--no-sync", "equicast-future"]
CMD ["--config", "config/futures.dev.yaml", "--out", "/output"]
