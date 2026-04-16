---
layout: default
title: Media Reviewer
nav_order: 1
---

# Media Reviewer

A lightweight, mobile-first web application for reviewing and sorting large sets of images and
videos. No separate database required — companion sidecar files track item state on disk.

## Features

- Add media folders via the web UI; state persists in `~/.mediareviewer`
- Grid view with thumbnail previews and per-status counts
- Fullscreen review mode with keyboard shortcuts, swipe navigation, and auto-advance
- Lock, trash, seen, and unseen companion-file actions with single-level undo
- Batch multi-select actions (long-press to enter selection mode)
- Async deletion queue with progress tracking and cancellation
- Configurable video preload size, light/dark/system theme

## Documentation

- [API Reference](api/reference) — full endpoint specification
- [Architecture Diagrams](architecture) — system component and data-flow diagrams
- [Lint Notes](lint-notes) — coding anti-patterns to avoid

## Quick Start

```bash
# Clone and start development servers
git clone https://github.com/mdmoore25404/mediareviewer.git
cd mediareviewer
./dev.sh start
```

See the [README](https://github.com/mdmoore25404/mediareviewer#readme) for full setup
instructions including Docker deployment.

## License

[Business Source License 1.1](https://github.com/mdmoore25404/mediareviewer/blob/main/LICENSE.md) —
converts to Apache 2.0 on 2030-04-15.
