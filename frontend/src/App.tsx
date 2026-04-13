import { type KeyboardEvent, type ReactElement, useEffect, useMemo, useState } from "react";

import {
  addReviewPath,
  applyMediaAction,
  buildMediaFileUrl,
  buildMediaThumbnailUrl,
  fetchHealth,
  fetchMediaItems,
  fetchReviewPaths,
} from "./api/client";
import type { HealthResponse, MediaAction, MediaItem } from "./api/types";

type ViewMode = "grid" | "list";
type StatusFilter = "all" | "locked" | "trashed" | "seen" | "unseen";
type MediaFilter = "all" | "image" | "video";
type SortOption = "modified-desc" | "modified-asc" | "size-desc" | "size-asc" | "name-asc";

function sortMediaItems(items: MediaItem[], sortOption: SortOption): MediaItem[] {
  const sorted = [...items];
  sorted.sort((left, right) => {
    if (sortOption === "name-asc") {
      return left.name.localeCompare(right.name);
    }
    if (sortOption === "size-desc") {
      return right.sizeBytes - left.sizeBytes;
    }
    if (sortOption === "size-asc") {
      return left.sizeBytes - right.sizeBytes;
    }

    const leftDate = new Date(left.modifiedAt).getTime();
    const rightDate = new Date(right.modifiedAt).getTime();
    if (sortOption === "modified-asc") {
      return leftDate - rightDate;
    }
    return rightDate - leftDate;
  });
  return sorted;
}

function formatSize(sizeBytes: number): string {
  if (sizeBytes < 1024) {
    return `${sizeBytes} B`;
  }
  const kib = sizeBytes / 1024;
  if (kib < 1024) {
    return `${kib.toFixed(1)} KiB`;
  }
  const mib = kib / 1024;
  if (mib < 1024) {
    return `${mib.toFixed(1)} MiB`;
  }
  return `${(mib / 1024).toFixed(1)} GiB`;
}

function App(): ReactElement {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [knownPaths, setKnownPaths] = useState<string[]>([]);
  const [hiddenPaths, setHiddenPaths] = useState<string[]>([]);
  const [selectedPath, setSelectedPath] = useState<string>("");
  const [newPathInput, setNewPathInput] = useState<string>("/home/michaelmoore/trailcam");
  const [mediaItems, setMediaItems] = useState<MediaItem[]>([]);
  const [ignoredCount, setIgnoredCount] = useState<number>(0);
  const [scanLimit, setScanLimit] = useState<number>(200);
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [mediaFilter, setMediaFilter] = useState<MediaFilter>("all");
  const [sortOption, setSortOption] = useState<SortOption>("modified-desc");
  const [isBootLoading, setIsBootLoading] = useState<boolean>(true);
  const [isScanLoading, setIsScanLoading] = useState<boolean>(false);
  const [isSubmittingPath, setIsSubmittingPath] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [activeReviewPath, setActiveReviewPath] = useState<string | null>(null);
  const [touchStartX, setTouchStartX] = useState<number | null>(null);
  const [touchStartY, setTouchStartY] = useState<number | null>(null);

  useEffect(() => {
    const abortController = new AbortController();

    const loadBootstrap = async (): Promise<void> => {
      try {
        const [healthPayload, pathsPayload] = await Promise.all([
          fetchHealth(abortController.signal),
          fetchReviewPaths(abortController.signal),
        ]);
        setHealth(healthPayload);
        setKnownPaths(pathsPayload.knownPaths);
        setHiddenPaths(pathsPayload.hiddenPickerPaths);
        if (pathsPayload.knownPaths.length > 0) {
          setSelectedPath(pathsPayload.knownPaths[0]);
        }
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "Unable to load API status.";
        setErrorMessage(message);
      } finally {
        setIsBootLoading(false);
      }
    };

    void loadBootstrap();
    return () => {
      abortController.abort();
    };
  }, []);

  const displayedItems = useMemo(() => {
    const filteredByMedia = mediaItems.filter((item) => {
      if (mediaFilter === "all") {
        return true;
      }
      return item.mediaType === mediaFilter;
    });

    const filteredByStatus = filteredByMedia.filter((item) => {
      if (statusFilter === "all") {
        return true;
      }
      if (statusFilter === "locked") {
        return item.status.locked;
      }
      if (statusFilter === "trashed") {
        return item.status.trashed;
      }
      if (statusFilter === "seen") {
        return item.status.seen;
      }
      return !item.status.seen;
    });

    return sortMediaItems(filteredByStatus, sortOption);
  }, [mediaFilter, mediaItems, sortOption, statusFilter]);

  const activeReviewIndex = useMemo(() => {
    if (!activeReviewPath) {
      return -1;
    }
    return displayedItems.findIndex((item) => item.path === activeReviewPath);
  }, [activeReviewPath, displayedItems]);

  const activeReviewItem = activeReviewIndex >= 0 ? displayedItems[activeReviewIndex] : null;

  useEffect(() => {
    if (activeReviewPath && activeReviewIndex === -1) {
      setActiveReviewPath(null);
    }
  }, [activeReviewIndex, activeReviewPath]);

  useEffect(() => {
    if (!activeReviewItem) {
      return undefined;
    }

    const handleKeyDown = (event: globalThis.KeyboardEvent): void => {
      if (event.key === "Escape") {
        setActiveReviewPath(null);
        return;
      }
      if (event.key === "ArrowRight") {
        setActiveReviewPath(displayedItems[(activeReviewIndex + 1) % displayedItems.length]?.path ?? null);
        return;
      }
      if (event.key === "ArrowLeft") {
        const nextIndex = activeReviewIndex === 0 ? displayedItems.length - 1 : activeReviewIndex - 1;
        setActiveReviewPath(displayedItems[nextIndex]?.path ?? null);
        return;
      }
      if (event.key.toLowerCase() === "d" || event.key.toLowerCase() === "t") {
        void handleMediaAction(activeReviewItem.path, "trash");
        return;
      }
      if (event.key.toLowerCase() === "s") {
        void handleMediaAction(activeReviewItem.path, "seen");
        return;
      }
      if (event.key.toLowerCase() === "f" || event.key.toLowerCase() === "l") {
        void handleMediaAction(activeReviewItem.path, "lock");
        return;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [activeReviewIndex, activeReviewItem, displayedItems]);

  const handleScan = async (): Promise<void> => {
    if (!selectedPath) {
      setErrorMessage("Pick a review path before scanning.");
      return;
    }
    setIsScanLoading(true);
    setStatusMessage(null);
    setErrorMessage(null);
    try {
      const payload = await fetchMediaItems(selectedPath, scanLimit);
      setMediaItems(payload.items);
      setIgnoredCount(payload.ignoredCount);
      setStatusMessage(
        `Loaded ${payload.count} media items from ${payload.path}. Ignored ${payload.ignoredCount} non-media or companion files.`,
      );
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Unable to scan review path.";
      setErrorMessage(message);
    } finally {
      setIsScanLoading(false);
    }
  };

  const handleAddPath = async (): Promise<void> => {
    if (!newPathInput.trim()) {
      setErrorMessage("Enter a path to add.");
      return;
    }

    setIsSubmittingPath(true);
    setStatusMessage(null);
    setErrorMessage(null);
    try {
      const payload = await addReviewPath(newPathInput.trim());
      setKnownPaths(payload.knownPaths);
      if (!selectedPath && payload.knownPaths.length > 0) {
        setSelectedPath(payload.knownPaths[0]);
      }
      setStatusMessage(`Added review path: ${payload.addedPath}`);
      setNewPathInput("");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Unable to add review path.";
      setErrorMessage(message);
    } finally {
      setIsSubmittingPath(false);
    }
  };

  const handleMediaAction = async (itemPath: string, action: MediaAction): Promise<void> => {
    setErrorMessage(null);
    try {
      const payload = await applyMediaAction(itemPath, action);
      setMediaItems((previous) =>
        previous.map((item) =>
          item.path === payload.path
            ? {
                ...item,
                status: payload.status,
              }
            : item,
        ),
      );
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Unable to apply media action.";
      setErrorMessage(message);
    }
  };

  const openReviewMode = (itemPath: string): void => {
    setActiveReviewPath(itemPath);
  };

  const handleCardKeyDown = (event: KeyboardEvent<HTMLElement>, itemPath: string): void => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openReviewMode(itemPath);
    }
  };

  const showPreviousReviewItem = (): void => {
    if (displayedItems.length === 0 || activeReviewIndex === -1) {
      return;
    }
    const nextIndex = activeReviewIndex === 0 ? displayedItems.length - 1 : activeReviewIndex - 1;
    setActiveReviewPath(displayedItems[nextIndex]?.path ?? null);
  };

  const showNextReviewItem = (): void => {
    if (displayedItems.length === 0 || activeReviewIndex === -1) {
      return;
    }
    setActiveReviewPath(displayedItems[(activeReviewIndex + 1) % displayedItems.length]?.path ?? null);
  };

  const handleReviewTouchStart = (touchX: number, touchY: number): void => {
    setTouchStartX(touchX);
    setTouchStartY(touchY);
  };

  const handleReviewTouchEnd = (touchX: number, touchY: number): void => {
    if (touchStartX === null || touchStartY === null) {
      return;
    }

    const deltaX = touchX - touchStartX;
    const deltaY = touchY - touchStartY;
    const horizontalThreshold = 60;

    setTouchStartX(null);
    setTouchStartY(null);

    if (Math.abs(deltaX) < horizontalThreshold || Math.abs(deltaX) < Math.abs(deltaY)) {
      return;
    }

    if (deltaX < 0) {
      showNextReviewItem();
      return;
    }

    showPreviousReviewItem();
  };

  const renderMediaPreview = (item: MediaItem, className: string): ReactElement => {
    const thumbnailUrl = item.thumbnailUrl || buildMediaThumbnailUrl(item.path, 256);
    return <img className={className} src={thumbnailUrl} alt={item.name} loading="lazy" />;
  };

  return (
    <main className="app-shell">
      <section className="container py-4 py-lg-5">
        <header className="status-card mb-4">
          <div className="d-flex flex-column flex-lg-row justify-content-between gap-3 align-items-start">
            <div>
              <p className="eyebrow">Media Reviewer Prototype</p>
              <h1 className="display-6 fw-semibold mb-2">Trailcam review dashboard</h1>
              <p className="mb-0 text-secondary">
                Manage review roots, scan recursively, and set lock or trash decisions from one
                screen.
              </p>
            </div>
            <div className="summary-pill">
              <i className="fa-solid fa-leaf me-2" aria-hidden="true" />
              low-resource mode
            </div>
          </div>
        </header>

        {isBootLoading && <p>Loading API and path configuration...</p>}

        {!isBootLoading && (
          <div className="row g-4">
            <aside className="col-12 col-xl-4">
              <section className="status-card h-100">
                <h2 className="h5 mb-3">Review paths</h2>
                <div className="input-group mb-2">
                  <input
                    value={newPathInput}
                    onChange={(event) => {
                      setNewPathInput(event.target.value);
                    }}
                    className="form-control"
                    placeholder="/home/michaelmoore/trailcam"
                    aria-label="Path to add"
                  />
                  <button
                    type="button"
                    className="btn btn-outline-primary"
                    onClick={() => {
                      void handleAddPath();
                    }}
                    disabled={isSubmittingPath}
                  >
                    {isSubmittingPath ? "Adding..." : "Add"}
                  </button>
                </div>
                <label className="form-label small text-uppercase text-secondary mt-3" htmlFor="known-path">
                  Known path
                </label>
                <select
                  id="known-path"
                  className="form-select"
                  value={selectedPath}
                  onChange={(event) => {
                    setSelectedPath(event.target.value);
                  }}
                >
                  <option value="">Select a path</option>
                  {knownPaths.map((path) => (
                    <option key={path} value={path}>
                      {path}
                    </option>
                  ))}
                </select>

                <div className="metric-card mt-3">
                  <p className="metric-label">API status</p>
                  <p className="metric-value mb-2">{health?.status ?? "unknown"}</p>
                  <p className="small text-secondary mb-1">
                    State directory: {health?.settings.stateDirectory ?? "-"}
                  </p>
                  <p className="small text-secondary mb-0">Hidden paths: {hiddenPaths.length}</p>
                </div>

                <details className="mt-3">
                  <summary className="small fw-semibold text-secondary">Hidden picker paths</summary>
                  <ul className="small mt-2 mb-0 ps-3">
                    {hiddenPaths.map((path) => (
                      <li key={path}>{path}</li>
                    ))}
                  </ul>
                </details>
              </section>
            </aside>

            <section className="col-12 col-xl-8">
              <div className="status-card">
                <div className="d-flex flex-column flex-lg-row gap-2 align-items-lg-end mb-3">
                  <div>
                    <label className="form-label small text-uppercase text-secondary" htmlFor="scan-limit">
                      Scan limit
                    </label>
                    <input
                      id="scan-limit"
                      type="number"
                      min={1}
                      max={10000}
                      className="form-control"
                      value={scanLimit}
                      onChange={(event) => {
                        const nextLimit = Number(event.target.value);
                        if (Number.isFinite(nextLimit)) {
                          setScanLimit(nextLimit);
                        }
                      }}
                    />
                  </div>
                  <div>
                    <label className="form-label small text-uppercase text-secondary" htmlFor="view-mode">
                      View
                    </label>
                    <select
                      id="view-mode"
                      className="form-select"
                      value={viewMode}
                      onChange={(event) => {
                        setViewMode(event.target.value as ViewMode);
                      }}
                    >
                      <option value="grid">Grid</option>
                      <option value="list">List</option>
                    </select>
                  </div>
                  <div>
                    <label className="form-label small text-uppercase text-secondary" htmlFor="media-filter">
                      Media
                    </label>
                    <select
                      id="media-filter"
                      className="form-select"
                      value={mediaFilter}
                      onChange={(event) => {
                        setMediaFilter(event.target.value as MediaFilter);
                      }}
                    >
                      <option value="all">All</option>
                      <option value="image">Images</option>
                      <option value="video">Videos</option>
                    </select>
                  </div>
                  <div>
                    <label className="form-label small text-uppercase text-secondary" htmlFor="status-filter">
                      Status
                    </label>
                    <select
                      id="status-filter"
                      className="form-select"
                      value={statusFilter}
                      onChange={(event) => {
                        setStatusFilter(event.target.value as StatusFilter);
                      }}
                    >
                      <option value="all">All</option>
                      <option value="locked">Locked</option>
                      <option value="trashed">Trashed</option>
                      <option value="seen">Seen</option>
                      <option value="unseen">Unseen</option>
                    </select>
                  </div>
                  <div>
                    <label className="form-label small text-uppercase text-secondary" htmlFor="sort-option">
                      Sort
                    </label>
                    <select
                      id="sort-option"
                      className="form-select"
                      value={sortOption}
                      onChange={(event) => {
                        setSortOption(event.target.value as SortOption);
                      }}
                    >
                      <option value="modified-desc">Newest modified</option>
                      <option value="modified-asc">Oldest modified</option>
                      <option value="size-desc">Largest first</option>
                      <option value="size-asc">Smallest first</option>
                      <option value="name-asc">Name A-Z</option>
                    </select>
                  </div>
                  <button
                    type="button"
                    className="btn btn-primary scan-button"
                    onClick={() => {
                      void handleScan();
                    }}
                    disabled={isScanLoading || !selectedPath}
                  >
                    <i className="fa-solid fa-magnifying-glass me-2" aria-hidden="true" />
                    {isScanLoading ? "Scanning..." : "Scan media"}
                  </button>
                </div>

                {statusMessage && (
                  <div className="alert alert-success" role="status">
                    {statusMessage}
                  </div>
                )}
                {errorMessage && (
                  <div className="alert alert-danger" role="alert">
                    {errorMessage}
                  </div>
                )}

                <div className="d-flex justify-content-between align-items-center mb-2">
                  <p className="mb-0 fw-semibold">Displayed items: {displayedItems.length}</p>
                  <p className="mb-0 text-secondary small">Ignored while scanning: {ignoredCount}</p>
                </div>

                <div className={viewMode === "grid" ? "media-grid" : "media-list"}>
                  {displayedItems.map((item) => (
                    <article
                      key={item.path}
                      className={viewMode === "grid" ? "media-card" : "media-row"}
                      data-testid="media-item"
                      role="button"
                      tabIndex={0}
                      onClick={() => {
                        openReviewMode(item.path);
                      }}
                      onKeyDown={(event) => {
                        handleCardKeyDown(event, item.path);
                      }}
                    >
                      <div className="media-preview-shell">
                        {renderMediaPreview(item, "media-preview")}
                      </div>
                      <div className="media-card-body">
                        <div className="media-badge">
                          <i
                            className={
                              item.mediaType === "image"
                                ? "fa-regular fa-image"
                                : "fa-solid fa-film"
                            }
                            aria-hidden="true"
                          />
                          <span>{item.mediaType}</span>
                        </div>
                        <h3 className="h6 mb-1 text-break">{item.name}</h3>
                        <p className="small text-secondary mb-2 text-break">{item.path}</p>
                        <p className="small mb-2">
                          {formatSize(item.sizeBytes)} | modified {new Date(item.modifiedAt).toLocaleString()}
                        </p>
                        <div className="d-flex flex-wrap gap-2 mb-2">
                          {item.status.locked && <span className="badge text-bg-primary">locked</span>}
                          {item.status.trashed && <span className="badge text-bg-danger">trash</span>}
                          {item.status.seen && <span className="badge text-bg-success">seen</span>}
                          {!item.status.seen && <span className="badge text-bg-secondary">unseen</span>}
                        </div>
                        {item.metadata.width && item.metadata.height && (
                          <p className="small text-secondary mb-2">
                            {item.metadata.width} x {item.metadata.height}
                          </p>
                        )}
                        <div
                          className="d-flex flex-wrap gap-2"
                          onClick={(event) => {
                            event.stopPropagation();
                          }}
                          onKeyDown={(event) => {
                            event.stopPropagation();
                          }}
                        >
                          <button
                            type="button"
                            className="btn btn-sm btn-outline-primary"
                            onClick={() => {
                              void handleMediaAction(item.path, "lock");
                            }}
                          >
                            Lock
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm btn-outline-danger"
                            onClick={() => {
                              void handleMediaAction(item.path, "trash");
                            }}
                          >
                            Trash
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm btn-outline-success"
                            onClick={() => {
                              void handleMediaAction(item.path, "seen");
                            }}
                          >
                            Seen
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm btn-outline-secondary"
                            onClick={() => {
                              void handleMediaAction(item.path, "unseen");
                            }}
                          >
                            Unseen
                          </button>
                        </div>
                      </div>
                    </article>
                  ))}
                  {displayedItems.length === 0 && (
                    <div className="metric-card">
                      <p className="mb-0">
                        No media items to display. Add or select a path, then scan your trailcam root.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </section>
          </div>
        )}

        {activeReviewItem && (
          <div
            className="review-overlay"
            role="dialog"
            aria-modal="true"
            aria-label="Review media item"
            data-testid="review-dialog"
          >
            <div className="review-dialog">
              <div className="review-toolbar">
                <button
                  type="button"
                  className="btn btn-outline-light"
                  onClick={() => {
                    showPreviousReviewItem();
                  }}
                >
                  Prev
                </button>
                <p className="review-counter mb-0">
                  {activeReviewIndex + 1} / {displayedItems.length}
                </p>
                <button
                  type="button"
                  className="btn btn-outline-light"
                  onClick={() => {
                    showNextReviewItem();
                  }}
                >
                  Next
                </button>
                <button
                  type="button"
                  className="btn btn-light"
                  onClick={() => {
                    setActiveReviewPath(null);
                  }}
                >
                  Close
                </button>
              </div>

              <div className="review-media-shell">
                <div
                  className="review-media-gesture-layer"
                  data-testid="review-media-shell"
                  onTouchStart={(event) => {
                    const firstTouch = event.changedTouches[0];
                    if (firstTouch) {
                      handleReviewTouchStart(firstTouch.clientX, firstTouch.clientY);
                    }
                  }}
                  onTouchEnd={(event) => {
                    const firstTouch = event.changedTouches[0];
                    if (firstTouch) {
                      handleReviewTouchEnd(firstTouch.clientX, firstTouch.clientY);
                    }
                  }}
                >
                  {activeReviewItem.mediaType === "image" ? (
                    <img
                      className="review-media"
                      src={buildMediaFileUrl(activeReviewItem.path)}
                      alt={activeReviewItem.name}
                    />
                  ) : (
                    <video
                      className="review-media"
                      src={buildMediaFileUrl(activeReviewItem.path)}
                      controls
                      autoPlay
                      playsInline
                    >
                      <track kind="captions" />
                    </video>
                  )}
                </div>
              </div>

              <div className="review-footer">
                <div>
                  <h2 className="h5 mb-1">{activeReviewItem.name}</h2>
                  <p className="mb-1 text-break">{activeReviewItem.path}</p>
                  <p className="mb-0 text-secondary">
                    {formatSize(activeReviewItem.sizeBytes)} | modified {new Date(activeReviewItem.modifiedAt).toLocaleString()}
                  </p>
                </div>
                <div className="d-flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="btn btn-outline-primary"
                    onClick={() => {
                      void handleMediaAction(activeReviewItem.path, "lock");
                    }}
                  >
                    Lock
                  </button>
                  <button
                    type="button"
                    className="btn btn-outline-danger"
                    onClick={() => {
                      void handleMediaAction(activeReviewItem.path, "trash");
                    }}
                  >
                    Trash
                  </button>
                  <button
                    type="button"
                    className="btn btn-outline-success"
                    onClick={() => {
                      void handleMediaAction(activeReviewItem.path, "seen");
                    }}
                  >
                    Seen
                  </button>
                  <button
                    type="button"
                    className="btn btn-outline-light"
                    onClick={() => {
                      void handleMediaAction(activeReviewItem.path, "unseen");
                    }}
                  >
                    Unseen
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}

export default App;
