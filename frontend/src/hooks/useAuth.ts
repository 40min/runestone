import { useState } from 'react';
import { useAuth as useAuthContext } from '../context/AuthContext';
import { useApi } from '../utils/api';

interface UserData {
  id: number;
  email: string;
  name: string | null;
  surname: string | null;
  timezone: string | null;
  pages_recognised_count: number;
}

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
      const data = await api<{ access_token: string }>('/auth/token', {
        method: 'POST',
        body: credentials,
      });

      // Fetch user data
      const userData: UserData = await api<UserData>('/users/me');

      // Store token and user data
      contextLogin(data.access_token, userData);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An error occurred';
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
      await api('/auth/register', {
        method: 'POST',
        body: data,
      });

      // Automatically log in after successful registration
      await login({ email: data.email, password: data.password });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An error occurred';
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
      const updatedUserData: UserData = await api<UserData>('/users/me', {
        method: 'PUT',
        body: updates,
      });

      // Update stored user data
      const currentToken = localStorage.getItem('runestone_token');
      if (currentToken) {
        contextLogin(currentToken, updatedUserData);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An error occurred';
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

export type { UserData, LoginCredentials, RegisterData };
