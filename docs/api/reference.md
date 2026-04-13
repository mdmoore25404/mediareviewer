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

## GET /api/folders

Returns immediate child folders under a parent directory. Hidden folders (starting with `.`) are excluded.

### Query Parameters

- `path` (required): absolute path must be an existing directory.

### Response

```json
{
  "path": "/home/michaelmoore/reviews",
  "folders": [
    {
      "path": "/home/michaelmoore/reviews/trip-2025",
      "name": "trip-2025",
      "has_children": true
    },
    {
      "path": "/home/michaelmoore/reviews/archive-2024",
      "name": "archive-2024",
      "has_children": false
    }
  ]
}
```

### Notes

- Folders starting with `.` are hidden and excluded from results.
- `has_children` indicates whether the folder contains any non-hidden subfolders.
- Folders are sorted alphabetically by name.

### Errors

- `400`: missing `path` parameter or path does not exist or is not a directory.
- `403`: path is hidden by picker policy (e.g., under `/proc`, `/sys`).

## GET /api/folders/files

Returns paginated media files (images and videos only) in a single folder, non-recursive. Includes thumbnails.

### Query Parameters

- `path` (required): absolute folder path which must be under a configured known review path.
- `offset` (optional): integer >= 0, default `0`. Number of files to skip.
- `limit` (optional): integer from `1` to `1000`, default `100`. Maximum files to return.

### Response

```json
{
  "path": "/home/michaelmoore/reviews/trip-2025",
  "offset": 0,
  "limit": 100,
  "count": 15,
  "ignoredCount": 3,
  "items": [
    {
      "path": "/home/michaelmoore/reviews/trip-2025/day1/photo001.jpg",
      "name": "photo001.jpg",
      "mediaType": "image",
      "thumbnailUrl": "/api/media-thumbnail?path=%2Fhome%2Fmichaelmoore%2Freviews%2Ftrip-2025%2Fday1%2Fphoto001.jpg&size=256",
      "sizeBytes": 2048576,
      "modifiedAt": "2025-03-15T14:30:22.000000+00:00",
      "createdAt": "2025-03-15T14:30:22.000000+00:00",
      "status": {
        "locked": false,
        "trashed": false,
        "seen": false
      },
      "metadata": {
        "width": 4096,
        "height": 3072
      }
    }
  ]
}
```

### Notes

- Only image and video files are returned; other file types and companion files (`.lock`, `.trash`, `.seen`) are ignored.
- `ignoredCount` indicates non-media files encountered during scan.
- Results are sorted alphabetically by filename.
- Each item includes `thumbnailUrl` pointing to the cached thumbnail.
- Pagination is supported via `offset` and `limit` parameters for large folders.

### Errors

- `400`: missing `path`, invalid `offset` (negative), or invalid `limit` (zero, negative, or > 1000).
- `403`: folder path is not under a configured known review path.

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
      "thumbnailUrl": "/api/media-thumbnail?path=%2Fhome%2Fmichaelmoore%2Ftrailcam%2FDCIM%2F100MEDIA%2Fframe001.jpg&size=256",
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

### Notes

- Each item includes `thumbnailUrl`, which points at the disk-backed thumbnail cache.
- On Linux, generated thumbnails use the freedesktop thumbnail cache layout under `~/.cache/thumbnails` by default.
- On macOS and Windows, thumbnails are cached under the Media Reviewer state directory unless `MEDIAREVIEWER_THUMBNAIL_CACHE_DIR` overrides the location.

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
- `unlock`: removes `.lock`.
- `trash`: creates `.trash`, creates `.seen` (trash implies seen), and removes `.lock`.
- `untrash`: removes `.trash`.
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
    "seen": true
  }
}
```

### Errors

- `400`: request body invalid, unsupported action, or media path missing.
- `403`: media path is outside configured known review paths.

## GET /api/media-file

Streams an image or video file under a configured review path for fullscreen review mode.

### Query Parameters

- `path` (required): absolute media file path under a configured known review root.

### Behavior

- Image and video files can be streamed directly for fullscreen review playback.
- Access is denied for files outside configured review paths.

### Errors

- `400`: missing `path` or file does not exist.
- `403`: file is outside configured known review paths.

## GET /api/media-thumbnail

Serves a PNG thumbnail from the on-disk cache, generating it if needed.

### Query Parameters

- `path` (required): absolute media file path under a configured known review root.
- `size` (optional): integer from `1` to `1024`, default `256`.

### Behavior

- Image files are resized into a square PNG thumbnail.
- Video files currently receive a generated placeholder thumbnail when no system thumbnail is already available.
- On Linux, the cache location follows the freedesktop thumbnail directory convention by default.
- On macOS and Windows, Media Reviewer uses its own cache directory because native file-explorer thumbnail caches are not public, stable integration points.

### Errors

- `400`: missing `path`, invalid `size`, or file does not exist.
- `403`: file is outside configured known review paths.