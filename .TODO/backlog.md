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
- planned: generate and maintain Mermaid architecture diagrams in `docs/` — create a script (Python or bash) or a `.github/instructions`-backed agent skill that renders system, data-flow, and component diagrams as `.md` files containing Mermaid fences; diagrams must be re-runnable on demand so they stay current after major changes; output lives alongside the existing API reference in `docs/`; suitable for both human readers and AI agents parsing the repo structure.
- planned: remove trailcam-specific language from the UI — any hardcoded references to "trailcam" in labels, placeholders, or help text should be replaced with generic copy that suits any batch-review workflow (wildlife cameras, SD card culling, photo review, etc.).
- planned: video playback mini-controls in review mode — add −5 s / +5 s skip buttons, a single pause/play toggle, and a mute/unmute toggle so the user doesn't need to enable full native controls for basic navigation; add a playback-speed selector with values 1×, 2×, 4×, 8× (no faster makes sense for triage use); persist the chosen speed in `sessionStorage` so it survives item-to-item auto-advance within a session; disable the entire video-controls group when the active review item is an image.
- planned: strip the review-path prefix from file paths shown in the review dialog and grid cards — the user already knows which root they are reviewing; display only the relative path beneath the root (e.g. `DCIM/100MEDIA/DSCF0438.MP4` instead of the full `/mnt/…` string).
- planned: compact landscape info row in review dialog — in landscape / wider viewports, display the file size and last-modified timestamp on the same line as the filename using a smaller secondary font so more vertical space is available for the media preview.
- stretch: AI-assisted media description on the fly — surface a one-line AI-generated description or tag summary for each image/video in the review dialog and grid card; should be opt-in and non-blocking so the UI remains fast without an AI backend.
- done: server-side status filtering in the scan stream — the stream endpoint should accept a `statusFilter` query parameter (`unseen`, `locked`, `trashed`, `seen`, `all`) and apply it on the backend before counting against `limit`/`offset`, so the frontend receives only the items that match the active filter rather than filtering a full page post-load.
