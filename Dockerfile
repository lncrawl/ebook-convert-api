# syntax=docker/dockerfile:1
ARG CALIBRE_VERSION=9.9.0
ARG PYTHON_VERSION=3.14

# ──────────────────────────────────────────────────────────────────────────────
# Stage 1: build Calibre from source, stripping Qt/GUI components
# ──────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-bookworm AS calibre-builder

ARG CALIBRE_VERSION

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    pkg-config \
    wget \
    xz-utils \
    # Calibre C extension deps (no Qt dev packages)
    libxml2-dev \
    libxslt1-dev \
    libpng-dev \
    libjpeg62-turbo-dev \
    libfreetype6-dev \
    libicu-dev \
    libhunspell-dev \
    libhyphen-dev \
    libpodofo-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

RUN wget -q "https://github.com/kovidgoyal/calibre/releases/download/v${CALIBRE_VERSION}/calibre-${CALIBRE_VERSION}.tar.xz" \
    && tar -xf "calibre-${CALIBRE_VERSION}.tar.xz" \
    && rm "calibre-${CALIBRE_VERSION}.tar.xz"

WORKDIR /build/calibre-${CALIBRE_VERSION}

COPY docker/patch_calibre.py ./docker/patch_calibre.py
RUN python3 docker/patch_calibre.py

# Build C extensions (Qt extensions skipped automatically — marked optional)
RUN python3 setup.py build

# Install into a staging root so we can cherry-pick what goes into the runtime
RUN python3 setup.py install --prefix=/usr/local --staging-root=/calibre-staging

# Strip GUI modules, viewer, and device-sync binaries we don't need
RUN find /calibre-staging -type d -name "gui2" -exec rm -rf {} + 2>/dev/null; \
    rm -f /calibre-staging/bin/calibre \
          /calibre-staging/bin/calibre-debug \
          /calibre-staging/bin/calibre-customize \
          /calibre-staging/bin/calibre-server \
          /calibre-staging/bin/lrfviewer \
          /calibre-staging/bin/calibre-smtp 2>/dev/null; \
    find /calibre-staging -name "*.pyc" -delete; \
    true


# ──────────────────────────────────────────────────────────────────────────────
# Stage 2: slim runtime — copies only Calibre artifacts + app code
# ──────────────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

# uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Runtime shared libraries (no -dev, no compiler)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    libpng16-16 \
    libjpeg62-turbo \
    libfreetype6 \
    libicu72 \
    libhunspell-1.7-0 \
    libhyphen0 \
    libpodofo0.9.8 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Calibre modules and compiled extensions from builder
COPY --from=calibre-builder /calibre-staging/lib/calibre /usr/local/lib/calibre
COPY --from=calibre-builder /calibre-staging/bin /usr/local/bin/
COPY --from=calibre-builder /calibre-staging/share/calibre /usr/local/share/calibre

# Calibre installs to /usr/local/lib/calibre — add it to Python's module search path
ENV PYTHONPATH=/usr/local/lib

WORKDIR /app

# Install Python dependencies via uv (before copying app code for better layer caching)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

# Copy application source
COPY app/ ./app/

# Non-root user (UID 1001, GID 0 for OpenShift compatibility)
RUN useradd -r -u 1001 -g 0 -d /app app \
    && chown -R 1001:0 /app \
    && chmod -R g=u /app

USER 1001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8000/ready || exit 1

CMD ["uv", "run", "--frozen", "uvicorn", "app.main:app", \
     "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
