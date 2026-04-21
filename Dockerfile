FROM python:3.12-slim

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

# Install Python deps — copy pyproject + (minimal) src so pip can do an editable install.
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --upgrade pip && pip install -e '.[dev]'

# Cloud Run expects the container to listen on $PORT.
ENV PORT=8080
EXPOSE 8080

# Real entrypoint (web server) is wired in Phase 1.
CMD ["python", "-c", "print('wallet-bot: no entrypoint yet — added in Phase 1')"]
