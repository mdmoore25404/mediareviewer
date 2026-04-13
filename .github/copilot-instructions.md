# Media Reviewer Workspace Instructions

This repository is the implementation workspace for Media Reviewer, a lightweight mobile-first review tool for images and videos.

## Mandatory workflow

- Start by checking `.TODO/status.md`, `.TODO/backlog.md`, and `.TODO/open-questions.md` before implementing a new slice.
- Keep implementation requests small enough to finish linting, testing, and documenting in one pass.
- At the end of every implementation request, lint every Python, JavaScript, and TypeScript file that was created or modified in that request.
- Add or update tests for every feature change, then iterate until the relevant linting and tests pass.
- Commit each completed request with a clear git commit message.
- Record recurring lint mistakes or anti-patterns in `.TODO/lint-notes.md` so they are not repeated.
- Update `docs/api/reference.md` whenever API routes, payloads, or error models change.

## Coding standards

- Use explicit types. Do not rely on lazy typing or untyped public interfaces.
- Keep imports at the top of the file. Do not use local imports unless a future request explicitly documents why one is unavoidable.
- Write self-documenting code and include docstrings or concise explanatory comments where they improve generated documentation.
- Preserve the Flask API and React client as separate projects for local development, while keeping them compatible with a single-host deployment later.
- Prefer small, composable services over large route handlers.

## Implementation expectations

- Python changes should stay compatible with `ruff` and `pytest`.
- Frontend changes should stay compatible with `eslint`, `vitest`, and the TypeScript compiler.
- API reference documentation must remain in Markdown with Jekyll front matter.
- Avoid database dependencies. State is represented by filesystem companion files and user-level configuration under `~/.mediareviewer`.
- Runtime support must remain portable across x86_64 and ARM64 (including Apple Silicon).
- When adding low-level or native dependencies, document architecture impacts and compatibility notes.
- Docker images must be planned for multi-arch manifests (`linux/amd64` and `linux/arm64`) using suitable official base images.
