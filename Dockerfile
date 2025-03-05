FROM debian:bookworm-slim AS builder-base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="$PATH:/root/.local/bin/:/app/.venv/bin"

FROM builder-base AS python-base

WORKDIR /app

COPY pyproject.toml ./

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    curl \
    libpq-dev \
    clang \
    ca-certificates && \
    curl -LsSf https://github.com/astral-sh/uv/releases/download/0.5.9/uv-installer.sh | sh && \
    uv sync -p 3.13.1 --link-mode=copy -n --no-dev && \
    uv add psycopg-c

FROM python-base AS production

WORKDIR /app

COPY --from=python-base /app/.venv /app/.venv
COPY . /app/

CMD [ "python", "client.py" ]
