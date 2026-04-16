import type {
  AddReviewPathResponse,
  AppSettingsResponse,
  BatchActionResponse,
  FolderFilesResponse,
  FoldersResponse,
  HealthResponse,
  LogsResponse,
  MediaAction,
  MediaActionResponse,
  MediaItem,
  MediaStreamDone,
  RemoveReviewPathResponse,
  ReviewPathsResponse,
  StatusFilter,
  StatusSummary,
  TrashProgressEvent,
} from "./types";

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorPayload = (await response.json().catch(() => null)) as { error?: string } | null;
    const details = errorPayload?.error ?? `Request failed with status ${response.status}.`;
    throw new Error(details);
  }
  return (await response.json()) as T;
}

/** Fetch the current API status used by the initial application shell. */
export async function fetchHealth(signal: AbortSignal): Promise<HealthResponse> {
  const response = await fetch("/api/health", {
    headers: {
      Accept: "application/json",
    },
    signal,
  });

  return parseJsonResponse<HealthResponse>(response);
}

/** Fetch configured review paths and hidden picker path policies. */
export async function fetchReviewPaths(signal: AbortSignal): Promise<ReviewPathsResponse> {
  const response = await fetch("/api/review-paths", {
    headers: {
      Accept: "application/json",
    },
    signal,
  });
  return parseJsonResponse<ReviewPathsResponse>(response);
}

/** Add and persist a new review path. */
export async function addReviewPath(path: string): Promise<AddReviewPathResponse> {
  const response = await fetch("/api/review-paths", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ path }),
  });
  return parseJsonResponse<AddReviewPathResponse>(response);
}

/** Remove a configured review path from the persisted known-paths list. */
export async function removeReviewPath(path: string): Promise<RemoveReviewPathResponse> {
  const response = await fetch("/api/review-paths", {
    method: "DELETE",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ path }),
  });
  return parseJsonResponse<RemoveReviewPathResponse>(response);
}

/** Fetch per-status item counts for a review path without streaming items. */
export async function fetchStatusSummary(
  path: string,
  signal: AbortSignal,
): Promise<StatusSummary> {
  const url = `/api/media-items/summary?path=${encodeURIComponent(path)}`;
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    signal,
  });
  return parseJsonResponse<StatusSummary>(response);
}

/**
 * Stream media items from the NDJSON scan endpoint.
 *
 * Yields each {@link MediaItem} as soon as it is received.  The final value
 * is a {@link MediaStreamDone} sentinel with the total item count confirmed by
 * the server and the ``lastPath`` cursor needed for the next page.
 * Throws on non-2xx responses or network errors.
 *
 * Pass the ``lastPath`` from the previous {@link MediaStreamDone} event as
 * ``after`` to resume from the exact filesystem position where the previous
 * page ended.  This cursor-based approach is safe across concurrent reviews
 * because it tracks scan position, not filter-subset position.
 */
export async function* streamMediaItems(
  path: string,
  limit: number,
  signal: AbortSignal,
  offset = 0,
  statusFilter: StatusFilter = "all",
  after?: string,
): AsyncGenerator<MediaItem | MediaStreamDone> {
  const params: Record<string, string> = {
    path,
    limit: String(limit),
    offset: String(offset),
    statusFilter,
  };
  if (after !== undefined) {
    params.after = after;
  }
  const search = new URLSearchParams(params);
  const response = await fetch(`/api/media-items/stream?${search.toString()}`, {
    headers: { Accept: "application/x-ndjson" },
    signal,
  });
  if (!response.ok || !response.body) {
    const errorPayload = (await response.json().catch(() => null)) as { error?: string } | null;
    const details = errorPayload?.error ?? `Scan failed with status ${response.status}.`;
    throw new Error(details);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed) {
        yield JSON.parse(trimmed) as MediaItem | MediaStreamDone;
      }
    }
  }
  // Flush any remaining buffered content after the stream closes
  const remaining = buffer.trim();
  if (remaining) {
    yield JSON.parse(remaining) as MediaItem | MediaStreamDone;
  }
}

/** Apply lock/trash/seen/unseen state to a media item companion file set. */
export async function applyMediaAction(path: string, action: MediaAction): Promise<MediaActionResponse> {
  const response = await fetch("/api/media-actions", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ path, action }),
  });
  return parseJsonResponse<MediaActionResponse>(response);
}

/** Build a media streaming URL for fullscreen review mode. */
export function buildMediaFileUrl(path: string): string {
  const search = new URLSearchParams({ path });
  return `/api/media-file?${search.toString()}`;
}

/** Build a cached thumbnail URL for grid and list previews. */
export function buildMediaThumbnailUrl(path: string, size: number): string {
  const search = new URLSearchParams({ path, size: String(size) });
  return `/api/media-thumbnail?${search.toString()}`;
}

/** Stream NDJSON progress events from the empty-trash endpoint. */
export async function* streamEmptyTrash(
  path: string,
  signal: AbortSignal,
): AsyncGenerator<TrashProgressEvent> {
  const response = await fetch("/api/empty-trash", {
    method: "POST",
    headers: { Accept: "application/x-ndjson", "Content-Type": "application/json" },
    body: JSON.stringify({ path }),
    signal,
  });
  if (!response.ok || !response.body) {
    const errorPayload = (await response.json().catch(() => null)) as { error?: string } | null;
    const details = errorPayload?.error ?? `Empty trash failed with status ${response.status}.`;
    throw new Error(details);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed) {
        yield JSON.parse(trimmed) as TrashProgressEvent;
      }
    }
  }
  const remaining = buffer.trim();
  if (remaining) {
    yield JSON.parse(remaining) as TrashProgressEvent;
  }
}

/** Fetch immediate child folders under a parent directory. */
export async function fetchFolders(path: string, signal: AbortSignal): Promise<FoldersResponse> {
  const search = new URLSearchParams({ path });
  const response = await fetch(`/api/folders?${search.toString()}`, {
    headers: {
      Accept: "application/json",
    },
    signal,
  });
  return parseJsonResponse<FoldersResponse>(response);
}

/** Fetch paginated media files in a single folder. */
export async function fetchFolderFiles(
  path: string,
  offset = 0,
  limit = 100,
  signal?: AbortSignal
): Promise<FolderFilesResponse> {
  const search = new URLSearchParams({
    path,
    offset: String(offset),
    limit: String(limit),
  });
  const response = await fetch(`/api/folders/files?${search.toString()}`, {
    headers: {
      Accept: "application/json",
    },
    signal,
  });
  return parseJsonResponse<FolderFilesResponse>(response);
}

/** Fetch the tail of the server log file. */
export async function fetchLogs(signal: AbortSignal, lines = 200): Promise<LogsResponse> {
  const response = await fetch(`/api/logs?lines=${lines}`, {
    headers: { Accept: "application/json" },
    signal,
  });
  return parseJsonResponse<LogsResponse>(response);
}

export async function fetchSettings(signal: AbortSignal): Promise<AppSettingsResponse> {
  const response = await fetch("/api/settings", {
    headers: { Accept: "application/json" },
    signal,
  });
  return parseJsonResponse<AppSettingsResponse>(response);
}

export async function patchSettings(
  patch: Partial<AppSettingsResponse>,
  signal: AbortSignal,
): Promise<AppSettingsResponse> {
  const response = await fetch("/api/settings", {
    method: "PATCH",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(patch),
    signal,
  });
  return parseJsonResponse<AppSettingsResponse>(response);
}

export async function applyBatchAction(
  paths: string[],
  action: MediaAction,
  signal: AbortSignal,
): Promise<BatchActionResponse> {
  const response = await fetch("/api/media-items/batch", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ paths, action }),
    signal,
  });
  return parseJsonResponse<BatchActionResponse>(response);
}
