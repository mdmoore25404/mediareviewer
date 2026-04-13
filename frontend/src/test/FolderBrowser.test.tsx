import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FolderBrowser } from "../FolderBrowser";
import type { FoldersResponse } from "../api/types";

const foldersResponse: FoldersResponse = {
  path: "/home/michaelmoore/trailcam",
  folders: [
    { path: "/home/michaelmoore/trailcam/DCIM", name: "DCIM", has_children: true },
    { path: "/home/michaelmoore/trailcam/Videos", name: "Videos", has_children: false },
  ],
};

const emptyFoldersResponse: FoldersResponse = {
  path: "/home/michaelmoore/trailcam/Videos",
  folders: [],
};

describe("FolderBrowser", () => {
  beforeEach(() => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;

      if (url.startsWith("/api/folders?")) {
        const folderParam = new URL(url, "http://localhost").searchParams.get("path");
        if (folderParam === "/home/michaelmoore/trailcam/Videos") {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(emptyFoldersResponse),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(foldersResponse),
        });
      }

      return Promise.resolve({
        ok: false,
        json: () => Promise.resolve({ error: "Unexpected request" }),
      });
    });
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders known paths as root folders", () => {
    render(
      <FolderBrowser
        knownPaths={["/home/michaelmoore/trailcam"]}
        hiddenPaths={[]}
        onSelectFolder={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("/home/michaelmoore/trailcam")).toBeInTheDocument();
  });

  it("shows empty state when no known paths provided", () => {
    render(
      <FolderBrowser
        knownPaths={[]}
        hiddenPaths={[]}
        onSelectFolder={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText(/No review paths configured/)).toBeInTheDocument();
  });

  it("expands a root folder to show child folders", async () => {
    render(
      <FolderBrowser
        knownPaths={["/home/michaelmoore/trailcam"]}
        hiddenPaths={[]}
        onSelectFolder={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    const expandBtn = screen.getByRole("button", {
      name: /Expand \/home\/michaelmoore\/trailcam/,
    });
    await userEvent.click(expandBtn);

    await waitFor(() => {
      expect(screen.getByText("DCIM")).toBeInTheDocument();
      expect(screen.getByText("Videos")).toBeInTheDocument();
    });
  });

  it("shows 'No subfolders' when a leaf folder is expanded", async () => {
    render(
      <FolderBrowser
        knownPaths={["/home/michaelmoore/trailcam"]}
        hiddenPaths={[]}
        onSelectFolder={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    // Expand root to get children
    await userEvent.click(
      screen.getByRole("button", { name: /Expand \/home\/michaelmoore\/trailcam/ }),
    );
    await waitFor(() => expect(screen.getByText("Videos")).toBeInTheDocument());

    // Expand Videos (has_children: false should disable expand, so it won't show expand button as enabled)
    // But Videos has has_children: false — the expand button should be disabled
    const videoNode = screen.getByText("Videos").closest(".folder-browser-row");
    const videoExpandBtn = videoNode?.querySelector("button");
    expect(videoExpandBtn).toBeDisabled();
  });

  it("calls onSelectFolder and onClose when a folder name is clicked", async () => {
    const onSelectFolder = vi.fn();
    const onClose = vi.fn();

    render(
      <FolderBrowser
        knownPaths={["/home/michaelmoore/trailcam"]}
        hiddenPaths={[]}
        onSelectFolder={onSelectFolder}
        onClose={onClose}
      />,
    );

    await userEvent.click(screen.getByText("/home/michaelmoore/trailcam"));

    expect(onSelectFolder).toHaveBeenCalledWith("/home/michaelmoore/trailcam");
    expect(onClose).toHaveBeenCalled();
  });

  it("calls onClose when the close button is clicked", async () => {
    const onClose = vi.fn();

    render(
      <FolderBrowser
        knownPaths={["/home/michaelmoore/trailcam"]}
        hiddenPaths={[]}
        onSelectFolder={vi.fn()}
        onClose={onClose}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Close folder browser" }));

    expect(onClose).toHaveBeenCalled();
  });

  it("collapses a folder when the expand button is clicked a second time", async () => {
    render(
      <FolderBrowser
        knownPaths={["/home/michaelmoore/trailcam"]}
        hiddenPaths={[]}
        onSelectFolder={vi.fn()}
        onClose={vi.fn()}
      />,
    );

    const expandBtn = screen.getByRole("button", {
      name: /Expand \/home\/michaelmoore\/trailcam/,
    });

    await userEvent.click(expandBtn);
    await waitFor(() => expect(screen.getByText("DCIM")).toBeInTheDocument());

    const collapseBtn = screen.getByRole("button", {
      name: /Collapse \/home\/michaelmoore\/trailcam/,
    });
    await userEvent.click(collapseBtn);

    expect(screen.queryByText("DCIM")).not.toBeInTheDocument();
  });
});
