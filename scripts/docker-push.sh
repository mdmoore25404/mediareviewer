#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# scripts/docker-push.sh
#
# Build a multi-arch (linux/amd64 + linux/arm64) Docker image and push it to
# the GitHub Container Registry (ghcr.io).
#
# Usage:
#   ./scripts/docker-push.sh              # tags as :latest
#   ./scripts/docker-push.sh v1.2.3       # tags as :1.2.3 AND :latest
#   ./scripts/docker-push.sh --load       # build amd64 only, load into local
#                                         # Docker daemon (for quick testing)
#
# Prerequisites:
#   - Docker with buildx plugin installed
#   - gh CLI authenticated  (gh auth login)
#   - Write access to ghcr.io/mdmoore25404/mediareviewer
# ---------------------------------------------------------------------------
set -euo pipefail

IMAGE="ghcr.io/mdmoore25404/mediareviewer"
BUILDER_NAME="mediareviewer-multiarch"
# Run from the repo root regardless of where the script is invoked from
cd "$(dirname "$0")/.."

# ── Parse arguments ────────────────────────────────────────────────────────
LOAD_ONLY=false
VERSION_TAG=""

for arg in "$@"; do
    case "$arg" in
        --load)
            LOAD_ONLY=true
            ;;
        v[0-9]*)
            # Strip leading 'v' so the Docker tag is "1.2.3" not "v1.2.3"
            VERSION_TAG="${arg#v}"
            ;;
        *)
            echo "Unknown argument: $arg" >&2
            echo "Usage: $0 [v<semver>] [--load]" >&2
            exit 1
            ;;
    esac
done

# ── Ensure a multi-platform builder exists ─────────────────────────────────
# The default 'docker' driver cannot produce multi-platform manifests.
# We create a persistent 'docker-container' driver builder once and reuse it.
if ! docker buildx inspect "$BUILDER_NAME" &>/dev/null; then
    echo "Creating buildx builder '$BUILDER_NAME'..."
    docker buildx create --name "$BUILDER_NAME" --driver docker-container --bootstrap
fi
docker buildx use "$BUILDER_NAME"

# ── Authenticate with GHCR via gh CLI ─────────────────────────────────────
echo "Logging in to ghcr.io..."
gh auth token | docker login ghcr.io -u mdmoore25404 --password-stdin

# ── Assemble tag list ──────────────────────────────────────────────────────
TAGS=("${IMAGE}:latest")
if [[ -n "$VERSION_TAG" ]]; then
    TAGS+=("${IMAGE}:${VERSION_TAG}")
    # Also add the major.minor tag (e.g. "1.2" for "1.2.3")
    MAJOR_MINOR="${VERSION_TAG%.*}"
    TAGS+=("${IMAGE}:${MAJOR_MINOR}")
fi

TAG_ARGS=()
for t in "${TAGS[@]}"; do
    TAG_ARGS+=("--tag" "$t")
done

# ── Build ──────────────────────────────────────────────────────────────────
if [[ "$LOAD_ONLY" == "true" ]]; then
    echo "Building amd64 image and loading into local Docker daemon..."
    docker buildx build \
        --platform linux/amd64 \
        --load \
        "${TAG_ARGS[@]}" \
        .
    echo ""
    echo "Image loaded locally. Run with:"
    echo "  docker run --rm -p 8080:8080 -v \$(pwd)/data:/data ${TAGS[0]}"
else
    echo "Building multi-arch image (linux/amd64 + linux/arm64) and pushing..."
    docker buildx build \
        --platform linux/amd64,linux/arm64 \
        --push \
        "${TAG_ARGS[@]}" \
        .
    echo ""
    echo "Pushed:"
    for t in "${TAGS[@]}"; do
        echo "  $t"
    done
fi
