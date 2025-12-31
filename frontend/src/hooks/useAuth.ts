import { useState } from "react";
import { useAuth as useAuthContext } from "../context/AuthContext";
import { useApi, apiRequest } from "../utils/api";
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
}

interface UseAuthActionsReturn {
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  updateProfile: (updates: UpdateProfileData) => Promise<void>;
  logout: () => void;
  loading: boolean;
  error: string | null;
}

export const useAuthActions = (): UseAuthActionsReturn => {
  const { login: contextLogin, logout: contextLogout } = useAuthContext();
  const api = useApi();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = async (credentials: LoginCredentials) => {
    setLoading(true);
    setError(null);

    try {
      const data = await api<{ access_token: string }>("/api/auth/", {
        method: "POST",
        body: credentials,
      });

      // Get fresh user data with the new token (now properly authenticated!)
      const userData: UserData = await apiRequest<UserData>("/api/me", { method: "GET" }, data.access_token);

      // Update with real user data
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
      await api("/api/auth/register", {
        method: "POST",
        body: data,
      });

      // Automatically log in after successful registration
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
      const updatedUserData: UserData = await api<UserData>("/api/me", {
        method: "PUT",
        body: updates,
      });

      // Update stored user data
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

  const logout = () => {
    contextLogout();
  };

  return {
    login,
    register,
    updateProfile,
    logout,
    loading,
    error,
  };
};

export type { LoginCredentials, RegisterData };
