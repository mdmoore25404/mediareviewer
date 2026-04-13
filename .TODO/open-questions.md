# Design Notes And Open Questions

## Answered for the first slice

- initial slice: project scaffold only.
- metadata strategy: plan for a media probing library in the scan implementation slice.
- deletion worker model: in-process thread queue.
- path restrictions: start with conservative hidden system paths and make them configurable.
- deployment focus: local development first.

## Still open

- image metadata probing uses Pillow; decide whether to add dedicated video duration/dimension probing via ffprobe.
- decide whether hidden-path configuration should be allowlist-first or blocklist-first in the long term.
- server-side pagination: answered — offset-based NDJSON streaming with infinite scroll is in place.
- deletion queue is currently a counter-only placeholder; decide whether async worker-based deletion is needed or whether the synchronous empty-trash endpoint is sufficient for the target use case.
- `GET /api/media-items/stream` is now documented; the legacy `/api/media-items` polling endpoint has been removed. Resolved — Option B (consolidate to stream only).
