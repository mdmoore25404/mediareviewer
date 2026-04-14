import { type ReactElement, useEffect, useRef } from "react";

import type { TrashProgressEvent } from "./api/types";

interface TrashProgressDialogProps {
  /** Whether the dialog overlay is visible. */
  isOpen: boolean;
  /** Whether the empty-trash stream is still running. */
  isRunning: boolean;
  /** Accumulated NDJSON events from the stream. */
  events: TrashProgressEvent[];
  /** Hide the dialog overlay (stream continues running if isRunning is true). */
  onClose: () => void;
  /** Abort the running stream. */
  onAbort: () => void;
}

function eventLabel(event: TrashProgressEvent): ReactElement {
  const shortPath = event.path ? event.path.split("/").slice(-2).join("/") : "";
  if (event.type === "deleting") {
    return (
      <span className="text-secondary">
        <i className="fa-solid fa-circle-notch fa-spin me-2" aria-hidden="true" />
        {shortPath}
      </span>
    );
  }
  if (event.type === "deleted") {
    return (
      <span className="text-success">
        <i className="fa-solid fa-check me-2" aria-hidden="true" />
        {shortPath}
      </span>
    );
  }
  if (event.type === "skipped") {
    return (
      <span className="text-warning">
        <i className="fa-solid fa-lock me-2" aria-hidden="true" />
        {shortPath}
        <span className="text-secondary ms-1">(locked — skipped)</span>
      </span>
    );
  }
  if (event.type === "error") {
    return (
      <span className="text-danger">
        <i className="fa-solid fa-triangle-exclamation me-2" aria-hidden="true" />
        {shortPath}
        <span className="ms-1">{event.message}</span>
      </span>
    );
  }
  if (event.type === "done") {
    const noun = event.deleted === 1 ? "file" : "files";
    return (
      <span className="fw-semibold text-body">
        <i className="fa-solid fa-flag-checkered me-2" aria-hidden="true" />
        Done — {event.deleted} {noun} deleted
        {(event.errors ?? 0) > 0 && (
          <span className="text-danger ms-1">({event.errors} errors)</span>
        )}
      </span>
    );
  }
  return <span>{event.type}</span>;
}

export function TrashProgressDialog({
  isOpen,
  isRunning,
  events,
  onClose,
  onAbort,
}: TrashProgressDialogProps): ReactElement | null {
  const logRef = useRef<HTMLDivElement>(null);

  // Auto-scroll the log as events arrive
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events]);

  if (!isOpen) return null;

  const deletedCount = events.filter((e) => e.type === "deleted").length;
  const errorCount = events.filter((e) => e.type === "error").length;
  const doneEvent = events.find((e) => e.type === "done");

  return (
    <div
      className="modal d-block"
      role="dialog"
      aria-modal="true"
      aria-label="Empty trash progress"
      style={{ backgroundColor: "rgba(0,0,0,0.5)" }}
    >
      <div className="modal-dialog modal-dialog-scrollable">
        <div className="modal-content">
          <div className="modal-header">
            <h5 className="modal-title">
              <i className="fa-solid fa-trash me-2" aria-hidden="true" />
              Empty Trash
              {isRunning && (
                <span className="spinner-border spinner-border-sm ms-2" role="status" aria-hidden="true" />
              )}
            </h5>
            <button
              type="button"
              className="btn-close"
              aria-label="Close"
              onClick={onClose}
            />
          </div>

          <div className="modal-body p-0">
            <div className="px-3 py-2 border-bottom d-flex gap-3 small text-secondary">
              <span>
                <i className="fa-solid fa-check text-success me-1" aria-hidden="true" />
                Deleted: <strong className="text-body">{deletedCount}</strong>
              </span>
              {errorCount > 0 && (
                <span>
                  <i className="fa-solid fa-triangle-exclamation text-danger me-1" aria-hidden="true" />
                  Errors: <strong className="text-danger">{errorCount}</strong>
                </span>
              )}
              {doneEvent && !isRunning && (
                <span className="ms-auto text-success fw-semibold">Complete</span>
              )}
              {isRunning && (
                <span className="ms-auto text-secondary">Running…</span>
              )}
            </div>

            <div
              ref={logRef}
              className="p-3 small font-monospace overflow-auto"
              style={{ maxHeight: "18rem" }}
              data-testid="trash-progress-log"
            >
              {events.length === 0 && isRunning && (
                <span className="text-secondary">Scanning for trashed files…</span>
              )}
              {events
                .filter((e) => e.type !== "done")
                .map((event, index) => (
                  <div key={index} className="mb-1">
                    {eventLabel(event)}
                  </div>
                ))}
              {doneEvent && (
                <div className="mt-2 pt-2 border-top">{eventLabel(doneEvent)}</div>
              )}
            </div>
          </div>

          <div className="modal-footer">
            {isRunning ? (
              <button
                type="button"
                className="btn btn-outline-danger"
                onClick={onAbort}
              >
                <i className="fa-solid fa-stop me-2" aria-hidden="true" />
                Abort
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-secondary"
                onClick={onClose}
              >
                Close
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
