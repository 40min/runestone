import { useState } from "react";
import { useAuth as useAuthContext } from "../context/AuthContext";
import { useApi } from "../utils/api";
import type { UserData } from "../types/auth";

interface LoginCredentials {
  email: string;
  password: string;
}

interface RegisterData extends LoginCredentials {
  name?: string;
  surname?: string;
}

interface UpdateProfileData {
  name?: string | null;
  surname?: string | null;
  timezone?: string;
  password?: string;
  email?: string;
  personal_info?: Record<string, unknown> | null;
  areas_to_improve?: Record<string, unknown> | null;
  knowledge_strengths?: Record<string, unknown> | null;
}

interface UseAuthActionsReturn {
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  updateProfile: (updates: UpdateProfileData) => Promise<void>;
  clearMemory: (category?: string) => Promise<void>;
  logout: () => void;
  loading: boolean;
  error: string | null;
}

export const useAuthActions = (): UseAuthActionsReturn => {
  const { login: contextLogin, logout: contextLogout } = useAuthContext();
  const { post, get, put, delete: apiDelete } = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = async (credentials: LoginCredentials) => {
    setLoading(true);
    setError(null);

    try {
      const data = await post<{ access_token: string }>(
        "/api/auth/",
        credentials
      );

      // Get fresh user data with the new token using explicit token override
      const userData = await get<UserData>("/api/me", {
        token: data.access_token,
      });

      contextLogin(data.access_token, userData);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "An error occurred";
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const register = async (data: RegisterData) => {
    setLoading(true);
    setError(null);

    try {
      await post("/api/auth/register", data);
      await login({ email: data.email, password: data.password });
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "An error occurred";
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const updateProfile = async (updates: UpdateProfileData) => {
    setLoading(true);
    setError(null);

    try {
      const updatedUserData = await put<UserData>("/api/me", updates);

      const currentToken = localStorage.getItem("runestone_token");
      if (currentToken) {
        contextLogin(currentToken, updatedUserData);
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "An error occurred";
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const clearMemory = async (category?: string) => {
    setLoading(true);
    try {
      const url = category
        ? `/api/me/memory?category=${category}`
        : `/api/me/memory`;

      await apiDelete(url);

      // Refresh user data
      const updatedUserData = await get<UserData>("/api/me");
      const currentToken = localStorage.getItem("runestone_token");
      if (currentToken) {
        contextLogin(currentToken, updatedUserData);
      }
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to clear memory";
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    contextLogout();
  };

  return {
    login,
    register,
    updateProfile,
    clearMemory,
    logout,
    loading,
    error,
  };
};

export type { LoginCredentials, RegisterData };
