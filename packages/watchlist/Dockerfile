FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY packages/datafeed/ packages/datafeed/
COPY packages/metrics/ packages/metrics/
COPY packages/dividends/ packages/dividends/
COPY packages/events/ packages/events/
COPY packages/fx/ packages/fx/
COPY packages/benchmark/ packages/benchmark/
COPY packages/future/ packages/future/
COPY packages/stock/ packages/stock/
COPY packages/etf/ packages/etf/
COPY packages/watchlist/ packages/watchlist/

WORKDIR /app/packages/watchlist
RUN uv sync --frozen --no-dev

ENTRYPOINT ["uv", "run", "--no-sync", "equicast-watchlist"]
CMD ["--watchlist-key", "GLOBAL_MARKETS", "--config", "config/global_markets.dev.yaml", "--out", "/output"]
