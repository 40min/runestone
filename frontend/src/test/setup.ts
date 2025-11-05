import React from 'react';
import '@testing-library/jest-dom';

// Mock URL.createObjectURL and URL.revokeObjectURL
Object.defineProperty(window.URL, 'createObjectURL', {
  writable: true,
  value: vi.fn(() => 'mock-url'),
});

Object.defineProperty(window.URL, 'revokeObjectURL', {
  writable: true,
  value: vi.fn(),
});

// Mock window.alert
Object.defineProperty(window, 'alert', {
  writable: true,
  value: vi.fn(),
});

// Helper to create test wrapper with AuthProvider
export const createAuthWrapper = () => {
  // Dynamic import to avoid circular dependencies in tests
  let AuthProvider: React.ComponentType<{ children: React.ReactNode }>;
  import('../context/AuthContext').then(module => {
    AuthProvider = module.AuthProvider;
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(AuthProvider!, null, children);
};
