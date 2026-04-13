# mediareviewer

Media Reviewer is a mobile-first web application for sorting large image and video sets into keep, trash, and review states without requiring a separate database. The repository is scaffolded as a Flask API plus a typed React frontend.

The current prototype includes:

- known review path management
- recursive media scanning with non-media filtering
- grid and list views with image/video previews
- fullscreen review mode opened from a media card
- lock, trash, seen, and unseen companion-file actions

## Workspace layout

- `backend/`: Flask API, typed Python source, and pytest/ruff tooling.
- `frontend/`: Vite + React + TypeScript client with ESLint and Vitest.
- `docs/`: Project and API documentation in Markdown suitable for Jekyll rendering.
- `.TODO/`: Implementation backlog, status tracking, and lint lessons learned.

## Local development

### Backend

```bash
python3 -m venv backend/.venv
./backend/.venv/bin/pip install -r backend/requirements-dev.txt
./backend/.venv/bin/mediareviewer-api
```

Committed backend requirement files are available at:

- `backend/requirements.txt`
- `backend/requirements-dev.txt`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` requests to the Flask API running on `http://127.0.0.1:5000`.

## Dev helper script

Use `./dev.sh` from the repository root to manage local workflows:

- `./dev.sh start`: start backend and frontend dev servers.
- `./dev.sh stop`: stop both dev servers.
- `./dev.sh restart`: restart both dev servers.
- `./dev.sh status`: show server status and log file paths.
- `./dev.sh lint`: run backend and frontend lint suites.
- `./dev.sh test`: run backend tests, frontend tests, and frontend build checks.

`dev.sh` reads listen and port settings from `~/.mediareviewer/config.yaml`:

```yaml
known_paths:
	- /home/michaelmoore/trailcam
server:
	backend_host: 127.0.0.1
	backend_port: 5000
	frontend_host: 0.0.0.0
	frontend_port: 5173
	trusted_hosts:
	  - somehost
```

Access URLs are printed by `./dev.sh status` and after `./dev.sh start`.

`server.trusted_hosts` is for additional hostnames you expect to use when accessing the app, for example `http://somehost:<port>`.
These hostnames are applied to:

- Flask trusted host handling
- Vite dev server allowed hosts

## Architecture Portability

Media Reviewer is designed for x86_64 and ARM64 environments, including Apple Silicon.

- Python and Node-based application code is architecture-portable by default.
- Any future native extensions, system codecs, or low-level binaries must be validated on both x86_64 and ARM64.
- If introducing architecture-specific dependencies, document compatibility and fallback behavior in this README and in `.TODO/open-questions.md`.

## Docker Multi-Arch Guidance

When adding or updating container builds:

- Use official multi-arch base images (for example, official Python images).
- Build and publish a multi-platform image manifest for at least `linux/amd64` and `linux/arm64`.
- Validate runtime behavior on both architectures before release.

Example build command:

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t <image>:<tag> --push .
```

## Quality gates

Every implementation request in this repository must:

1. Add or revise tests for the behavior being introduced or changed.
2. Lint the Python and React/JavaScript/TypeScript files modified in the request.
3. Re-run tests and lint until they pass.
4. Commit the request as a clear, focused git commit.
