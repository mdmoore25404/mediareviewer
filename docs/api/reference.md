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

## GET /api/review-paths

Returns known review paths from `~/.mediareviewer/config.yaml` plus active hidden picker paths.

### Response

```json
{
  "knownPaths": ["/home/michaelmoore/trailcam"],
  "hiddenPickerPaths": ["/proc", "/sys"]
}
```

## POST /api/review-paths

Adds and persists a known review path.

### Request

```json
{
  "path": "/home/michaelmoore/trailcam"
}
```

### Success Response

```json
{
  "addedPath": "/home/michaelmoore/trailcam",
  "knownPaths": ["/home/michaelmoore/trailcam"]
}
```

### Errors

- `400`: request body missing or `path` invalid.
- `403`: path is under hidden picker policy.

## GET /api/media-items

Scans a known review path recursively and returns image/video files only. Companion state files and non-media files are ignored.

### Query Parameters

- `path` (required): absolute path that must already exist in `knownPaths`.
- `limit` (optional): integer from `1` to `10000`, default `1000`.

### Response

```json
{
  "path": "/home/michaelmoore/trailcam",
  "count": 2,
  "ignoredCount": 4,
  "items": [
    {
      "path": "/home/michaelmoore/trailcam/DCIM/100MEDIA/frame001.jpg",
      "name": "frame001.jpg",
      "mediaType": "image",
      "sizeBytes": 154323,
      "modifiedAt": "2026-04-12T21:50:19.123456+00:00",
      "createdAt": "2026-04-12T21:50:19.123456+00:00",
      "status": {
        "locked": false,
        "trashed": false,
        "seen": true
      },
      "metadata": {
        "width": 1920,
        "height": 1080
      }
    }
  ]
}
```

### Errors

- `400`: missing required `path` query parameter or invalid `limit`.
- `403`: path is not in configured known review paths.

## POST /api/media-actions

Applies a companion-file state action to a media file under a known review path.

### Request

```json
{
  "path": "/home/michaelmoore/trailcam/DCIM/100MEDIA/clip001.mp4",
  "action": "trash"
}
```

### Actions

- `lock`: creates `.lock` and removes `.trash`.
- `trash`: creates `.trash` and removes `.lock`.
- `seen`: creates `.seen`.
- `unseen`: removes `.seen`.

### Success Response

```json
{
  "path": "/home/michaelmoore/trailcam/DCIM/100MEDIA/clip001.mp4",
  "action": "trash",
  "status": {
    "locked": false,
    "trashed": true,
    "seen": false
  }
}
```

### Errors

- `400`: request body invalid, unsupported action, or media path missing.
- `403`: media path is outside configured known review paths.

## GET /api/media-file

Streams an image or video file under a configured review path for thumbnail display and fullscreen review mode.

### Query Parameters

- `path` (required): absolute media file path under a configured known review root.

### Behavior

- Image files can be used directly in `<img>` previews.
- Video files can be used directly in `<video>` previews and fullscreen review playback.
- Access is denied for files outside configured review paths.

### Errors

- `400`: missing `path` or file does not exist.
- `403`: file is outside configured known review paths.