# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Single image for all four services. The control plane (gateway/scheduler/
# metrics) and the default stub worker need no torch, so the base image stays
# small. Pass --build-arg INSTALL_ML=1 to bake in the PyTorch/ONNX runtime for
# a GPU worker image.
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps: libgl/zlib for Pillow image decoding.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg62-turbo zlib1g curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first (better layer caching).
COPY pyproject.toml README.md ./
COPY libs/platform_common/pyproject.toml libs/platform_common/
COPY libs/platform_common/platform_common/__init__.py libs/platform_common/platform_common/

# Copy the full source.
COPY libs ./libs
COPY services ./services
COPY scripts ./scripts
COPY models ./models

ARG INSTALL_ML=0
RUN pip install -e libs/platform_common \
    && pip install -e . \
    && if [ "$INSTALL_ML" = "1" ]; then pip install -e ".[ml]"; fi

# Non-root runtime user.
RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

EXPOSE 8080 8085 8090 9000

# Default command runs the gateway; compose/k8s override per service.
CMD ["uvicorn", "services.api_gateway.main:app", "--host", "0.0.0.0", "--port", "8080"]
