#!/usr/bin/env bash
# generate-diagrams.sh — regenerate docs/architecture.md from the live codebase.
#
# Usage:
#   ./docs/scripts/generate-diagrams.sh
#
# This script is intentionally simple: architecture.md is hand-maintained
# Mermaid source that is re-authored by a Copilot agent run whenever the
# system structure changes significantly (new service, new route group, new
# data-flow step).  The script validates that the Mermaid fences are present
# and optionally renders PNGs if mmdc (mermaid-cli) is available.
#
# To trigger a full AI-assisted regeneration, run via the agent skill:
#   .github/instructions/generate-diagrams.instructions.md
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARCH_DOC="${REPO_ROOT}/docs/architecture.md"

echo "=== Media Reviewer — diagram check ==="
echo "  source: ${ARCH_DOC}"

if [[ ! -f "${ARCH_DOC}" ]]; then
  echo "ERROR: docs/architecture.md not found. Run the agent to regenerate." >&2
  exit 1
fi

FENCE_COUNT=$(grep -c '```mermaid' "${ARCH_DOC}" || true)
echo "  mermaid fences found: ${FENCE_COUNT}"

if [[ "${FENCE_COUNT}" -lt 1 ]]; then
  echo "ERROR: no mermaid fences found in architecture.md" >&2
  exit 1
fi

# Optional: render PNGs with mermaid-cli if available
if command -v mmdc >/dev/null 2>&1; then
  OUT_DIR="${REPO_ROOT}/docs/diagrams"
  mkdir -p "${OUT_DIR}"
  echo "  mmdc found — rendering PNGs to ${OUT_DIR}/"

  DIAGRAM_INDEX=0
  IN_FENCE=0
  CURRENT_FILE=""

  while IFS= read -r line; do
    if [[ "${line}" == '```mermaid' ]]; then
      DIAGRAM_INDEX=$((DIAGRAM_INDEX + 1))
      CURRENT_FILE="${OUT_DIR}/diagram-${DIAGRAM_INDEX}.mmd"
      > "${CURRENT_FILE}"
      IN_FENCE=1
    elif [[ "${line}" == '```' && "${IN_FENCE}" -eq 1 ]]; then
      IN_FENCE=0
      mmdc -i "${CURRENT_FILE}" \
           -o "${OUT_DIR}/diagram-${DIAGRAM_INDEX}.png" \
           --backgroundColor transparent \
           --quiet 2>/dev/null \
        && echo "    rendered diagram-${DIAGRAM_INDEX}.png" \
        || echo "    WARNING: mmdc failed for diagram-${DIAGRAM_INDEX} (skipping)"
    elif [[ "${IN_FENCE}" -eq 1 ]]; then
      echo "${line}" >> "${CURRENT_FILE}"
    fi
  done < "${ARCH_DOC}"
else
  echo "  mmdc not installed — skipping PNG render (npm install -g @mermaid-js/mermaid-cli to enable)"
fi

echo "=== done ==="
