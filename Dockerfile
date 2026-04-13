# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Multi-arch single-container image for Media Reviewer
# Tested base:  ubuntu:24.04  (amd64 + arm64 official manifest)
# ---------------------------------------------------------------------------

# ── Stage 1: build React frontend ─────────────────────────────────────────
FROM ubuntu:24.04 AS frontend-builder

# Install Node.js LTS via NodeSource (supports amd64 + arm64)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --prefer-offline

COPY frontend/ ./
RUN npm run build


# ── Stage 2: runtime image ────────────────────────────────────────────────
FROM ubuntu:24.04 AS runtime

# Install Python 3.12 (ships with Ubuntu 24.04) and Pillow system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.12 \
        python3.12-venv \
        python3-pip \
        # Pillow native deps
        libjpeg-turbo8 \
        libpng16-16 \
        libwebp7 \
        libtiff6 \
    && rm -rf /var/lib/apt/lists/*

# ubuntu:24.04 ships with an 'ubuntu' user at UID 1000 — use it directly
WORKDIR /app

# Install Python dependencies into an isolated venv
COPY backend/requirements.txt ./
RUN python3.12 -m venv /app/.venv \
    && /app/.venv/bin/pip install --no-cache-dir --upgrade pip \
    && /app/.venv/bin/pip install --no-cache-dir -r requirements.txt

# Install the backend package (editable not available in production; use normal install)
COPY backend/src ./src
COPY backend/pyproject.toml ./
RUN /app/.venv/bin/pip install --no-cache-dir ./src \
    || /app/.venv/bin/pip install --no-cache-dir -e .

# Copy pre-built frontend assets
COPY --from=frontend-builder /build/frontend/dist /app/static

# Config and state directories will be mounted at runtime
RUN mkdir -p /data && chown ubuntu:ubuntu /data
VOLUME ["/data"]

USER ubuntu

# Runtime environment
ENV MEDIAREVIEWER_HOST=0.0.0.0 \
    MEDIAREVIEWER_PORT=8080 \
    MEDIAREVIEWER_STATE_DIR=/data \
    MEDIAREVIEWER_STATIC_DIR=/app/static

EXPOSE 8080

# Use the mediareviewer-api entry-point installed by pyproject.toml
CMD ["/app/.venv/bin/mediareviewer-api"]
