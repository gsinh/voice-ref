# The backend image: every module in one process (ADR-0015). The build context is this
# `backend/` directory, which is also exactly what gets pushed to the Hugging Face Space.
#
# Same image, different commands (12-factor, XII):
#   docker run IMAGE                 -> start: gateway + sidecars (SIDECARS=laya,voice)
#   docker run IMAGE migrate seed    -> one-off admin tasks
#
# Build args:
#   WITH_LAYA=false  skip the Laya sidecar (~1 GB of CPU PyTorch). Useful on a Mac, where
#                    Laya runs faster natively on the Apple GPU (see README).

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
COPY apps/voice_worker/pyproject.toml apps/voice_worker/pyproject.toml
COPY libs/signed_tokens/pyproject.toml libs/signed_tokens/pyproject.toml
COPY modules/banking_api/pyproject.toml modules/banking_api/pyproject.toml
COPY modules/mcp_server/pyproject.toml modules/mcp_server/pyproject.toml
COPY modules/orchestrator/pyproject.toml modules/orchestrator/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-workspace --all-packages
COPY apps apps
COPY libs libs
COPY modules modules
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable --all-packages

# Laya (System 1) in its own virtualenv: PyTorch never enters the app's dependency tree,
# and the app talks to it only over HTTP on localhost (ADR-0005).
FROM python:3.12-slim AS laya
ARG WITH_LAYA=true
ARG LAYA_VERSION=0.3.20
RUN python -m venv /opt/laya && if [ "$WITH_LAYA" = "true" ]; then \
      /opt/laya/bin/pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu torch && \
      /opt/laya/bin/pip install --no-cache-dir "laya[serve]==${LAYA_VERSION}"; \
    fi

FROM python:3.12-slim AS runtime
# Hugging Face Spaces run containers as uid 1000.
RUN useradd --create-home --uid 1000 user
COPY --from=build --chown=user:user /app/.venv /app/.venv
COPY --from=laya --chown=user:user /opt/laya /opt/laya
# Model files (Laya weights, Kokoro voice) download here on first start; mount a volume
# to keep them between runs.
RUN mkdir -p /data/hf /data/models && chown -R user:user /data
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PORT=7860 HF_HOME=/data/hf \
    KOKORO_DIR=/data/models/kokoro
USER user
EXPOSE 7860
# Exec form: the launcher is PID 1, receives SIGTERM directly and forwards it to every
# process it started (gateway, sidecars) for a graceful shutdown.
ENTRYPOINT ["python", "-m", "gateway"]
CMD ["start"]
