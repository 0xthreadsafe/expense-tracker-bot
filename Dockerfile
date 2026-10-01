# Dependencies are installed in a separate stage so that the runtime image
# carries neither the build tooling nor the package cache.
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies are copied and installed before the source so that editing the
# source does not invalidate the cached dependency layer.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev --extra postgres

COPY src ./src
COPY README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra postgres


FROM python:3.12-slim AS runtime

# Running as root would let a container escape become a host compromise.
RUN useradd --create-home --uid 10001 bot

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY --from=builder --chown=bot:bot /app/.venv /app/.venv
COPY --from=builder --chown=bot:bot /app/src /app/src

# Holds the SQLite file when no external database is configured.
RUN mkdir -p /app/data && chown bot:bot /app/data
VOLUME ["/app/data"]

USER bot

# Fails the container when the bot cannot import its own configuration.
HEALTHCHECK --interval=60s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import expensebot" || exit 1

CMD ["expensebot"]
