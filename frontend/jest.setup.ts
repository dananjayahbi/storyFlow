import '@testing-library/jest-dom';

// ── jsdom polyfills for browser APIs ──

// ResizeObserver is not implemented in jsdom but required by Radix UI components
global.ResizeObserver = class ResizeObserver {
  private cb: ResizeObserverCallback;
  constructor(cb: ResizeObserverCallback) {
    this.cb = cb;
  }
  observe() {}
  unobserve() {}
  disconnect() {}
};

// HTMLMediaElement methods are not implemented in jsdom — stub them globally
// so every test that renders <audio> (e.g. AudioPlayer, SegmentCard) won't
// emit noisy "Not implemented" console errors.
Object.defineProperty(window.HTMLMediaElement.prototype, 'play', {
  configurable: true,
  value: () => Promise.resolve(),
});
Object.defineProperty(window.HTMLMediaElement.prototype, 'pause', {
  configurable: true,
  value: () => {},
});
Object.defineProperty(window.HTMLMediaElement.prototype, 'load', {
  configurable: true,
  value: () => {},
});
