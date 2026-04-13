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
