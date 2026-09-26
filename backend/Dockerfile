# The backend image: every module in one process (ADR-0015). The build context is this
# `backend/` directory, which is also exactly what gets pushed to the Hugging Face Space.
#
# Same image, different commands (12-factor, XII):
#   docker run IMAGE                 -> serve (default)
#   docker run IMAGE migrate seed    -> one-off admin tasks

# uv comes from its official image. Overridable, e.g. to use a registry mirror.
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.8
FROM ${UV_IMAGE} AS uv

FROM python:3.12-slim AS build
COPY --from=uv /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first, so editing code doesn't invalidate the dependency layer.
COPY pyproject.toml uv.lock ./
COPY apps/gateway/pyproject.toml apps/gateway/pyproject.toml
COPY modules/banking_api/pyproject.toml modules/banking_api/pyproject.toml
COPY modules/decision/pyproject.toml modules/decision/pyproject.toml
COPY modules/mcp_server/pyproject.toml modules/mcp_server/pyproject.toml
COPY modules/orchestrator/pyproject.toml modules/orchestrator/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-workspace --package gateway
COPY apps apps
COPY modules modules
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable --package gateway

FROM python:3.12-slim AS runtime
# Hugging Face Spaces run containers as uid 1000.
RUN useradd --create-home --uid 1000 user
COPY --from=build --chown=user:user /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PORT=7860
USER user
EXPOSE 7860
# Exec form: Python is PID 1 and receives SIGTERM directly for a graceful shutdown.
ENTRYPOINT ["python", "-m", "gateway"]
CMD ["serve"]
