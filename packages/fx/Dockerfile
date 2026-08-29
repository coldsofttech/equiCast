FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages/datafeed/ packages/datafeed/
COPY packages/fx/ packages/fx/

WORKDIR /app/packages/fx
RUN uv sync --frozen --no-dev

ENTRYPOINT ["uv", "run", "--no-sync", "equicast-fx"]
CMD ["--config", "config/fx_pairs.yaml", "--out", "/output"]
