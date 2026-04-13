---
layout: default
title: Media Reviewer API Reference
---

# Media Reviewer API Reference

## GET /api/health

Returns a typed status payload used by the frontend shell to confirm API availability and expose baseline configuration values.

### Response

```json
{
  "status": "ok",
  "service": "mediareviewer-api",
  "settings": {
    "stateDirectory": "/home/example/.mediareviewer",
    "hiddenPickerPaths": ["/proc", "/sys"],
    "deletionWorkers": 2
  },
  "deletionQueue": {
    "max_workers": 2,
    "active_jobs": 0,
    "submitted_jobs": 0,
    "completed_jobs": 0,
    "failed_jobs": 0
  }
}
```

### Notes

- `settings.hiddenPickerPaths` exposes the current conservative hidden-path defaults for the folder picker.
- `deletionQueue` is currently a scaffolded placeholder for the future async trash-empty workflow.