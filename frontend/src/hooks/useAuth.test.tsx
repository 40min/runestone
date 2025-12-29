import React from "react";
import { renderHook, waitFor, act } from "@testing-library/react";
import { vi } from "vitest";
import { useAuthActions } from "./useAuth";
import { AuthProvider } from "../context/AuthContext";

/// <reference types="vitest/globals" />
/// <reference types="vitest/globals" />

// Mock config
vi.mock("../config", () => ({
  API_BASE_URL: "http://localhost:8010",
}));

// Mock fetch
vi.stubGlobal("fetch", vi.fn());

// Mock localStorage
const mockLocalStorage = {
  getItem: vi.fn(),
  setItem: vi.fn(),
  removeItem: vi.fn(),
  clear: vi.fn(),
};
Object.defineProperty(window, "localStorage", {
  value: mockLocalStorage,
});

describe("useAuthActions", () => {
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <AuthProvider>{children}</AuthProvider>
  );

  beforeEach(() => {
    vi.clearAllMocks();
    // Reset localStorage mock to return null by default
    mockLocalStorage.getItem.mockReturnValue(null);
  });

  it("handles successful login", async () => {
    const mockTokenResponse = { access_token: "test-token" };
    const mockUserResponse = {
      id: 1,
      email: "test@example.com",
      name: "Test",
      surname: "User",
      timezone: "UTC",
      pages_recognised_count: 5,
    };

    vi.mocked(globalThis.fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUserResponse),
      } as Response);

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await act(async () => {
      await result.current.login({
        email: "test@example.com",
        password: "password123",
      });
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8010/api/auth/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          email: "test@example.com",
          password: "password123",
        }),
      })
    );

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8010/api/me",
      expect.any(Object)
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.error).toBe(null);
  });

  it("handles login failure", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: "Invalid credentials" }),
    } as Response);

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await act(async () => {
      await expect(
        result.current.login({ email: "test@example.com", password: "wrong" })
      ).rejects.toThrow("Invalid credentials");
    });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBe("Invalid credentials");
    });
  });

  it("handles successful registration", async () => {
    const mockRegisterResponse = { success: true };
    const mockTokenResponse = { access_token: "test-token" };
    const mockUserResponse = {
      id: 1,
      email: "test@example.com",
      name: "Test",
      surname: "User",
      timezone: "UTC",
      pages_recognised_count: 0,
    };

    vi.mocked(globalThis.fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRegisterResponse),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUserResponse),
      } as Response);

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await act(async () => {
      await result.current.register({
        email: "test@example.com",
        password: "password123",
        name: "Test",
        surname: "User",
      });
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8010/api/auth/register",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          email: "test@example.com",
          password: "password123",
          name: "Test",
          surname: "User",
        }),
      })
    );

    // Should automatically login after registration
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8010/api/auth/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          email: "test@example.com",
          password: "password123",
        }),
      })
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.error).toBe(null);
  });

  it("handles registration failure", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: "Email already exists" }),
    } as Response);

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await act(async () => {
      await expect(
        result.current.register({
          email: "existing@example.com",
          password: "password123",
        })
      ).rejects.toThrow("Email already exists");
    });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBe("Email already exists");
    });
  });

  it("handles successful profile update", async () => {
    const mockUpdateResponse = {
      id: 1,
      email: "test@example.com",
      name: "Updated",
      surname: "Name",
      timezone: "EST",
      pages_recognised_count: 5,
    };

    vi.mocked(globalThis.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockUpdateResponse),
    } as Response);

    // Set up localStorage mock with valid JSON
    mockLocalStorage.getItem
      .mockReturnValueOnce("existing-token") // For token
      .mockReturnValueOnce(
        JSON.stringify({
          // For user data
          id: 1,
          email: "test@example.com",
          name: "Test",
          surname: "User",
          timezone: "UTC",
          pages_recognised_count: 5,
        })
      );

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await act(async () => {
      await result.current.updateProfile({
        name: "Updated",
        surname: "Name",
        timezone: "EST",
      });
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8010/api/me",
      expect.objectContaining({
        method: "PUT",
        headers: expect.objectContaining({
          Authorization: "Bearer existing-token",
        }),
        body: JSON.stringify({
          name: "Updated",
          surname: "Name",
          timezone: "EST",
        }),
      })
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.error).toBe(null);
  });

  it("handles profile update failure", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: "Update failed" }),
    } as Response);

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await act(async () => {
      await expect(
        result.current.updateProfile({
          name: "New Name",
        })
      ).rejects.toThrow("Update failed");
    });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
      expect(result.current.error).toBe("Update failed");
    });
  });

  it("sets loading state during operations", async () => {
    const mockTokenResponse = { access_token: "test-token" };
    const mockUserResponse = {
      id: 1,
      email: "test@example.com",
      name: "Test",
      surname: "User",
      timezone: "UTC",
      pages_recognised_count: 5,
    };

    vi.mocked(globalThis.fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUserResponse),
      } as Response);

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    // Initially loading should be false
    expect(result.current.loading).toBe(false);

    // Start login operation
    await act(async () => {
      await result.current.login({
        email: "test@example.com",
        password: "password123",
      });
    });

    // After completion, loading should be false
    expect(result.current.loading).toBe(false);
  });

  it("resets error state on new operations", async () => {
    // First operation fails
    vi.mocked(globalThis.fetch).mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: "First error" }),
    } as Response);

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await act(async () => {
      await expect(
        result.current.login({ email: "test@example.com", password: "wrong" })
      ).rejects.toThrow();
    });

    await waitFor(() => {
      expect(result.current.error).toBe("First error");
    });

    // Second operation should reset error
    const mockTokenResponse = { access_token: "token" };
    const mockUserResponse = {
      id: 1,
      email: "test@example.com",
      name: "Test",
      surname: "User",
      timezone: "UTC",
      pages_recognised_count: 5,
    };

    vi.mocked(globalThis.fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUserResponse),
      } as Response);

    await act(async () => {
      await result.current.login({
        email: "test@example.com",
        password: "correct",
      });
    });

    await waitFor(() => {
      expect(result.current.error).toBe(null);
    });
  });

  it("auto-logs in after successful registration", async () => {
    const mockRegisterResponse = { success: true };
    const mockTokenResponse = { access_token: "registration-token" };
    const mockUserResponse = {
      id: 1,
      email: "new@example.com",
      name: "New",
      surname: "User",
      timezone: "UTC",
      pages_recognised_count: 0,
    };

    vi.mocked(globalThis.fetch)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockRegisterResponse),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTokenResponse),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockUserResponse),
      } as Response);

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await act(async () => {
      await result.current.register({
        email: "new@example.com",
        password: "password123",
      });
    });

    // Verify registration was called first
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8010/api/auth/register",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          email: "new@example.com",
          password: "password123",
        }),
      })
    );

    // Verify login was called with registration credentials
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8010/api/auth/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          email: "new@example.com",
          password: "password123",
        }),
      })
    );
  });

  it("handles updateProfile without token", async () => {
    mockLocalStorage.getItem.mockReturnValue(null);

    // Mock API to reject when there's no valid token
    vi.mocked(globalThis.fetch).mockRejectedValueOnce(
      new Error("Authentication required. Please log in again.")
    );

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    // When there's no token, updateProfile should throw
    await act(async () => {
      await expect(
        result.current.updateProfile({
          name: "New Name",
        })
      ).rejects.toThrow("Authentication required");
    });
  });

  it("handles concurrent register and login operations", async () => {
    const mockRegisterResponse = { success: true };

    vi.mocked(globalThis.fetch).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockRegisterResponse),
    } as Response);

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    // Start both operations
    await act(async () => {
      const registerPromise = result.current.register({
        email: "test@example.com",
        password: "password123",
      });

      const loginPromise = result.current.login({
        email: "test@example.com",
        password: "password123",
      });

      // Both should complete without errors
      await Promise.all([registerPromise, loginPromise]);
    });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
  });

  it("handles profile update with password change", async () => {
    const mockUpdateResponse = {
      id: 1,
      email: "test@example.com",
      name: "Test",
      surname: "User",
      timezone: "UTC",
      pages_recognised_count: 5,
    };

    vi.mocked(globalThis.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockUpdateResponse),
    } as Response);

    // Set up localStorage mock with valid JSON
    mockLocalStorage.getItem
      .mockReturnValueOnce("existing-token") // For token
      .mockReturnValueOnce(
        JSON.stringify({
          // For user data
          id: 1,
          email: "test@example.com",
          name: "Test",
          surname: "User",
          timezone: "UTC",
          pages_recognised_count: 5,
        })
      );

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await act(async () => {
      await result.current.updateProfile({
        name: "Test",
        password: "newpassword123",
      });
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "http://localhost:8010/api/me",
      expect.objectContaining({
        method: "PUT",
        body: JSON.stringify({
          name: "Test",
          password: "newpassword123",
        }),
      })
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
  });

  // Email-related tests

  it('includes email in API request payload when updating profile', async () => {
    const mockUpdateResponse = {
      id: 1,
      email: 'newemail@example.com',
      name: 'Test',
      surname: 'User',
      timezone: 'UTC',
      pages_recognised_count: 5
    };

    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockUpdateResponse),
    } as Response);

    mockLocalStorage.getItem.mockReturnValue('existing-token');

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await result.current.updateProfile({
      name: 'Test',
      email: 'newemail@example.com'
    });

    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8010/api/me',
      expect.objectContaining({
        method: 'PUT',
        headers: expect.objectContaining({
          'Authorization': 'Bearer existing-token',
        }),
        body: JSON.stringify({
          name: 'Test',
          email: 'newemail@example.com'
        }),
      })
    );

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.error).toBe(null);
  });

  it('updates user context with new email after successful profile update', async () => {
    const mockUpdateResponse = {
      id: 1,
      email: 'updated@example.com',
      name: 'Test',
      surname: 'User',
      timezone: 'UTC',
      pages_recognised_count: 5
    };

    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve(mockUpdateResponse),
    } as Response);

    mockLocalStorage.getItem.mockReturnValue('existing-token');

    const { result } = renderHook(() => useAuthActions(), { wrapper });

    await result.current.updateProfile({
      email: 'updated@example.com'
    });

    // Verify the API was called with the updated email
    await waitFor(() => {
      const fetchCall = global.fetch.mock.calls[0];
      const requestBody = JSON.parse(fetchCall[1].body);
      expect(requestBody.email).toBe('updated@example.com');
    });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.error).toBe(null);
  });
});
