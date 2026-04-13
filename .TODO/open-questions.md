# Design Notes And Open Questions

## Answered for the first slice

- initial slice: project scaffold only.
- metadata strategy: plan for a media probing library in the scan implementation slice.
- deletion worker model: in-process thread queue.
- path restrictions: start with conservative hidden system paths and make them configurable.
- deployment focus: local development first.

## Still open

- choose the exact metadata probing toolchain for still images and videos.
- decide whether hidden-path configuration should be allowlist-first or blocklist-first in the long term.
- define the review item pagination and caching strategy once media scanning exists.
