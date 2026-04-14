import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TrashProgressDialog } from "../TrashProgressDialog";
import type { TrashProgressEvent } from "../api/types";

const noOp = (): void => {
  // intentional no-op stub for unused callbacks
};

afterEach(() => {
  cleanup();
});

describe("TrashProgressDialog", () => {
  it("returns null when isOpen is false", () => {
    const { container } = render(
      <TrashProgressDialog
        isOpen={false}
        isRunning={false}
        events={[]}
        onClose={noOp}
        onAbort={noOp}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows dialog when isOpen is true", () => {
    render(
      <TrashProgressDialog
        isOpen={true}
        isRunning={false}
        events={[]}
        onClose={noOp}
        onAbort={noOp}
      />,
    );
    expect(screen.getByRole("dialog", { name: "Empty trash progress" })).toBeInTheDocument();
  });

  it("shows spinner and Running label while isRunning", () => {
    const { container } = render(
      <TrashProgressDialog
        isOpen={true}
        isRunning={true}
        events={[]}
        onClose={noOp}
        onAbort={noOp}
      />,
    );
    expect(screen.getByText("Running…")).toBeInTheDocument();
    expect(container.querySelector(".spinner-border")).not.toBeNull();
  });

  it("shows Complete label when done event received and not running", () => {
    const events: TrashProgressEvent[] = [
      { type: "done", deleted: 3, errors: 0 },
    ];
    render(
      <TrashProgressDialog
        isOpen={true}
        isRunning={false}
        events={events}
        onClose={noOp}
        onAbort={noOp}
      />,
    );
    expect(screen.getByText("Complete")).toBeInTheDocument();
  });

  it("renders deleted and error event entries in the log", () => {
    const events: TrashProgressEvent[] = [
      { type: "deleted", path: "/media/.trash/photo.jpg" },
      { type: "error", path: "/media/.trash/locked.mp4", message: "Permission denied" },
    ];
    render(
      <TrashProgressDialog
        isOpen={true}
        isRunning={false}
        events={events}
        onClose={noOp}
        onAbort={noOp}
      />,
    );
    const log = screen.getByTestId("trash-progress-log");
    expect(log).toHaveTextContent(".trash/photo.jpg");
    expect(log).toHaveTextContent("Permission denied");
  });

  it("shows deleted count in stats bar", () => {
    const events: TrashProgressEvent[] = [
      { type: "deleted", path: "/media/.trash/a.jpg" },
      { type: "deleted", path: "/media/.trash/b.jpg" },
    ];
    render(
      <TrashProgressDialog
        isOpen={true}
        isRunning={true}
        events={events}
        onClose={noOp}
        onAbort={noOp}
      />,
    );
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("shows Abort button while running and calls onAbort when clicked", async () => {
    const user = userEvent.setup();
    const onAbort = vi.fn();
    render(
      <TrashProgressDialog
        isOpen={true}
        isRunning={true}
        events={[]}
        onClose={noOp}
        onAbort={onAbort}
      />,
    );
    await user.click(screen.getByRole("button", { name: /abort/i }));
    expect(onAbort).toHaveBeenCalledOnce();
  });

  it("shows Close button when not running and calls onClose when clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <TrashProgressDialog
        isOpen={true}
        isRunning={false}
        events={[{ type: "done", deleted: 0, errors: 0 }]}
        onClose={onClose}
        onAbort={noOp}
      />,
    );
    // Use getByText to target the footer Close button (not the X btn-close which uses aria-label)
    await user.click(screen.getByText("Close"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when the X button is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <TrashProgressDialog
        isOpen={true}
        isRunning={false}
        events={[]}
        onClose={onClose}
        onAbort={noOp}
      />,
    );
    await user.click(screen.getByLabelText("Close"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("shows done summary line in the log", () => {
    const events: TrashProgressEvent[] = [
      { type: "done", deleted: 5, errors: 1 },
    ];
    render(
      <TrashProgressDialog
        isOpen={true}
        isRunning={false}
        events={events}
        onClose={noOp}
        onAbort={noOp}
      />,
    );
    const log = screen.getByTestId("trash-progress-log");
    expect(log).toHaveTextContent("Done — 5 files deleted");
    expect(log).toHaveTextContent("1 errors");
  });
});
