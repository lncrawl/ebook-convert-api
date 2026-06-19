
#------------------------------------------------
# Common modules
#------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS common

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    QTWEBENGINE_DISABLE_SANDBOX=1 \
    QT_QPA_PLATFORM=offscreen \
    QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu --disable-software-rasterizer"

RUN apt-get update -yq && \
    apt-get install -yq --no-install-recommends \
    ca-certificates \
    curl \
    libnss3 \
    libfontconfig \
    libxkbcommon0 \
    && rm -rf /var/lib/apt/lists/*

#------------------------------------------------
# Install Calibre
#------------------------------------------------
FROM common AS calibre

RUN apt-get update -yq && \
    apt-get install -yq --no-install-recommends \
    wget \
    libxcb-cursor0 \
    xdg-utils \
    xz-utils \
    libegl1 \
    libopengl0 \
    libglx0 \
    libnss3 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

RUN wget -nv -O- https://download.calibre-ebook.com/linux-installer.sh \
    | sh /dev/stdin install_dir=/opt isolated=y

#------------------------------------------------
# Base runtime image
#------------------------------------------------
FROM common

# Copy calibre
COPY --from=calibre /opt/calibre /opt/calibre
ENV PATH="/opt/calibre:${PATH}"

# Root user
WORKDIR /app

COPY scripts/calibre_introspect.py ./scripts/calibre_introspect.py
RUN calibre-debug -e ./scripts/calibre_introspect.py ./data/output.json

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

COPY app/ ./app/

# Non-root user (UID 1001, GID 0 for OpenShift compatibility)
RUN useradd -r -u 1001 -g 0 -d /app app \
    && chown -R 1001:0 /app \
    && chmod -R g=u /app

USER 1001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8000/ready || exit 1

CMD ["/app/.venv/bin/uvicorn", "app.main:app",\
    "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
