import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import type { HealthResponse, MediaActionResponse, MediaItem, RemoveReviewPathResponse, ReviewPathsResponse } from "../api/types";

const healthResponse: HealthResponse = {
  status: "ok",
  service: "mediareviewer-api",
  settings: {
    stateDirectory: "/tmp/mediareviewer",
    hiddenPickerPaths: ["/proc"],
    deletionWorkers: 2,
    videoPreloadMb: 50,
  },
  deletionQueue: {
    max_workers: 2,
    active_jobs: 0,
    submitted_jobs: 0,
    completed_jobs: 0,
    failed_jobs: 0,
  },
};

const reviewPathsResponse: ReviewPathsResponse = {
  knownPaths: ["/home/michaelmoore/trailcam"],
  availablePaths: ["/home/michaelmoore", "/mnt"],
  hiddenPickerPaths: ["/proc"],
};

const mediaItems: MediaItem[] = [
  {
    path: "/home/michaelmoore/trailcam/DCIM/100MEDIA/frame001.jpg",
    name: "frame001.jpg",
    mediaType: "image",
    thumbnailUrl: "/api/media-thumbnail?path=%2Fhome%2Fmichaelmoore%2Ftrailcam%2FDCIM%2F100MEDIA%2Fframe001.jpg&size=256",
    sizeBytes: 1024,
    modifiedAt: "2026-04-12T21:50:19+00:00",
    createdAt: "2026-04-12T21:50:19+00:00",
    status: {
      locked: false,
      trashed: false,
      seen: false,
    },
    metadata: {
      width: 12,
      height: 8,
    },
  },
  {
    path: "/home/michaelmoore/trailcam/DCIM/100MEDIA/frame002.jpg",
    name: "frame002.jpg",
    mediaType: "image",
    thumbnailUrl: "/api/media-thumbnail?path=%2Fhome%2Fmichaelmoore%2Ftrailcam%2FDCIM%2F100MEDIA%2Fframe002.jpg&size=256",
    sizeBytes: 2048,
    modifiedAt: "2026-04-12T21:55:19+00:00",
    createdAt: "2026-04-12T21:55:19+00:00",
    status: {
      locked: false,
      trashed: false,
      seen: false,
    },
    metadata: {
      width: 10,
      height: 10,
    },
  },
];

/** Build a ReadableStream that emits NDJSON for the given items plus a done sentinel. */
function makeStreamBody(items: MediaItem[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  const ndjson =
    items.map((item) => JSON.stringify(item)).join("\n") +
    "\n" +
    JSON.stringify({ type: "done", count: items.length }) +
    "\n";
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(ndjson));
      controller.close();
    },
  });
}

const mediaActionResponse: MediaActionResponse = {
  path: "/home/michaelmoore/trailcam/DCIM/100MEDIA/frame001.jpg",
  action: "seen",
  status: {
    locked: false,
    trashed: false,
    seen: true,
  },
};

const videoItem: MediaItem = {
  path: "/home/michaelmoore/trailcam/DCIM/100MEDIA/clip001.mp4",
  name: "clip001.mp4",
  mediaType: "video",
  thumbnailUrl: "",
  sizeBytes: 10240,
  modifiedAt: "2026-04-12T21:50:19+00:00",
  createdAt: "2026-04-12T21:50:19+00:00",
  status: { locked: false, trashed: false, seen: false },
  metadata: { width: null, height: null },
};

describe("App", () => {
  beforeEach(() => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;

      if (url.endsWith("/api/health")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(healthResponse),
        });
      }

      if (url.endsWith("/api/review-paths") && (!init?.method || init.method === "GET")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(reviewPathsResponse),
        });
      }

      if (url.endsWith("/api/review-paths") && init?.method === "DELETE") {
        const removeResponse: RemoveReviewPathResponse = {
          removedPath: "/home/michaelmoore/trailcam",
          knownPaths: [],
        };
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(removeResponse),
        });
      }

      if (url.startsWith("/api/media-items/stream?")) {
        return Promise.resolve({
          ok: true,
          body: makeStreamBody(mediaItems),
        });
      }

      if (url.endsWith("/api/empty-trash") && init?.method === "POST") {
        const encoder = new TextEncoder();
        const ndjson =
          JSON.stringify({ type: "done", deleted: 0, errors: 0 }) + "\n";
        return Promise.resolve({
          ok: true,
          body: new ReadableStream({
            start(controller) {
              controller.enqueue(encoder.encode(ndjson));
              controller.close();
            },
          }),
        });
      }

      if (url.endsWith("/api/media-actions")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mediaActionResponse),
        });
      }

      if (url.startsWith("/api/logs")) {
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              lines: ["2026-04-14 INFO mediareviewer_api.app: Starting"],
              logFile: "/tmp/mediareviewer/mediareviewer.log",
              available: true,
            }),
        });
      }

      return Promise.resolve({
        ok: false,
        json: () => Promise.resolve({ error: `Unhandled request: ${url}` }),
      });
    });

    vi.stubGlobal(
      "fetch",
      fetchMock,
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("loads review paths and scans media items", async () => {
    const user = userEvent.setup();
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("Media Reviewer")).toBeInTheDocument();
      expect(screen.getByLabelText("Known path")).toHaveValue("/home/michaelmoore/trailcam");
    });

    await user.click(screen.getByRole("button", { name: "Scan media" }));

    await waitFor(() => {
      expect(screen.getByText("frame001.jpg")).toBeInTheDocument();
      expect(screen.getByText(/Loaded 2 media items/i)).toBeInTheDocument();
    });
  });

  it("applies seen action to a media item", async () => {
    const user = userEvent.setup();
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Scan media" })).toBeInTheDocument();
    });

    // Switch to "All" before scanning so the item remains visible after being marked seen
    await user.selectOptions(screen.getByLabelText("Status"), "all");

    await user.click(screen.getByRole("button", { name: "Scan media" }));

    await waitFor(() => {
      expect(screen.getByText("frame001.jpg")).toBeInTheDocument();
    });

    const cards = screen.getAllByTestId("media-item");
    const frame001Card = cards.find((card) => within(card).queryByText("frame001.jpg") !== null);
    expect(frame001Card).toBeTruthy();

    if (!frame001Card) {
      throw new Error("Expected frame001.jpg card to be present.");
    }

    await user.click(within(frame001Card).getByRole("button", { name: "Seen" }));

    await waitFor(() => {
      expect(screen.getAllByText("seen").length).toBeGreaterThan(0);
    });
  });

  it("opens fullscreen review mode when a card body is clicked", async () => {
    const user = userEvent.setup();
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Scan media" })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Scan media" }));

    await waitFor(() => {
      expect(screen.getByText("frame001.jpg")).toBeInTheDocument();
    });

    const cards = screen.getAllByTestId("media-item");
    const frame001Card = cards.find((card) => within(card).queryByText("frame001.jpg") !== null);
    expect(frame001Card).toBeTruthy();

    if (!frame001Card) {
      throw new Error("Expected frame001.jpg card to be present.");
    }

    await user.click(frame001Card);

    await waitFor(() => {
      expect(screen.getByTestId("review-dialog")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Close" })).toBeInTheDocument();
    });
  });

  it("swipes to the next item in fullscreen review mode", async () => {
    const user = userEvent.setup();
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Scan media" })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Scan media" }));

    await waitFor(() => {
      expect(screen.getByText("frame001.jpg")).toBeInTheDocument();
      expect(screen.getByText("frame002.jpg")).toBeInTheDocument();
    });

    const cards = screen.getAllByTestId("media-item");
    const frame001Card = cards.find((card) => within(card).queryByText("frame001.jpg") !== null);
    expect(frame001Card).toBeTruthy();

    if (!frame001Card) {
      throw new Error("Expected frame001.jpg card to be present.");
    }

    await user.click(frame001Card);

    const reviewDialog = await screen.findByTestId("review-dialog");

    await waitFor(() => {
      expect(reviewDialog).toBeInTheDocument();
      expect(within(reviewDialog).getByRole("heading", { name: "frame001.jpg" })).toBeInTheDocument();
    });

    const reviewMediaShell = screen.getByTestId("review-media-shell");
    fireEvent.touchStart(reviewMediaShell, {
      changedTouches: [{ clientX: 200, clientY: 100 }],
    });
    fireEvent.touchEnd(reviewMediaShell, {
      changedTouches: [{ clientX: 80, clientY: 100 }],
    });

    await waitFor(() => {
      expect(within(reviewDialog).getByRole("heading", { name: "frame002.jpg" })).toBeInTheDocument();
    });
  });

  it("removes selected review path and updates the known-paths list", async () => {
    const user = userEvent.setup();
    render(<App />);

    await waitFor(() => {
      expect(screen.getByLabelText("Known path")).toHaveValue("/home/michaelmoore/trailcam");
    });

    const removeButton = screen.getByRole("button", { name: "Remove selected path" });
    expect(removeButton).not.toBeDisabled();

    await user.click(removeButton);

    await waitFor(() => {
      expect(screen.getByText(/Removed review path:/i)).toBeInTheDocument();
      expect(screen.getByLabelText("Known path")).toHaveValue("");
    });

    const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls as [string, RequestInit][];
    const deleteCall = calls.find(([url, init]) => url.endsWith("/api/review-paths") && init?.method === "DELETE");
    expect(deleteCall).toBeTruthy();
  });

  it("includes statusFilter in the stream request URL", async () => {
    const user = userEvent.setup();
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Scan media" })).toBeInTheDocument();
    });

    await user.selectOptions(screen.getByLabelText("Status"), "locked");
    await user.click(screen.getByRole("button", { name: "Scan media" }));

    await waitFor(() => {
      const calls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls as [string][];
      const streamCall = calls.find(([url]) => url.startsWith("/api/media-items/stream?"));
      expect(streamCall).toBeTruthy();
      expect(streamCall?.[0]).toContain("statusFilter=locked");
    });
  });

  it("theme toggle cycles through auto → light → dark", async () => {
    const user = userEvent.setup();

    render(<App />);

    // Default is auto — icon is fa-circle-half-stroke title includes "Auto mode"
    const toggleBtn = screen.getByRole("button", { name: /auto mode/i });
    expect(toggleBtn).toBeInTheDocument();

    // Click once → light
    await user.click(toggleBtn);
    expect(screen.getByRole("button", { name: /light mode/i })).toBeInTheDocument();

    // Click again → dark
    await user.click(screen.getByRole("button", { name: /light mode/i }));
    expect(screen.getByRole("button", { name: /dark mode/i })).toBeInTheDocument();

    // Click again → back to auto
    await user.click(screen.getByRole("button", { name: /dark mode/i }));
    expect(screen.getByRole("button", { name: /auto mode/i })).toBeInTheDocument();
  });

  it("shows video mini-controls when a video item is in review", async () => {
    const user = userEvent.setup();

    // Override stream to return one video item
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      if (url.endsWith("/api/health")) return Promise.resolve({ ok: true, json: () => Promise.resolve(healthResponse) });
      if (url.endsWith("/api/review-paths") && (!init?.method || init.method === "GET")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(reviewPathsResponse) });
      }
      if (url.startsWith("/api/media-items/stream?")) {
        return Promise.resolve({ ok: true, body: makeStreamBody([videoItem]) });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({ error: "unhandled" }) });
    }));

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Scan media" })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Scan media" }));

    await waitFor(() => {
      expect(screen.getByText("clip001.mp4")).toBeInTheDocument();
    });

    // Open in review mode
    await user.click(screen.getByText("clip001.mp4"));

    await waitFor(() => {
      expect(screen.getByRole("group", { name: "Video playback controls" })).toBeInTheDocument();
    });

    // Speed buttons are present
    expect(screen.getByRole("button", { name: "1×" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "2×" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "4×" })).toBeInTheDocument();

    // Skip buttons
    expect(screen.getByRole("button", { name: "Skip back 5 seconds" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Skip forward 5 seconds" })).toBeInTheDocument();

    // Mute toggle
    expect(screen.getByRole("button", { name: "Mute" })).toBeInTheDocument();
  });

  it("speed buttons cycle playback rate and persist to sessionStorage", async () => {
    const user = userEvent.setup();

    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
      if (url.endsWith("/api/health")) return Promise.resolve({ ok: true, json: () => Promise.resolve(healthResponse) });
      if (url.endsWith("/api/review-paths") && (!init?.method || init.method === "GET")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve(reviewPathsResponse) });
      }
      if (url.startsWith("/api/media-items/stream?")) {
        return Promise.resolve({ ok: true, body: makeStreamBody([videoItem]) });
      }
      return Promise.resolve({ ok: false, json: () => Promise.resolve({ error: "unhandled" }) });
    }));

    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Scan media" })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Scan media" }));
    await waitFor(() => { expect(screen.getByText("clip001.mp4")).toBeInTheDocument(); });
    await user.click(screen.getByText("clip001.mp4"));

    await waitFor(() => {
      expect(screen.getByRole("group", { name: "Video playback controls" })).toBeInTheDocument();
    });

    // 1× is active by default (aria-pressed)
    expect(screen.getByRole("button", { name: "1×" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "2×" })).toHaveAttribute("aria-pressed", "false");

    // Click 2×
    await user.click(screen.getByRole("button", { name: "2×" }));
    expect(screen.getByRole("button", { name: "2×" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "1×" })).toHaveAttribute("aria-pressed", "false");
    expect(sessionStorage.getItem("mediareviewer-playback-rate")).toBe("2");
  });
  it("opens settings and shows log lines in the log viewer", async () => {
    const user = userEvent.setup();
    render(<App />);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Open settings" })).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: "Open settings" }));

    await waitFor(() => {
      expect(screen.getByTestId("log-viewer")).toBeInTheDocument();
    });

    expect(screen.getByTestId("log-viewer")).toHaveTextContent(
      "2026-04-14 INFO mediareviewer_api.app: Starting",
    );
  });});
