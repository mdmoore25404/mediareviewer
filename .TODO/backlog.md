# Media Reviewer Backlog

## Completed

- done: initialize git repository.
- done: add workspace instructions and coding standards.
- done: scaffold backend, frontend, documentation, and test tooling.
- done: establish the first vertical foundation with typed config and health status.
- done: persist review folder settings under `~/.mediareviewer`.
- done: add folder picker API with hidden-path enforcement.
- done: scan media folders and return typed review item summaries.
- done: implement companion file actions for `lock`, `trash`, and `seen`.
- done: implement frontend review-path management and media browser controls.
- done: wire frontend companion state actions for lock/trash/seen/unseen.
- done: document architecture portability and Docker multi-arch manifest expectations.
- done: configure dev listen/ports through `~/.mediareviewer/config.yaml` and `dev.sh`.
- done: add committed backend requirements files and YAML trusted-host support.
- done: add deletion queue placeholder; implement synchronous empty-trash endpoint.
- done: package the single-host deployment path for Docker and NAS usage (Dockerfile + docker-compose).
- done: stream NDJSON scan results with offset pagination and infinite scroll.
- done: review mode UX polish (status indicators, auto-advance, mobile layout, keyboard shortcuts, help panel).
- done: locked-item trash prevention (backend 409 + frontend warning modal).
- done: document `/api/media-items/stream`; removed legacy `/api/media-items` polling endpoint.
- done: server-side status filtering in the scan stream (`statusFilter` query param, applied before limit/offset).
- done: fix video thumbnail generation — stale-placeholder mtime=0 retry; TimeoutExpired catch; tempfile.mkstemp race fix; `prune_orphaned_thumbnails`; background warm thread on scan.

## Planned

- done: add theme mode toggle with light, dark, and auto(system) options.
- planned: probe video duration and dimensions with ffprobe during scan; surface in grid card and review footer.
- done: auto-generate thumbnails in background when a new known path is added; configurable via `~/.mediareviewer/config.yaml` key `auto_thumbnail_on_add` (default `true`); runs as an async background thread using the same warm-thumbnail worker already used during scan.
- planned: add per-status item counts to filter labels (e.g. "Unseen (47)") via a lightweight summary endpoint.
- planned: batch actions — multi-select grid items and apply seen/trash/lock in one operation.
- planned: review progress indicator — show remaining-unseen counter or thin progress bar in the review dialog header.
- planned: single-level undo — store last action+item in React state; show an Undo button in the review toolbar for ~5 seconds after any action.
- done: remove review path — `DELETE /api/review-paths` endpoint and Remove button in the sidebar path list.
- planned: quick-jump to next locked item — toolbar button in review mode to skip forward to the next locked item without changing the status filter.
- planned: prevent double-click action bleed in review mode — debounce or disable buttons during in-flight API calls.
- planned: generate and maintain Mermaid architecture diagrams in `docs/` via a script or agent skill; re-runnable after structural changes.
- planned: remove trailcam-specific language from the UI — replace with generic copy for any batch-review workflow.
- done: video playback mini-controls in review mode — −5 s / +5 s skip, pause/play toggle, mute toggle; playback-speed selector (0.5×, 1×, 1.5×, 2×, 4×) persisted in `sessionStorage`; control group disabled for image items.
- done: strip the review-path prefix from file paths shown in the review dialog and grid cards; display only the relative path beneath the root.
- done: compact landscape info row — file size and modified timestamp on the same line as the filename in a smaller font to give more vertical space to the media preview.
- planned: expose `video_preload_mb` as a configurable setting via `GET/PATCH /api/settings` endpoint and a settings panel in the frontend UI; currently only configurable via YAML (`~/.mediareviewer/config.yaml`) or environment variable (`MEDIAREVIEWER_VIDEO_PRELOAD_MB`).

## Planned (cont.)

- done: DCIM-aware incremental scan walk — for paths that follow DCF/DCIM conventions
  (``DCIM/NNNxxxxx/`` structure), filename order is equivalent to modified-date order, so
  ``sorted(rglob("*"))`` can be replaced with an incremental ``os.walk``-based walk that yields
  files immediately without materialising the full path list first.  This reduces first-item
  latency for large SD-card scans and avoids peak memory proportional to total file count.
  The optimised walk should also prune hidden directories before descending (instead of
  filtering after discovery) and log when DCIM structure is detected.  Detect three forms:
  (1) path itself is ``DCIM/`` with numbered subdirs, (2) path is a numbered DCIM subdir
  inside a ``DCIM/`` parent, (3) path contains an immediate ``DCIM/`` child with numbered
  subdirs.  Fall back to the existing ``sorted(rglob)`` path for non-DCIM roots.

## Stretch goals

- stretch: AI-assisted media description on the fly — opt-in, non-blocking one-line AI tag summary in the review dialog and grid card.
