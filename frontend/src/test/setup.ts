import "@testing-library/jest-dom/vitest";

// IntersectionObserver is not implemented in jsdom; provide a no-op stub.
class IntersectionObserverStub {
  // eslint-disable-next-line @typescript-eslint/no-empty-function
  observe(): void {}
  // eslint-disable-next-line @typescript-eslint/no-empty-function
  unobserve(): void {}
  // eslint-disable-next-line @typescript-eslint/no-empty-function
  disconnect(): void {}
}
Object.defineProperty(globalThis, "IntersectionObserver", {
  writable: true,
  configurable: true,
  value: IntersectionObserverStub,
});

// window.matchMedia is not implemented in jsdom; stub it as a non-desktop (touch) device.
Object.defineProperty(globalThis, "matchMedia", {
  writable: true,
  configurable: true,
  value: (query: string): MediaQueryList =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: (): void => { /* stub */ },
      removeListener: (): void => { /* stub */ },
      addEventListener: (): void => { /* stub */ },
      removeEventListener: (): void => { /* stub */ },
      dispatchEvent: (): boolean => false,
    }) as MediaQueryList,
});
