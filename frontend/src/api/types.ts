export interface HealthSettings {
  stateDirectory: string;
  hiddenPickerPaths: string[];
  deletionWorkers: number;
}

export interface DeletionQueueSnapshot {
  max_workers: number;
  active_jobs: number;
  submitted_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
}

export interface HealthResponse {
  status: string;
  service: string;
  settings: HealthSettings;
  deletionQueue: DeletionQueueSnapshot;
}

export interface ReviewPathsResponse {
  knownPaths: string[];
  hiddenPickerPaths: string[];
}

export interface AddReviewPathResponse {
  addedPath: string;
  knownPaths: string[];
}

export interface MediaStatus {
  locked: boolean;
  trashed: boolean;
  seen: boolean;
}

export interface MediaMetadata {
  width: number | null;
  height: number | null;
}

export interface MediaItem {
  path: string;
  name: string;
  mediaType: "image" | "video";
  thumbnailUrl: string;
  sizeBytes: number;
  modifiedAt: string;
  createdAt: string;
  status: MediaStatus;
  metadata: MediaMetadata;
}

export interface MediaItemsResponse {
  path: string;
  count: number;
  ignoredCount: number;
  items: MediaItem[];
}

export type MediaAction = "lock" | "unlock" | "trash" | "untrash" | "seen" | "unseen";

export interface MediaActionResponse {
  path: string;
  action: MediaAction;
  status: MediaStatus;
}

export interface EmptyTrashResponse {
  deleted: number;
  paths: string[];
  errors: string[];
}

export interface FolderInfo {
  path: string;
  name: string;
  has_children: boolean;
}

export interface FoldersResponse {
  path: string;
  folders: FolderInfo[];
}

export interface FolderFilesResponse {
  path: string;
  offset: number;
  limit: number;
  count: number;
  ignoredCount: number;
  items: MediaItem[];
}

/** Final line of a ``/api/media-items/stream`` NDJSON response. */
export interface MediaStreamDone {
  type: "done";
  count: number;
}
