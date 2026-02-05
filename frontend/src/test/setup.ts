/* eslint-disable @typescript-eslint/no-explicit-any */
import "@testing-library/jest-dom";
import { vi, afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// Mock URL.createObjectURL and URL.revokeObjectURL
Object.defineProperty(window.URL, "createObjectURL", {
  writable: true,
  value: vi.fn(() => "mock-url"),
});

Object.defineProperty(window.URL, "revokeObjectURL", {
  writable: true,
  value: vi.fn(),
});

// Mock window.alert
Object.defineProperty(window, "alert", {
  writable: true,
  value: vi.fn(),
});

// Silence JSDOM media element not-implemented errors
Object.defineProperty(HTMLMediaElement.prototype, "play", {
  writable: true,
  value: vi.fn(() => Promise.resolve()),
});
Object.defineProperty(HTMLMediaElement.prototype, "pause", {
  writable: true,
  value: vi.fn(),
});
Object.defineProperty(HTMLMediaElement.prototype, "load", {
  writable: true,
  value: vi.fn(),
});

// Mock BroadcastChannel
class MockBroadcastChannel {
  name: string;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onmessageerror: ((event: MessageEvent) => void) | null = null;

  constructor(name: string) {
    this.name = name;
  }

  postMessage(_data: unknown) { // eslint-disable-line @typescript-eslint/no-unused-vars
    // In a real environment, this would broadcast to other tabs
    // For testing, we can just keep it as a no-op or simulate local reception if needed
  }
  close() {}
  addEventListener(type: string, listener: EventListenerOrEventListenerObject) {
    if (type === 'message') this.onmessage = listener as (event: MessageEvent) => void;
  }
  removeEventListener(_type: string, _listener: EventListenerOrEventListenerObject) { // eslint-disable-line @typescript-eslint/no-unused-vars
    if (_type === 'message') this.onmessage = null;
  }
  dispatchEvent() { return true; }
}

(globalThis as any).BroadcastChannel = MockBroadcastChannel;

// Mock crypto.randomUUID
if (!globalThis.crypto) {
  (globalThis as any).crypto = {};
}
if (!globalThis.crypto.randomUUID) {
  (globalThis as any).crypto.randomUUID = () => {
    return '12345678-1234-1234-1234-123456789012';
  };
}

// Global cleanup patterns
afterEach(() => {
  // Clean up React components after each test
  cleanup();
  // Only clear mock call history, don't reset implementations
  // This is faster and sufficient for most tests
  vi.clearAllMocks();
});

// Helper to create test wrapper with AuthProvider
export const createAuthWrapper = () => {
  // Dynamic import to avoid circular dependencies in tests
  let AuthProvider: React.ComponentType<{ children: React.ReactNode }>;
  import("../context/AuthContext").then((module) => {
    AuthProvider = module.AuthProvider;
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(AuthProvider!, null, children);
};
