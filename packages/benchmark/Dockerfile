FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages/datafeed/ packages/datafeed/
COPY packages/metrics/ packages/metrics/
COPY packages/news/ packages/news/
COPY packages/benchmark/ packages/benchmark/

WORKDIR /app/packages/benchmark
RUN uv sync --frozen --no-dev

ENTRYPOINT ["uv", "run", "--no-sync", "equicast-benchmark"]
CMD ["--config", "config/benchmarks.dev.yaml", "--out", "/output"]
