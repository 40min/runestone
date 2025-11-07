import { vi } from 'vitest';

export const createMockAuthContext = (overrides = {}) => ({
  token: null,
  userData: null,
  login: vi.fn(),
  logout: vi.fn(),
  isAuthenticated: () => false,
  ...overrides,
});

export const createMockUseAuthActions = (overrides = {}) => ({
  register: vi.fn(),
  login: vi.fn(),
  updateProfile: vi.fn(),
  logout: vi.fn(),
  loading: false,
  error: null,
  ...overrides,
});

export const createMockUserData = (overrides = {}) => ({
  id: 1,
  email: 'test@example.com',
  name: 'Test',
  surname: 'User',
  timezone: 'UTC',
  pages_recognised_count: 0,
  words_in_learn_count: 0,
  words_learned_count: 0,
  ...overrides,
});

export const setupMockLocalStorage = () => {
  const mockLocalStorage = {
    getItem: vi.fn(),
    setItem: vi.fn(),
    removeItem: vi.fn(),
    clear: vi.fn(),
  };
  Object.defineProperty(window, 'localStorage', {
    value: mockLocalStorage,
    writable: true,
  });
  return mockLocalStorage;
};

export const setupAuthenticatedLocalStorage = (userData = createMockUserData()) => {
  const mockLocalStorage = setupMockLocalStorage();
  mockLocalStorage.getItem.mockImplementation((key: string) => {
    if (key === 'runestone_token') return 'test-token';
    if (key === 'runestone_user_data') return JSON.stringify(userData);
    return null;
  });
  return mockLocalStorage;
};
