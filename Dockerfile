FROM debian:trixie-slim AS builder
RUN apt-get update && apt-get install -y ca-certificates git build-essential && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app

ENV UV_MANAGED_PYTHON=1 \
    UV_PYTHON_INSTALL_DIR=/appy/ \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

RUN uv python install 3.13 && uv venv --relocatable /app/.venv
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-editable --no-dev
COPY . .
RUN uv sync --locked --no-editable --no-dev

RUN GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown") && \
    if [ "$GIT_COMMIT" != "unknown" ] && ! git diff --quiet 2>/dev/null; then \
        GIT_COMMIT="${GIT_COMMIT}-dirty"; \
    fi && \
    echo "${GIT_COMMIT}" > /app/.venv/.git_commit && \
    echo "Built with commit: ${GIT_COMMIT}"

FROM debian:trixie-slim
COPY --from=builder /etc/ssl/certs /etc/ssl/certs
COPY --from=builder /usr/share/ca-certificates /usr/share/ca-certificates
COPY --from=builder /app/ /app/
COPY --from=builder /appy/ /appy/
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app"
CMD ["aikta"]
