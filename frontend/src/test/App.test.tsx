import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import type { HealthResponse } from "../api/types";

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

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(healthResponse),
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders API status returned by the backend", async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("Scaffold ready for the first review workflow slice.")).toBeInTheDocument();
      expect(screen.getByText("ok")).toBeInTheDocument();
      expect(screen.getByText("/tmp/mediareviewer")).toBeInTheDocument();
    });
  });
});
