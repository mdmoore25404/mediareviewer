# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Multi-arch single-container image for Media Reviewer
# Base images:
#   node:20-slim    — amd64/arm64 official manifest; frontend built natively
#   python:3.12-slim — amd64/arm64 official manifest; Python already present
# ---------------------------------------------------------------------------

# ── Stage 1: build React frontend ─────────────────────────────────────────
# ARG BUILDPLATFORM is the host machine platform (amd64 on CI runners and
# local x86 machines).  Using it here means npm/vite always run natively,
# never under QEMU emulation, regardless of the target --platform.
FROM --platform=$BUILDPLATFORM node:20-slim AS frontend-builder

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --prefer-offline

COPY frontend/ ./
RUN npm run build


# ── Stage 2: runtime image ────────────────────────────────────────────────
# python:3.12-slim is a minimal Debian image with Python 3.12 pre-installed
# and published as a native multi-arch manifest (amd64 + arm64 + more).
# This means pip can download pre-compiled manylinux wheels for Pillow etc.
# rather than building from source — arm64 pip installs complete in seconds.
FROM python:3.12-slim AS runtime

# ffmpeg — video thumbnail generation via subprocess
# gosu   — lightweight setuid helper (Debian equivalent of Alpine's su-exec)
#           used by entrypoint.sh to drop from root to PUID/PGID
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        gosu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies directly into the system Python (no venv needed
# in an isolated container).  Pillow wheels include libjpeg/libpng/libwebp.
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Install the backend package.
# pyproject.toml lives at /app/pyproject.toml; pip install . reads it and
# finds the packages under src/ via [tool.setuptools.packages.find].
COPY backend/src ./src
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy pre-built frontend assets from stage 1
COPY --from=frontend-builder /build/frontend/dist /app/static

# Create state/data directory; entrypoint.sh will chown it at runtime
# to match PUID/PGID, so we keep it root-owned here.
RUN mkdir -p /data

# Copy entrypoint script (runs as root, drops to PUID/PGID before exec)
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

VOLUME ["/data"]

# Run as root so entrypoint.sh can chown /data and call su-exec
# USER appuser  ← removed; privilege drop is handled by entrypoint.sh

ENV MEDIAREVIEWER_HOST=0.0.0.0 \
    MEDIAREVIEWER_PORT=8080 \
    MEDIAREVIEWER_STATE_DIR=/data \
    MEDIAREVIEWER_STATIC_DIR=/app/static \
    PUID=1000 \
    PGID=1000

EXPOSE 8080

# entrypoint.sh chowns /data, drops to PUID:PGID, then execs mediareviewer-api
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["mediareviewer-api"]
