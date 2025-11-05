import { useState } from 'react';
import { API_BASE_URL } from '../config';
import { useAuth as useAuthContext } from '../context/AuthContext';

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

interface UseAuthActionsReturn {
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  updateProfile: (updates: Partial<UserData> & { password?: string }) => Promise<void>;
  logout: () => void;
  loading: boolean;
  error: string | null;
}

export const useAuthActions = (): UseAuthActionsReturn => {
  const { login: contextLogin, logout: contextLogout } = useAuthContext();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = async (credentials: LoginCredentials) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/auth/token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(credentials),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({ detail: 'Login failed' }));
        throw new Error(data.detail || 'Login failed');
      }

      const data = await response.json();

      // Fetch user data
      const userResponse = await fetch(`${API_BASE_URL}/users/me`, {
        headers: {
          Authorization: `Bearer ${data.access_token}`,
        },
      });

      if (!userResponse.ok) {
        throw new Error('Failed to fetch user data');
      }

      const userData: UserData = await userResponse.json();

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
      const response = await fetch(`${API_BASE_URL}/auth/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Registration failed' }));
        throw new Error(errorData.detail || 'Registration failed');
      }

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

  const updateProfile = async (updates: Partial<UserData> & { password?: string }) => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/users/me`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updates),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({ detail: 'Update failed' }));
        throw new Error(data.detail || 'Update failed');
      }

      const updatedUserData: UserData = await response.json();

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
