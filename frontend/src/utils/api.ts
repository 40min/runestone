import { useCallback } from 'react';
import { API_BASE_URL } from '../config';
import { useAuth } from '../context/AuthContext';

// API client options interface
export interface ApiClientOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE';
  body?: unknown;
  headers?: Record<string, string>;
}

// Type for validation error items
interface ValidationErrorItem {
  msg?: string;
  [key: string]: unknown;
}

// Custom hook that provides authenticated API client
export const useApi = () => {
  const { token, logout } = useAuth();

  const apiClient = useCallback(async <T>(
    endpoint: string,
    options: ApiClientOptions = {}
  ): Promise<T> => {
    const url = `${API_BASE_URL}${endpoint}`;

    const headers: Record<string, string> = {
      ...(options.headers || {}),
    };

    // Automatically inject Authorization header if token exists
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const requestOptions: RequestInit = {
      method: options.method || 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
    };

    // Add body if provided and not GET method
    if (options.body && options.method !== 'GET') {
      requestOptions.body = JSON.stringify(options.body);
    }

    const response = await fetch(url, requestOptions);

    // Handle 401 Unauthorized - automatically logout
    if (response.status === 401) {
      logout();
      // Continue to error handling below to use backend error message
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: 'An error occurred',
      }));

      // Handle different error formats
      let errorMessage = 'Request failed';
      if (typeof error.detail === 'string') {
        errorMessage = error.detail;
      } else if (error.detail && typeof error.detail === 'object') {
        // Handle validation errors from FastAPI with multiple fields
        if (Array.isArray(error.detail)) {
          errorMessage = error.detail.map((err: ValidationErrorItem) =>
            typeof err === 'string' ? err : (err.msg ?? 'Validation error')
          ).join(', ');
        } else if (error.detail.message) {
          errorMessage = error.detail.message;
        } else {
          errorMessage = JSON.stringify(error.detail);
        }
      } else if (error.message) {
        errorMessage = error.message;
      }

      throw new Error(errorMessage);
    }

    return response.status === 204 ? null : response.json();
  }, [token, logout]);

  return apiClient;
};

// API utility for standalone calls (non-hook contexts)
// @deprecated Use useApi hook instead for automatic authentication
export const apiRequest = async <T>(
  endpoint: string,
  options: RequestInit = {},
  authToken?: string | null
): Promise<T> => {
  const url = `${API_BASE_URL}${endpoint}`;

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string> || {}),
  };

  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: 'An error occurred',
    }));

    // Handle different error formats
    let errorMessage = 'Request failed';
    if (typeof error.detail === 'string') {
      errorMessage = error.detail;
    } else if (error.detail && typeof error.detail === 'object') {
      // Handle validation errors from FastAPI with multiple fields
      if (Array.isArray(error.detail)) {
        errorMessage = error.detail.map((err: ValidationErrorItem) =>
          typeof err === 'string' ? err : err.msg || 'Validation error'
        ).join(', ');
      } else if (error.detail.message) {
        errorMessage = error.detail.message;
      } else {
        errorMessage = JSON.stringify(error.detail);
      }
    } else if (error.message) {
      errorMessage = error.message;
    }

    throw new Error(errorMessage);
  }

  return response.status === 204 ? null : response.json();
};
