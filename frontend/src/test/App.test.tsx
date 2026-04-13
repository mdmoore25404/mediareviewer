import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import type { HealthResponse, MediaActionResponse, MediaItemsResponse, ReviewPathsResponse } from "../api/types";

const healthResponse: HealthResponse = {
  status: "ok",
  service: "mediareviewer-api",
  settings: {
    stateDirectory: "/tmp/mediareviewer",
    hiddenPickerPaths: ["/proc"],
    deletionWorkers: 2,
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
  hiddenPickerPaths: ["/proc"],
};

const mediaItemsResponse: MediaItemsResponse = {
  path: "/home/michaelmoore/trailcam",
  count: 2,
  ignoredCount: 2,
  items: [
    {
      path: "/home/michaelmoore/trailcam/DCIM/100MEDIA/frame001.jpg",
      name: "frame001.jpg",
      mediaType: "image",
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
  ],
};

const mediaActionResponse: MediaActionResponse = {
  path: "/home/michaelmoore/trailcam/DCIM/100MEDIA/frame001.jpg",
  action: "seen",
  status: {
    locked: false,
    trashed: false,
    seen: true,
  },
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

      if (url.startsWith("/api/media-items?")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mediaItemsResponse),
        });
      }

      if (url.endsWith("/api/media-actions")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mediaActionResponse),
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
  });

  it("loads review paths and scans media items", async () => {
    const user = userEvent.setup();
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("Trailcam review dashboard")).toBeInTheDocument();
      expect(screen.getByLabelText("Known path")).toHaveValue("/home/michaelmoore/trailcam");
    });

    await user.click(screen.getByRole("button", { name: "Scan media" }));

    await waitFor(() => {
      expect(screen.getByText("frame001.jpg")).toBeInTheDocument();
      expect(screen.getByText(/Ignored while scanning: 2/i)).toBeInTheDocument();
    });
  });

  it("applies seen action to a media item", async () => {
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
});
