# ── base: shared system deps + Python env ─────────────────────────────────────
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps for the barcode lib are installed in Phase 3.
# This apt layer stays so later phase PRs can append packages here.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── dev: editable install with dev extras (used by docker compose) ─────────────
FROM base AS dev

COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --upgrade pip && pip install -e '.[dev]'

ENV PORT=8080
EXPOSE 8080

CMD ["bash"]

# ── prod: non-editable install, no dev extras, minimal attack surface ──────────
FROM base AS prod

COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --upgrade pip && pip install .

ENV PORT=8080
EXPOSE 8080

# Cloud Run sets $PORT; uvicorn reads it at startup.
CMD ["sh", "-c", "uvicorn wallet_bot.main:app --host 0.0.0.0 --port ${PORT}"]
