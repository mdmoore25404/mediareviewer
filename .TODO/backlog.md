# Media Reviewer Backlog

## Current tranche

- done: initialize git repository.
- done: add workspace instructions and coding standards.
- done: scaffold backend, frontend, documentation, and test tooling.
- done: establish the first vertical foundation with typed config and health status.

## Next implementation slices

- done: persist review folder settings under `~/.mediareviewer`.
- done: add folder picker API with hidden-path enforcement.
- done: scan media folders and return typed review item summaries.
- done: implement companion file actions for `lock`, `trash`, and `seen`.
- done: implement frontend review-path management and media browser controls.
- done: wire frontend companion state actions for lock/trash/seen/unseen.
- done: document architecture portability and Docker multi-arch manifest expectations.
- done: configure dev listen/ports through `~/.mediareviewer/config.yaml` and `dev.sh`.
- done: add committed backend requirements files and YAML trusted-host support.
- planned: add theme mode toggle with light, dark, and auto(system) options.
- done: add deletion queue placeholder; implement synchronous empty-trash endpoint.
- done: package the single-host deployment path for Docker and NAS usage (Dockerfile + docker-compose).
- done: stream NDJSON scan results with offset pagination and infinite scroll.
- done: review mode UX polish (status indicators, auto-advance, mobile layout, keyboard shortcuts, help panel).
- done: locked-item trash prevention (backend 409 + frontend warning modal).
- planned: probe video duration and dimensions with ffprobe during scan; surface in grid card and review footer.
- done: document `/api/media-items/stream` in docs/api/reference.md; removed the legacy `/api/media-items` polling endpoint (Option B: consolidate to stream only).
- planned: add per-status item counts to filter labels (e.g. "Unseen (47)") via a lightweight summary endpoint.
- planned: batch actions — multi-select grid items and apply seen/trash/lock in one operation.
- planned: review progress indicator — show remaining-unseen counter or thin progress bar in the review dialog header.
- planned: single-level undo — store last action+item in React state; show an Undo button in the review toolbar for ~5 seconds after any action.
- planned: remove review path — `DELETE /api/review-paths` endpoint and Remove button in the sidebar path list.
- planned: quick-jump to next locked item — toolbar button in review mode to skip forward to the next locked item without changing the status filter.
- planned: prevent double-click action bleed in review mode — rapid clicks on lock/trash/seen buttons should not apply the resulting auto-advance to the wrong item; debounce or disable buttons during in-flight API calls.
- planned: server-side status filtering in the scan stream — the stream endpoint should accept a `statusFilter` query parameter (`unseen`, `locked`, `trashed`, `seen`, `all`) and apply it on the backend before counting against `limit`/`offset`, so the frontend receives only the items that match the active filter rather than filtering a full page post-load.
