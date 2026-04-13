# mediareviewer

Media Reviewer is a mobile-first web application for sorting large image and video sets into keep, trash, and review states without requiring a separate database. The repository is scaffolded as a Flask API plus a typed React frontend.

## Workspace layout

- `backend/`: Flask API, typed Python source, and pytest/ruff tooling.
- `frontend/`: Vite + React + TypeScript client with ESLint and Vitest.
- `docs/`: Project and API documentation in Markdown suitable for Jekyll rendering.
- `.TODO/`: Implementation backlog, status tracking, and lint lessons learned.

## Local development

### Backend

```bash
python3 -m venv backend/.venv
./backend/.venv/bin/pip install -e "backend[dev]"
./backend/.venv/bin/mediareviewer-api
```

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

## Quality gates

Every implementation request in this repository must:

1. Add or revise tests for the behavior being introduced or changed.
2. Lint the Python and React/JavaScript/TypeScript files modified in the request.
3. Re-run tests and lint until they pass.
4. Commit the request as a clear, focused git commit.
