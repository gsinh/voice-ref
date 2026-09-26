# One Dockerfile for every Python service (DRY). Build with:
#   docker build -f services/python.Dockerfile --build-arg SERVICE=banking_api --build-arg PACKAGE=banking-api .
# The build context is the repo root because services share the uv workspace and libs/common.

FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
ARG PACKAGE
# Dependencies first, so code edits don't invalidate the dependency layer.
COPY pyproject.toml uv.lock ./
COPY libs/common/pyproject.toml libs/common/pyproject.toml
COPY services/orchestrator/pyproject.toml services/orchestrator/pyproject.toml
COPY services/banking_api/pyproject.toml services/banking_api/pyproject.toml
COPY services/mcp_server/pyproject.toml services/mcp_server/pyproject.toml
COPY services/decision/pyproject.toml services/decision/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-workspace --package "$PACKAGE"
COPY libs libs
COPY services services
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package "$PACKAGE"

FROM python:3.12-slim AS runtime
ARG SERVICE
RUN useradd --create-home --uid 10001 app
COPY --from=build --chown=app:app /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 SERVICE_MODULE=${SERVICE}
USER app
# exec replaces the shell, so Python runs as PID 1 and receives SIGTERM directly.
CMD ["sh", "-c", "exec python -m \"$SERVICE_MODULE\""]
