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
- planned: add review-mode navigation and fullscreen media playback UI.
- planned: add deletion queue endpoints and cancellation support.
- planned: package the single-host deployment path for Docker and NAS usage.
