#------------------------------------------------
# Calibre: download the self-contained binary, generate the option catalog,
# then strip everything a headless convert-only service never touches.
#------------------------------------------------
FROM debian:trixie-slim AS calibre

ENV QT_QPA_PLATFORM=offscreen \
    QTWEBENGINE_DISABLE_SANDBOX=1

# Tools to fetch/unpack Calibre plus the few shared libs `calibre-debug` needs to
# import the conversion pipeline for catalog generation. None reach the runtime image.
RUN apt-get update -yq
RUN apt-get install -yq --no-install-recommends \
    ca-certificates \
    wget \
    xz-utils \
    python3 \
    libnss3 \
    libfontconfig1 \
    libxkbcommon0 \
    libxcb-cursor0 \
    libegl1 \
    libopengl0 \
    libglx0 \
    libasound2

RUN wget -nv -O- https://download.calibre-ebook.com/linux-installer.sh \
    | sh /dev/stdin install_dir=/opt isolated=y

ENV PATH="/opt/calibre:${PATH}"

# Generate the option catalog from the exact Calibre version installed above.
COPY ./scripts/calibre_introspect.py calibre_introspect.py
RUN calibre-debug -e calibre_introspect.py /catalog.json

# Drop components unused by headless `ebook-convert`: UI translation catalogs
# (locales.zip, but keep the iso639/iso3166 language data the pipeline imports),
# all but the English WebEngine locale, the content server, WebEngine devtools,
# man pages, compiled-Python caches, and the bundled ONNX (AI/TTS) + ffmpeg
# (audio) libraries that the conversion pipeline never touches.
RUN cd /opt/calibre \
    && rm -f resources/localization/locales.zip \
    && find translations/qtwebengine_locales -type f ! -name 'en-US.pak' -delete \
    && rm -rf resources/content-server \
    && rm -f resources/qtwebengine_devtools_resources.pak \
    && rm -rf share/man share/doc \
    && rm -f lib/libonnxruntime.so* lib/libav*.so* lib/libsw*.so* \
    && find . -type d -name __pycache__ -prune -exec rm -rf {} + \
    && find . -type f -name '*.pyc' -delete

#------------------------------------------------
# Runtime: Minimal dependencies for running Calibre ebook-convert
#------------------------------------------------
FROM python:3.14-slim-trixie AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    QT_QPA_PLATFORM=offscreen \
    QTWEBENGINE_DISABLE_SANDBOX=1 \
    QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu --disable-software-rasterizer --disable-dev-shm-usage"

# Shared libraries the bundled Qt/WebEngine needs for headless conversion. The
# heavy Mesa software rasterizer (libLLVM/gallium/llvmpipe, ~180 MB) is pulled in
# as a dependency but never used — WebEngine renders via its bundled SwiftShader
# under --disable-gpu — so it is deleted in the same layer.
RUN apt-get update -yq \
    && apt-get install -yq --no-install-recommends \
    libnss3 \
    libfontconfig1 \
    libxkbcommon0 \
    libxcb-cursor0 \
    libegl1 \
    libopengl0 \
    libglx0 \
    libasound2t64 \
    && rm -f /usr/lib/*/libLLVM*.so* /usr/lib/*/libgallium*.so* /usr/lib/*/libz3*.so* \
    && rm -rf /usr/lib/*/dri \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=calibre /opt/calibre /opt/calibre
COPY --from=calibre /catalog.json ./data/catalog.json
ENV PATH="/opt/calibre:/app/.venv/bin:${PATH}"

#------------------------------------------------
# Builder: resolve the Python venv with uv (uv itself never reaches runtime).
#------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder

WORKDIR /app

COPY --from=calibre /opt/calibre /opt/calibre
COPY --from=calibre /catalog.json ./data/catalog.json
ENV PATH="/opt/calibre:/app/.venv/bin:${PATH}"

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

#------------------------------------------------
# Dev: runtime + uv + dev-group dependencies
#------------------------------------------------
FROM runtime AS dev

COPY --from=ghcr.io/astral-sh/uv:python3.14-trixie-slim /usr/local/bin/uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-editable

EXPOSE 8000

CMD ["uvicorn", "app.main:app", \
    "--host", "0.0.0.0", "--port", "8000", \
    "--reload", "--reload-dir", "/app/app"]

#------------------------------------------------
# Runtime: slim base + libraries needed at run time.
#------------------------------------------------
FROM runtime AS app

COPY --from=builder /app/.venv ./.venv
COPY app/ ./app/

# Non-root user (UID 1001, GID 0 for OpenShift compatibility)
RUN useradd -r -u 1001 -g 0 -d /app app \
    && chown -R 1001:0 /app \
    && chmod -R g=u /app

USER 1001

EXPOSE 8000

# Readiness probe via the bundled venv Python — avoids shipping curl.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD ["python", "-c", "import sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/ready').status==200 else 1)"]

CMD ["uvicorn", "app.main:app", \
    "--host", "0.0.0.0", "--port", "8000", \
    "--no-access-log"]
