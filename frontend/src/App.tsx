import { type ReactElement, useEffect, useState } from "react";

import { fetchHealth } from "./api/client";
import type { HealthResponse } from "./api/types";

function App(): ReactElement {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const abortController = new AbortController();

    const loadHealth = async (): Promise<void> => {
      try {
        const payload = await fetchHealth(abortController.signal);
        setHealth(payload);
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : "Unable to load API status.";
        setErrorMessage(message);
      } finally {
        setIsLoading(false);
      }
    };

    void loadHealth();
    return () => {
      abortController.abort();
    };
  }, []);

  return (
    <main className="app-shell">
      <section className="hero-panel container py-5">
        <div className="row justify-content-center">
          <div className="col-12 col-lg-10">
            <div className="status-card shadow-lg">
              <div className="d-flex flex-column flex-md-row justify-content-between gap-4">
                <div>
                  <p className="eyebrow">Media Reviewer</p>
                  <h1 className="display-5 fw-semibold">Scaffold ready for the first review workflow slice.</h1>
                  <p className="lead text-secondary mb-0">
                    The frontend is connected to the Flask API and ready to evolve into folder
                    selection, review, and deletion management.
                  </p>
                </div>
                <div className="summary-pill align-self-start">
                  <i className="fa-solid fa-mobile-screen-button me-2" aria-hidden="true" />
                  Mobile-first shell
                </div>
              </div>

              <div className="mt-4">
                {isLoading && <p className="mb-0">Loading API status...</p>}
                {!isLoading && errorMessage && (
                  <div className="alert alert-danger mb-0" role="alert">
                    {errorMessage}
                  </div>
                )}
                {!isLoading && health && (
                  <div className="row g-3">
                    <div className="col-12 col-md-4">
                      <article className="metric-card h-100">
                        <p className="metric-label">API status</p>
                        <p className="metric-value">{health.status}</p>
                      </article>
                    </div>
                    <div className="col-12 col-md-4">
                      <article className="metric-card h-100">
                        <p className="metric-label">State directory</p>
                        <p className="metric-value metric-value--small">{health.settings.stateDirectory}</p>
                      </article>
                    </div>
                    <div className="col-12 col-md-4">
                      <article className="metric-card h-100">
                        <p className="metric-label">Deletion workers</p>
                        <p className="metric-value">{health.settings.deletionWorkers}</p>
                      </article>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

export default App;
