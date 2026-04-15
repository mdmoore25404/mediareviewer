import { type KeyboardEvent, type ReactElement, useEffect, useMemo, useRef, useState } from "react";

import {
  addReviewPath,
  applyMediaAction,
  buildMediaFileUrl,
  buildMediaThumbnailUrl,
  fetchHealth,
  fetchLogs,
  fetchReviewPaths,
  removeReviewPath,
  streamEmptyTrash,
  streamMediaItems,
} from "./api/client";
import type {
  HealthResponse,
  LogsResponse,
  MediaAction,
  MediaItem,
  StatusFilter,
  TrashProgressEvent,
} from "./api/types";
import { TrashProgressDialog } from "./TrashProgressDialog";
import { FolderBrowser } from "./FolderBrowser";
import { useTheme } from "./useTheme";
import type { ThemeMode } from "./useTheme";

type ViewMode = "grid" | "list";
type MediaFilter = "all" | "image" | "video";

interface TrashLockedWarning {
  item: MediaItem;
  fromReview: boolean;
}
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

const SPEED_STEPS = [0.5, 1, 1.5, 2, 4, 8] as const;
type SpeedStep = (typeof SPEED_STEPS)[number];

function stepSpeed(current: number, direction: 1 | -1): SpeedStep {
  const idx = SPEED_STEPS.indexOf(current as SpeedStep);
  const clamped = Math.max(0, Math.min(SPEED_STEPS.length - 1, (idx === -1 ? 0 : idx) + direction));
  return SPEED_STEPS[clamped] ?? 1;
}

function themeIcon(mode: ThemeMode): string {
  if (mode === "light") return "fa-sun theme-icon--light";
  if (mode === "dark") return "fa-moon theme-icon--dark";
  return "fa-circle-half-stroke theme-icon--auto";
}

function themeLabel(mode: ThemeMode): string {
  if (mode === "light") return "Light mode (click for dark)";
  if (mode === "dark") return "Dark mode (click for auto)";
  return "Auto mode (click for light)";
}

function App(): ReactElement {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [knownPaths, setKnownPaths] = useState<string[]>([]);
  const [hiddenPaths, setHiddenPaths] = useState<string[]>([]);
  const [availablePaths, setAvailablePaths] = useState<string[]>([]);
  const [selectedPath, setSelectedPath] = useState<string>("");
  const [newPathInput, setNewPathInput] = useState<string>("/home/michaelmoore/trailcam");
  const [mediaItems, setMediaItems] = useState<MediaItem[]>([]);
  const [ignoredCount, setIgnoredCount] = useState<number>(0);
  const [scanLimit, setScanLimit] = useState<number>(20);
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("unseen");
  const [mediaFilter, setMediaFilter] = useState<MediaFilter>("all");
  const [sortOption, setSortOption] = useState<SortOption>("modified-asc");
  const [isBootLoading, setIsBootLoading] = useState<boolean>(true);
  const [isScanLoading, setIsScanLoading] = useState<boolean>(false);
  const [isFetchingMore, setIsFetchingMore] = useState<boolean>(false);
  const [hasMore, setHasMore] = useState<boolean>(false);
  const [fetchMoreFailed, setFetchMoreFailed] = useState<boolean>(false);
  const [scanCursor, setScanCursor] = useState<string | null>(null);
  const scanAbortRef = useRef<AbortController | null>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const lastZPressRef = useRef<number>(0);
  const [playbackRate, setPlaybackRate] = useState<number>(() => {
    const stored = sessionStorage.getItem("mediareviewer-playback-rate");
    const parsed = stored !== null ? Number(stored) : NaN;
    return [0.5, 1, 1.5, 2, 4, 8].includes(parsed) ? parsed : 1;
  });
  const [isVideoPaused, setIsVideoPaused] = useState<boolean>(false);
  const [isVideoMuted, setIsVideoMuted] = useState<boolean>(false);
  const [isSubmittingPath, setIsSubmittingPath] = useState<boolean>(false);
  const [isRemovingPath, setIsRemovingPath] = useState<boolean>(false);
  const [isEmptyingTrash, setIsEmptyingTrash] = useState<boolean>(false);
  const [trashProgressOpen, setTrashProgressOpen] = useState<boolean>(false);
  const [trashEvents, setTrashEvents] = useState<TrashProgressEvent[]>([]);
  const trashAbortRef = useRef<AbortController | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [activeReviewPath, setActiveReviewPath] = useState<string | null>(null);
  const [touchStartX, setTouchStartX] = useState<number | null>(null);
  const [touchStartY, setTouchStartY] = useState<number | null>(null);
  const [isFolderBrowserOpen, setIsFolderBrowserOpen] = useState<boolean>(false);
  const [showVideoControls, setShowVideoControls] = useState<boolean>(
    () => window.matchMedia("(pointer: fine) and (hover: hover)").matches,
  );
  const [showHelp, setShowHelp] = useState<boolean>(false);
  const [trashLockedWarning, setTrashLockedWarning] = useState<TrashLockedWarning | null>(null);
  const [showSettings, setShowSettings] = useState<boolean>(false);
  const [logs, setLogs] = useState<LogsResponse | null>(null);
  const [logsLoading, setLogsLoading] = useState<boolean>(false);
  const logsAbortRef = useRef<AbortController | null>(null);
  const [themeMode, cycleTheme] = useTheme();

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
        setAvailablePaths(pathsPayload.availablePaths);
        if (pathsPayload.knownPaths.length > 0) {
          setSelectedPath(pathsPayload.knownPaths[0]);
        }
      } catch (error: unknown) {
        if (error instanceof Error && error.name === "AbortError") return;
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

  // When statusFilter changes, the current scan results are from the previous filter.
  // Reset so the user re-scans rather than seeing stale data.
  useEffect(() => {
    scanAbortRef.current?.abort();
    setMediaItems([]);
    setHasMore(false);
    setScanCursor(null);
    setStatusMessage(null);
  }, [statusFilter]);

  const displayedItems = useMemo(() => {
    // Status filtering is now handled by the backend; only media-type filtering remains here.
    const filteredByMedia = mediaItems.filter((item) => {
      if (mediaFilter === "all") {
        return true;
      }
      return item.mediaType === mediaFilter;
    });

    return sortMediaItems(filteredByMedia, sortOption);
  }, [mediaFilter, mediaItems, sortOption]);

  const activeReviewIndex = useMemo(() => {
    if (!activeReviewPath) {
      return -1;
    }
    return displayedItems.findIndex((item) => item.path === activeReviewPath);
  }, [activeReviewPath, displayedItems]);

  const activeReviewItem = activeReviewIndex >= 0 ? displayedItems[activeReviewIndex] : null;

  const nextReviewItem =
    activeReviewIndex >= 0 && activeReviewIndex < displayedItems.length - 1
      ? (displayedItems[activeReviewIndex + 1] ?? null)
      : null;

  useEffect(() => {
    if (activeReviewPath && activeReviewIndex === -1) {
      setActiveReviewPath(null);
    }
  }, [activeReviewIndex, activeReviewPath]);

  // Keep video element in sync with controlled playback rate.
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.playbackRate = playbackRate;
    }
  }, [playbackRate, activeReviewPath]);

  // Reset pause indicator when navigating to a new item (autoPlay starts fresh).
  useEffect(() => {
    setIsVideoPaused(false);
  }, [activeReviewPath]);

  // Prime HTTP cache for the next item so it loads instantly when navigated to.
  useEffect(() => {
    if (!nextReviewItem) return undefined;
    const link = document.createElement("link");
    link.rel = "preload";
    link.as = nextReviewItem.mediaType === "video" ? "video" : "image";
    link.href = buildMediaFileUrl(nextReviewItem.path);
    document.head.appendChild(link);
    return () => {
      if (document.head.contains(link)) {
        document.head.removeChild(link);
      }
    };
  // nextReviewItem.path uniquely identifies the resource to preload
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nextReviewItem?.path]);

  useEffect(() => {
    if (!activeReviewItem) {
      return undefined;
    }

    const handleKeyDown = (event: globalThis.KeyboardEvent): void => {
      if (event.key === "Escape") {
        if (showHelp) {
          setShowHelp(false);
          return;
        }
        if (trashLockedWarning) {
          setTrashLockedWarning(null);
          return;
        }
        setActiveReviewPath(null);
        return;
      }
      if (event.key === "ArrowRight") {
        showNextReviewItem();
        return;
      }
      if (event.key === "ArrowLeft") {
        showPreviousReviewItem();
        return;
      }
      if (event.key.toLowerCase() === "e") {
        showPreviousReviewItem();
        return;
      }
      if (event.key.toLowerCase() === "r") {
        showNextReviewItem();
        return;
      }
      if (event.key.toLowerCase() === "d" || event.key.toLowerCase() === "t") {
        if (activeReviewItem.status.trashed) {
          void handleMediaAction(activeReviewItem.path, "untrash");
        } else if (activeReviewItem.status.locked) {
          setTrashLockedWarning({ item: activeReviewItem, fromReview: true });
        } else {
          void (async () => {
            await handleMediaAction(activeReviewItem.path, "trash");
            showNextReviewItem();
          })();
        }
        return;
      }
      if (event.key.toLowerCase() === "s") {
        if (activeReviewItem.status.seen) {
          void handleMediaAction(activeReviewItem.path, "unseen");
        } else {
          void (async () => {
            await handleMediaAction(activeReviewItem.path, "seen");
            showNextReviewItem();
          })();
        }
        return;
      }
      if (event.key.toLowerCase() === "f" || event.key.toLowerCase() === "l") {
        if (activeReviewItem.status.locked) {
          void handleMediaAction(activeReviewItem.path, "unlock");
        } else {
          void (async () => {
            await handleMediaAction(activeReviewItem.path, "lock");
            showNextReviewItem();
          })();
        }
        return;
      }
      if (event.key === "?") {
        setShowHelp((prev) => !prev);
        return;
      }
      // Video-only shortcuts
      if (activeReviewItem.mediaType === "video") {
        if (event.key === " ") {
          event.preventDefault();
          const vid = videoRef.current;
          if (!vid) return;
          if (vid.paused) void vid.play();
          else vid.pause();
          return;
        }
        if (event.key.toLowerCase() === "z") {
          const now = Date.now();
          if (videoRef.current) {
            if (now - lastZPressRef.current < 400) {
              // Double-Z: jump to start
              videoRef.current.currentTime = 0;
              lastZPressRef.current = 0;
            } else {
              videoRef.current.currentTime -= 5;
              lastZPressRef.current = now;
            }
          }
          return;
        }
        if (event.key.toLowerCase() === "x") {
          if (videoRef.current) videoRef.current.currentTime += 5;
          return;
        }
        if (event.key === "[" || event.key.toLowerCase() === "q") {
          setPlaybackRate((prev) => {
            const next = stepSpeed(prev, -1);
            sessionStorage.setItem("mediareviewer-playback-rate", String(next));
            return next;
          });
          return;
        }
        if (event.key === "]" || event.key.toLowerCase() === "w") {
          setPlaybackRate((prev) => {
            const next = stepSpeed(prev, 1);
            sessionStorage.setItem("mediareviewer-playback-rate", String(next));
            return next;
          });
          return;
        }
        const speedKeys: Record<string, SpeedStep> = { "1": 0.5, "2": 1, "3": 1.5, "4": 2, "5": 4, "6": 8 };
        const targetSpeed = speedKeys[event.key];
        if (targetSpeed !== undefined) {
          sessionStorage.setItem("mediareviewer-playback-rate", String(targetSpeed));
          setPlaybackRate(targetSpeed);
          return;
        }
      }
    };

    // Use capture phase so this fires before shadow-DOM event retargeting
    // inside native video controls swallows the event.
    window.addEventListener("keydown", handleKeyDown, { capture: true });
    return () => {
      window.removeEventListener("keydown", handleKeyDown, { capture: true });
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps -- showNextReviewItem captures displayedItems/activeReviewIndex which are already deps
  }, [activeReviewIndex, activeReviewItem, displayedItems, showHelp, trashLockedWarning]);

  const handleScan = async (): Promise<void> => {
    if (!selectedPath) {
      setErrorMessage("Pick a review path before scanning.");
      return;
    }
    // Cancel any scan already in flight
    scanAbortRef.current?.abort();
    const controller = new AbortController();
    scanAbortRef.current = controller;

    setIsScanLoading(true);
    setMediaItems([]);
    setIgnoredCount(0);
    setHasMore(false);
    setScanCursor(null);
    setStatusMessage(null);
    setErrorMessage(null);

    let count = 0;
    try {
      for await (const event of streamMediaItems(selectedPath, scanLimit, controller.signal, 0, statusFilter)) {
        if ("type" in event && event.type === "done") {
          setScanCursor(event.lastPath ?? null);
          setHasMore(event.count >= scanLimit);
          setStatusMessage(`Loaded ${event.count} media items from ${selectedPath}.`);
        } else {
          count += 1;
          setMediaItems((prev) => [...prev, event as MediaItem]);
          setStatusMessage(`Scanning\u2026 ${count} found`);
        }
      }
    } catch (error: unknown) {
      if ((error as Error).name === "AbortError") return;
      const message = error instanceof Error ? error.message : "Unable to scan review path.";
      setErrorMessage(message);
    } finally {
      setIsScanLoading(false);
    }
  };

  const handleLoadMore = async (): Promise<void> => {
    if (!selectedPath || isFetchingMore || isScanLoading || !hasMore || fetchMoreFailed) return;

    const controller = new AbortController();
    scanAbortRef.current = controller;
    setIsFetchingMore(true);
    setFetchMoreFailed(false);

    try {
      let count = 0;
      // Use the cursor from the last page so items reviewed between page loads
      // do not shift the page boundary and cause gaps or duplicates.
      for await (const event of streamMediaItems(
        selectedPath,
        scanLimit,
        controller.signal,
        0,
        statusFilter,
        scanCursor ?? undefined,
      )) {
        if ("type" in event && event.type === "done") {
          setScanCursor(event.lastPath ?? null);
          setHasMore(event.count >= scanLimit);
        } else {
          count += 1;
          setMediaItems((prev) => [...prev, event as MediaItem]);
        }
      }
      if (count === 0) setHasMore(false);
    } catch (error: unknown) {
      if ((error as Error).name === "AbortError") return;
      setFetchMoreFailed(true);
      const message = error instanceof Error ? error.message : "Unable to load more items.";
      setErrorMessage(message);
    } finally {
      setIsFetchingMore(false);
    }
  };

  // IntersectionObserver: load more items when the sentinel enters the viewport
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return undefined;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && !fetchMoreFailed) {
          void handleLoadMore();
        }
      },
      { threshold: 0.1 },
    );
    observer.observe(sentinel);
    return () => {
      observer.disconnect();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasMore, isFetchingMore, isScanLoading, selectedPath, mediaItems.length, fetchMoreFailed]);

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
      // Always select the newly added path so Scan uses it immediately
      setSelectedPath(payload.addedPath);
      setStatusMessage(`Added review path: ${payload.addedPath}`);
      setNewPathInput("");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Unable to add review path.";
      setErrorMessage(message);
    } finally {
      setIsSubmittingPath(false);
    }
  };

  const handleRemovePath = async (): Promise<void> => {
    if (!selectedPath) return;
    setIsRemovingPath(true);
    setStatusMessage(null);
    setErrorMessage(null);
    try {
      const payload = await removeReviewPath(selectedPath);
      setKnownPaths(payload.knownPaths);
      setSelectedPath(payload.knownPaths[0] ?? "");
      setStatusMessage(`Removed review path: ${payload.removedPath}`);
      setMediaItems([]);
      setHasMore(false);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Unable to remove review path.";
      setErrorMessage(message);
    } finally {
      setIsRemovingPath(false);
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

  const handleEmptyTrash = async (): Promise<void> => {
    const controller = new AbortController();
    trashAbortRef.current = controller;
    setTrashEvents([]);
    setTrashProgressOpen(true);
    setIsEmptyingTrash(true);
    setStatusMessage(null);
    setErrorMessage(null);
    const deletedPaths: string[] = [];
    try {
      for await (const event of streamEmptyTrash(selectedPath, controller.signal)) {
        setTrashEvents((prev) => [...prev, event]);
        if (event.type === "deleted" && event.path) {
          deletedPaths.push(event.path);
        }
        if (event.type === "done") {
          const deletedSet = new Set(deletedPaths);
          setMediaItems((prev) => prev.filter((item) => !deletedSet.has(item.path)));
          const n = event.deleted ?? deletedPaths.length;
          const msg = n === 1
            ? "Permanently deleted 1 trashed item."
            : `Permanently deleted ${n} trashed items.`;
          setStatusMessage(msg);
        }
      }
    } catch (error: unknown) {
      if (error instanceof Error && error.name !== "AbortError") {
        setErrorMessage(error.message);
      }
    } finally {
      setIsEmptyingTrash(false);
    }
  };

  const handleUnlockAndTrash = async (): Promise<void> => {
    if (!trashLockedWarning) return;
    const { item, fromReview } = trashLockedWarning;
    setTrashLockedWarning(null);
    await handleMediaAction(item.path, "unlock");
    await handleMediaAction(item.path, "trash");
    if (fromReview) {
      showNextReviewItem();
    }
  };

  const loadLogs = (): void => {
    logsAbortRef.current?.abort();
    const controller = new AbortController();
    logsAbortRef.current = controller;
    setLogsLoading(true);
    fetchLogs(controller.signal)
      .then((result) => {
        setLogs(result);
      })
      .catch(() => {
        /* ignore abort errors */
      })
      .finally(() => {
        setLogsLoading(false);
      });
  };

  const openReviewMode = (itemPath: string): void => {    setActiveReviewPath(itemPath);
  };

  const handleCardKeyDown = (event: KeyboardEvent<HTMLElement>, itemPath: string): void => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openReviewMode(itemPath);
    }
  };

  const showPreviousReviewItem = (): void => {
    if (displayedItems.length === 0 || activeReviewIndex <= 0) {
      return;
    }
    setActiveReviewPath(displayedItems[activeReviewIndex - 1]?.path ?? null);
  };

  const showNextReviewItem = (): void => {
    if (displayedItems.length === 0 || activeReviewIndex === -1) {
      return;
    }
    // Pre-fetch the next batch when within 5 items of the end
    const itemsFromEnd = displayedItems.length - 1 - activeReviewIndex;
    if (itemsFromEnd <= 5 && hasMore && !isFetchingMore) {
      void handleLoadMore();
    }
    const nextIndex = activeReviewIndex + 1;
    if (nextIndex >= displayedItems.length) {
      // Don't wrap to the start when more items are loading or still to come
      if (hasMore) {
        if (fetchMoreFailed && !isFetchingMore) {
          // Retry the failed load when user advances past the last known item
          setFetchMoreFailed(false);
          void handleLoadMore();
        }
        return;
      }
      setActiveReviewPath(displayedItems[0]?.path ?? null);
      return;
    }
    setActiveReviewPath(displayedItems[nextIndex]?.path ?? null);
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
      <nav className="app-topnav" aria-label="Application navigation">
        <span className="app-topnav-brand">Media Reviewer</span>
        <div className="app-topnav-actions">
          <span
            className={`app-status-dot app-status-dot--${health?.status === "ok" ? "ok" : "unknown"}`}
            title={`API: ${health?.status ?? "loading\u2026"}`}
            aria-label={`API status: ${health?.status ?? "loading"}`}
          />
          <button
            type="button"
            className="btn btn-sm btn-outline-secondary"
            title={themeLabel(themeMode)}
            aria-label={themeLabel(themeMode)}
            onClick={cycleTheme}
          >
            <i className={`fa-solid ${themeIcon(themeMode)}`} aria-hidden="true" />
          </button>
          <button
            type="button"
            className="btn btn-sm btn-outline-secondary"
            title="Settings"
            aria-label="Open settings"
            onClick={() => {
              setShowSettings(true);
              loadLogs();
            }}
          >
            <i className="fa-solid fa-gear" aria-hidden="true" />
          </button>
        </div>
      </nav>
      <section className="container py-4 py-lg-5">

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
                    className="btn btn-outline-secondary"
                    title="Browse folders"
                    aria-label="Browse folders"
                    onClick={() => {
                      setIsFolderBrowserOpen((prev) => !prev);
                    }}
                  >
                    <i className="fa-solid fa-folder-open" aria-hidden="true" />
                  </button>
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

                {isFolderBrowserOpen && (
                  <FolderBrowser
                    availablePaths={availablePaths}
                    hiddenPaths={hiddenPaths}
                    onSelectFolder={(path) => {
                      setNewPathInput(path);
                    }}
                    onClose={() => {
                      setIsFolderBrowserOpen(false);
                    }}
                  />
                )}
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
                <button
                  type="button"
                  className="btn btn-outline-danger btn-sm mt-2"
                  onClick={() => {
                    void handleRemovePath();
                  }}
                  disabled={!selectedPath || isRemovingPath}
                >
                  {isRemovingPath ? "Removing..." : "Remove selected path"}
                </button>


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
                  <button
                    type="button"
                    className="btn btn-outline-danger"
                    onClick={() => {
                      void handleEmptyTrash();
                    }}
                    disabled={isEmptyingTrash}
                  >
                    <i className="fa-solid fa-trash me-2" aria-hidden="true" />
                    {isEmptyingTrash ? "Emptying..." : "Empty trash"}
                  </button>
                  {(isEmptyingTrash || trashEvents.length > 0) && (
                    <button
                      type="button"
                      className="btn btn-outline-secondary btn-sm"
                      onClick={() => {
                        setTrashProgressOpen(true);
                      }}
                    >
                      <i className="fa-solid fa-list me-1" aria-hidden="true" />
                      Progress
                    </button>
                  )}
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
                        <h3 className="h6 mb-1 text-break">
                          {item.name}
                          <span className="review-footer-meta ms-2" aria-hidden="true">
                            {formatSize(item.sizeBytes)} · {new Date(item.modifiedAt).toLocaleString()}
                          </span>
                        </h3>

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
                              if (item.status.locked) {
                                setTrashLockedWarning({ item, fromReview: false });
                              } else {
                                void handleMediaAction(item.path, "trash");
                              }
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
                        No media items to display. Add or select a path, then scan your media root.
                      </p>
                    </div>
                  )}
                </div>

                {/* Infinite scroll sentinel — observed by IntersectionObserver */}
                <div ref={sentinelRef} className="scroll-sentinel" aria-hidden="true" />
                {isFetchingMore && (
                  <p className="text-center text-secondary small py-2">
                    <i className="fa-solid fa-circle-notch fa-spin me-2" aria-hidden="true" />
                    Loading more…
                  </p>
                )}
                {!hasMore && mediaItems.length > 0 && !isScanLoading && (
                  <p className="text-center text-secondary small py-2">All items loaded.</p>
                )}
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
                  disabled={activeReviewIndex === 0}
                >
                  Prev{showVideoControls && <kbd className="review-action-kbd" aria-hidden="true">E</kbd>}
                </button>
                <p className="review-counter mb-0">
                  {activeReviewIndex + 1} / {displayedItems.length}
                  {isFetchingMore && (
                    <span className="review-counter-loading ms-2" aria-label="Loading more items">
                      <span className="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true" />
                      <span className="review-counter-loading-text">Loading more…</span>
                    </span>
                  )}
                  {fetchMoreFailed && hasMore && !isFetchingMore && (
                    <button
                      type="button"
                      className="review-counter-retry btn btn-link btn-sm p-0 ms-2"
                      onClick={() => {
                        setFetchMoreFailed(false);
                        void handleLoadMore();
                      }}
                    >
                      <i className="fa-solid fa-rotate me-1" aria-hidden="true" />
                      Retry
                    </button>
                  )}
                </p>
                <button
                  type="button"
                  className="btn btn-outline-light"
                  onClick={() => {
                    showNextReviewItem();
                  }}
                  disabled={
                    activeReviewIndex === displayedItems.length - 1 && !hasMore && !isFetchingMore
                  }
                >
                  Next{showVideoControls && <kbd className="review-action-kbd" aria-hidden="true">R</kbd>}
                </button>
                <button
                  type="button"
                  className="btn btn-light"
                  onClick={() => {
                    setActiveReviewPath(null);
                  }}
                >
                  Close{showVideoControls && <kbd className="review-action-kbd" aria-hidden="true">Esc</kbd>}
                </button>
                {activeReviewItem.mediaType === "video" && (
                  <button
                    type="button"
                    className={showVideoControls ? "btn btn-secondary" : "btn btn-outline-secondary"}
                    onClick={() => setShowVideoControls((prev) => !prev)}
                    title="Toggle seek controls"
                  >
                    <i className="fa-solid fa-sliders" aria-hidden="true" />
                  </button>
                )}
                <button
                  type="button"
                  className={`btn review-help-btn ${showHelp ? "btn-secondary" : "btn-outline-secondary"}`}
                  onClick={() => setShowHelp((prev) => !prev)}
                  aria-label="Keyboard shortcuts"
                  title="Keyboard shortcuts (?)"
                >
                  <i className="fa-solid fa-keyboard" aria-hidden="true" />
                </button>
              </div>

              {showHelp && (
                <div className="review-help-panel" role="complementary" aria-label="Keyboard shortcuts">
                  <h3 className="review-help-title">Keyboard shortcuts</h3>
                  <table className="review-help-table">
                    <tbody>
                      <tr><td><kbd>→</kbd> / <kbd>←</kbd></td><td>Next / previous item</td></tr>
                      <tr><td><kbd>R</kbd> / <kbd>E</kbd></td><td>Next / previous item (alt)</td></tr>
                      <tr><td><kbd>S</kbd></td><td>Mark seen (auto-advances) — toggle unseen</td></tr>
                      <tr><td><kbd>T</kbd> / <kbd>D</kbd></td><td>Trash (auto-advances) — toggle untrash</td></tr>
                      <tr><td><kbd>L</kbd> / <kbd>F</kbd></td><td>Lock (auto-advances) — toggle unlock</td></tr>
                      <tr><td><kbd>?</kbd></td><td>Show / hide this panel</td></tr>
                      <tr><td><kbd>Esc</kbd></td><td>Close panel / close review</td></tr>
                    </tbody>
                  </table>
                  {activeReviewItem.mediaType === "video" && (
                    <table className="review-help-table mt-2">
                      <tbody>
                        <tr><td colSpan={2} className="review-help-section">Video controls</td></tr>
                        <tr><td><kbd>Space</kbd></td><td>Play / pause</td></tr>
                        <tr><td><kbd>Z</kbd></td><td>Skip back 5 s</td></tr>
                        <tr><td><kbd>Z</kbd><kbd>Z</kbd></td><td>Jump to start</td></tr>
                        <tr><td><kbd>X</kbd></td><td>Skip forward 5 s</td></tr>
                        <tr><td><kbd>Q</kbd> / <kbd>[</kbd></td><td>Speed down</td></tr>
                        <tr><td><kbd>W</kbd> / <kbd>]</kbd></td><td>Speed up</td></tr>
                        <tr><td><kbd>1</kbd>–<kbd>6</kbd></td><td>Speed 0.5× / 1× / 1.5× / 2× / 4× / 8×</td></tr>
                      </tbody>
                    </table>
                  )}
                </div>
              )}

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
                      ref={videoRef}
                      className="review-media"
                      src={buildMediaFileUrl(activeReviewItem.path)}
                      autoPlay
                      playsInline
                      preload="auto"
                      muted={isVideoMuted}
                      controls={showVideoControls}
                      onPlay={() => { setIsVideoPaused(false); }}
                      onPause={() => { setIsVideoPaused(true); }}
                      onClick={(event) => {
                        if (showVideoControls) {
                          return;
                        }
                        const vid = event.currentTarget;
                        if (vid.paused) void vid.play();
                        else vid.pause();
                      }}
                    >
                      <track kind="captions" />
                    </video>
                  )}
                </div>
              </div>

              {/* Video mini-controls */}
              {activeReviewItem.mediaType === "video" && (
                <div className="video-mini-controls" role="group" aria-label="Video playback controls">
                  <button
                    type="button"
                    className="btn btn-sm btn-outline-light video-mini-btn"
                    title="Skip back 5 seconds (Z)"
                    aria-label="Skip back 5 seconds"
                    onClick={() => {
                      if (videoRef.current) videoRef.current.currentTime -= 5;
                    }}
                  >
                    <i className="fa-solid fa-backward-step" aria-hidden="true" />
                    <span className="video-mini-label">−5s</span>
                    {showVideoControls && <kbd className="video-mini-kbd" aria-hidden="true">Z</kbd>}
                  </button>

                  <button
                    type="button"
                    className="btn btn-sm btn-outline-light video-mini-btn video-mini-playpause"
                    title={`${isVideoPaused ? "Play" : "Pause"} (Space)`}
                    aria-label={isVideoPaused ? "Play" : "Pause"}
                    onClick={() => {
                      const vid = videoRef.current;
                      if (!vid) return;
                      if (vid.paused) void vid.play();
                      else vid.pause();
                    }}
                  >
                    <i
                      className={`fa-solid ${isVideoPaused ? "fa-play" : "fa-pause"}`}
                      aria-hidden="true"
                    />
                    {showVideoControls && <kbd className="video-mini-kbd" aria-hidden="true">Spc</kbd>}
                  </button>

                  <button
                    type="button"
                    className="btn btn-sm btn-outline-light video-mini-btn"
                    title="Skip forward 5 seconds (X)"
                    aria-label="Skip forward 5 seconds"
                    onClick={() => {
                      if (videoRef.current) videoRef.current.currentTime += 5;
                    }}
                  >
                    <i className="fa-solid fa-forward-step" aria-hidden="true" />
                    <span className="video-mini-label">+5s</span>
                    {showVideoControls && <kbd className="video-mini-kbd" aria-hidden="true">X</kbd>}
                  </button>

                  <button
                    type="button"
                    className={`btn btn-sm video-mini-btn ${isVideoMuted ? "btn-secondary" : "btn-outline-light"}`}
                    title={isVideoMuted ? "Unmute" : "Mute"}
                    aria-label={isVideoMuted ? "Unmute" : "Mute"}
                    onClick={() => { setIsVideoMuted((prev) => !prev); }}
                  >
                    <i
                      className={`fa-solid ${isVideoMuted ? "fa-volume-xmark" : "fa-volume-high"}`}
                      aria-hidden="true"
                    />
                  </button>

                  <div className="video-mini-speed">
                    {showVideoControls && (
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-light video-mini-btn"
                        title="Speed down (Q / [)"
                        aria-label="Speed down"
                        onClick={() => {
                          setPlaybackRate((prev) => {
                            const next = stepSpeed(prev, -1);
                            sessionStorage.setItem("mediareviewer-playback-rate", String(next));
                            return next;
                          });
                        }}
                      >
                        <i className="fa-solid fa-gauge-simple-low" aria-hidden="true" />
                        <span className="video-mini-label">Slower</span>
                        <kbd className="video-mini-kbd" aria-hidden="true">Q</kbd>
                      </button>
                    )}
                    {SPEED_STEPS.map((rate, i) => (
                      <button
                        key={rate}
                        type="button"
                        className={`btn btn-sm video-mini-btn ${playbackRate === rate ? "video-mini-btn--active" : "btn-outline-light"}`}
                        aria-pressed={playbackRate === rate}
                        onClick={() => {
                          sessionStorage.setItem("mediareviewer-playback-rate", String(rate));
                          setPlaybackRate(rate);
                        }}
                      >
                        {rate}×{showVideoControls && <kbd className="video-mini-kbd" aria-hidden="true">{i + 1}</kbd>}
                      </button>
                    ))}
                    {showVideoControls && (
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-light video-mini-btn"
                        title="Speed up (W / ])"
                        aria-label="Speed up"
                        onClick={() => {
                          setPlaybackRate((prev) => {
                            const next = stepSpeed(prev, 1);
                            sessionStorage.setItem("mediareviewer-playback-rate", String(next));
                            return next;
                          });
                        }}
                      >
                        <i className="fa-solid fa-gauge-simple-high" aria-hidden="true" />
                        <span className="video-mini-label">Faster</span>
                        <kbd className="video-mini-kbd" aria-hidden="true">W</kbd>
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* Pre-fetch next item — hidden but fully rendered to avoid browser throttling */}
              {nextReviewItem && (
                <div
                  style={{
                    position: "absolute",
                    width: 0,
                    height: 0,
                    overflow: "hidden",
                    pointerEvents: "none",
                    visibility: "hidden",
                  }}
                  aria-hidden="true"
                >
                  {nextReviewItem.mediaType === "image" ? (
                    <img src={buildMediaFileUrl(nextReviewItem.path)} alt="" />
                  ) : (
                    <video src={buildMediaFileUrl(nextReviewItem.path)} preload="auto" muted autoPlay />
                  )}
                </div>
              )}

              <div className="review-footer">
                <div>
                  <h2 className="h5 mb-1">
                    {activeReviewItem.name}
                    <span className="review-footer-meta ms-2" aria-hidden="true">
                      {formatSize(activeReviewItem.sizeBytes)} · {new Date(activeReviewItem.modifiedAt).toLocaleString()}
                    </span>
                  </h2>

                </div>
                <div className="d-flex flex-wrap gap-2">
                  <button
                    type="button"
                    className={activeReviewItem.status.locked ? "btn btn-warning" : "btn btn-outline-warning"}
                    onClick={() => {
                      if (activeReviewItem.status.locked) {
                        void handleMediaAction(activeReviewItem.path, "unlock");
                      } else {
                        void (async () => {
                          await handleMediaAction(activeReviewItem.path, "lock");
                          showNextReviewItem();
                        })();
                      }
                    }}
                  >
                    {activeReviewItem.status.locked ? "Locked" : "Lock"}
                    {showVideoControls && <kbd className="review-action-kbd" aria-hidden="true">F</kbd>}
                  </button>
                  <button
                    type="button"
                    className={activeReviewItem.status.trashed ? "btn btn-danger" : "btn btn-outline-danger"}
                    onClick={() => {
                      if (activeReviewItem.status.trashed) {
                        void handleMediaAction(activeReviewItem.path, "untrash");
                      } else if (activeReviewItem.status.locked) {
                        setTrashLockedWarning({ item: activeReviewItem, fromReview: true });
                      } else {
                        void (async () => {
                          await handleMediaAction(activeReviewItem.path, "trash");
                          showNextReviewItem();
                        })();
                      }
                    }}
                  >
                    {activeReviewItem.status.trashed ? "Trashed" : "Trash"}
                    {showVideoControls && <kbd className="review-action-kbd" aria-hidden="true">D</kbd>}
                  </button>
                  <button
                    type="button"
                    className={activeReviewItem.status.seen ? "btn btn-success" : "btn btn-outline-success"}
                    onClick={() => {
                      if (activeReviewItem.status.seen) {
                        void handleMediaAction(activeReviewItem.path, "unseen");
                      } else {
                        void (async () => {
                          await handleMediaAction(activeReviewItem.path, "seen");
                          showNextReviewItem();
                        })();
                      }
                    }}
                  >
                    {activeReviewItem.status.seen ? "Seen" : "Unseen"}
                    {showVideoControls && <kbd className="review-action-kbd" aria-hidden="true">S</kbd>}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
        <TrashProgressDialog
          isOpen={trashProgressOpen}
          isRunning={isEmptyingTrash}
          events={trashEvents}
          onClose={() => {
            setTrashProgressOpen(false);
          }}
          onAbort={() => {
            trashAbortRef.current?.abort();
          }}
        />
        {showSettings && (
          <div
            className="review-overlay"
            role="dialog"
            aria-modal="true"
            aria-label="Settings"
            data-testid="settings-dialog"
            onClick={(event) => {
              if (event.target === event.currentTarget) {
                logsAbortRef.current?.abort();
                setShowSettings(false);
              }
            }}
          >
            <div className="settings-dialog">
              <div className="d-flex align-items-center justify-content-between mb-4">
                <h2 className="h5 mb-0">
                  <i className="fa-solid fa-gear me-2" aria-hidden="true" />
                  Settings
                </h2>
                <button
                  type="button"
                  className="btn-close"
                  aria-label="Close settings"
                  onClick={() => {
                    logsAbortRef.current?.abort();
                    setShowSettings(false);
                  }}
                />
              </div>

              <div className="mb-3">
                <p className="settings-section-label">API status</p>
                <p className="mb-0">
                  <span
                    className={`app-status-dot app-status-dot--${health?.status === "ok" ? "ok" : "unknown"} me-2`}
                    aria-hidden="true"
                  />
                  {health?.status ?? "unknown"}
                </p>
              </div>

              <div className="mb-3">
                <p className="settings-section-label">State directory</p>
                <p className="settings-path-value mb-0">
                  {health?.settings.stateDirectory ?? "-"}
                </p>
              </div>

              <div className="mb-3">
                <p className="settings-section-label">
                  Hidden picker paths ({hiddenPaths.length})
                </p>
                {hiddenPaths.length === 0 ? (
                  <p className="small text-secondary mb-0">None configured.</p>
                ) : (
                  <ul className="small mb-0 ps-3">
                    {hiddenPaths.map((path) => (
                      <li key={path}>{path}</li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="mb-0">
                <p className="settings-section-label">Video preload buffer</p>
                <p className="mb-0 small">
                  {health?.settings.videoPreloadMb != null
                    ? `${health.settings.videoPreloadMb} MB`
                    : "-"}
                  <span className="text-secondary ms-2">
                    (set via <code>MEDIAREVIEWER_VIDEO_PRELOAD_MB</code>)
                  </span>
                </p>
              </div>

              <div className="mb-0 mt-3">
                <div className="d-flex align-items-center justify-content-between mb-2">
                  <p className="settings-section-label mb-0">Server logs</p>
                  <button
                    type="button"
                    className="btn btn-sm btn-outline-secondary"
                    aria-label="Refresh logs"
                    disabled={logsLoading}
                    onClick={loadLogs}
                  >
                    <i
                      className={`fa-solid fa-rotate-right${
                        logsLoading ? " fa-spin" : ""
                      }`}
                      aria-hidden="true"
                    />
                  </button>
                </div>
                {logs === null && !logsLoading && (
                  <p className="small text-secondary mb-0">No logs loaded yet.</p>
                )}
                {logs !== null && !logs.available && (
                  <p className="small text-secondary mb-0">
                    Log file not yet created: <code>{logs.logFile}</code>
                  </p>
                )}
                {logs !== null && logs.available && (
                  <>
                    <p className="small text-secondary mb-1">
                      <code>{logs.logFile}</code>
                    </p>
                    <pre
                      className="settings-log-viewer"
                      data-testid="log-viewer"
                    >
                      {logs.lines.length === 0
                        ? "(empty)"
                        : logs.lines.join("\n")}
                    </pre>
                  </>
                )}
              </div>
            </div>
          </div>
        )}

        {trashLockedWarning && (
          <div
            className="review-overlay"
            role="dialog"
            aria-modal="true"
            aria-label="Cannot trash locked item"
            data-testid="trash-locked-warning"
          >
            <div className="trash-locked-dialog">
              <h2 className="h5 mb-3">
                <i className="fa-solid fa-lock me-2" aria-hidden="true" />
                Cannot trash a locked item
              </h2>
              <p className="mb-4">
                You cannot trash a locked item. You must unlock it to trash it.
              </p>
              <div className="d-flex gap-2 justify-content-end">
                <button
                  type="button"
                  className="btn btn-outline-secondary"
                  onClick={() => {
                    setTrashLockedWarning(null);
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={() => {
                    void handleUnlockAndTrash();
                  }}
                >
                  <i className="fa-solid fa-unlock me-2" aria-hidden="true" />
                  Unlock &amp; Trash
                </button>
              </div>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}

export default App;
