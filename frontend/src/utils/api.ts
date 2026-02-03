import { useCallback } from "react";
import { API_BASE_URL } from "../config";
import { useAuth } from "../context/AuthContext";

// API client options interface
export interface ApiClientOptions {
  method?: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  body?: unknown;
  headers?: Record<string, string>;
  token?: string; // Allow explicit token override
}

// Type for validation error items
interface ValidationErrorItem {
  msg?: string;
  [key: string]: unknown;
}

// Extract error message handling into a reusable function
const extractErrorMessage = (error: Record<string, unknown>): string => {
  const detail = error.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (detail && typeof detail === "object") {
    // Handle validation errors from FastAPI with multiple fields
    if (Array.isArray(detail)) {
      return (detail as ValidationErrorItem[])
        .map((err: ValidationErrorItem | string) =>
          typeof err === "string" ? err : err.msg ?? "Validation error"
        )
        .join(", ");
    }

    const detailObj = detail as Record<string, unknown>;
    if (typeof detailObj.message === "string") {
      return detailObj.message;
    }

    return JSON.stringify(detail);
  }

  if (typeof error.message === "string") {
    return error.message;
  }

  return "Request failed";
};

// Core API request function - can be used with or without auth context
const makeRequest = async <T>(
  endpoint: string,
  options: ApiClientOptions,
  contextToken: string | null,
  logout?: () => void
): Promise<T> => {
  // Normalize slashes: ensure exactly one slash between API_BASE_URL and endpoint
  const base = API_BASE_URL.replace(/\/+$/, "");
  const path = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const url = `${base}${path}`;

  // Use explicit token if provided, otherwise fall back to context token
  const authToken = options.token ?? contextToken;

  const isFormData = options.body instanceof FormData;

  const headers: Record<string, string> = {
    ...options.headers,
  };

  if (!isFormData) {
    headers["Content-Type"] = "application/json";
  }

  if (authToken) {
    headers["Authorization"] = `Bearer ${authToken}`;
  }

  const requestOptions: RequestInit = {
    method: options.method || "GET",
    headers,
  };

  // Add body if provided and not GET method
  if (options.body && options.method !== "GET") {
    requestOptions.body = isFormData
      ? (options.body as FormData)
      : JSON.stringify(options.body);
  }

  const response = await fetch(url, requestOptions);

  // Handle 401 Unauthorized - automatically logout if logout function provided
  if (response.status === 401 && logout) {
    logout();
    // Continue to error handling below to use backend error message
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: "An error occurred",
    }));

    throw new Error(extractErrorMessage(error));
  }

  // Handle 204 No Content responses
  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
};

// Custom hook that provides authenticated API client
export const useApi = () => {
  const { token, logout } = useAuth();

  // Main API client for requests that return data
  const apiClient = useCallback(
    async <T>(endpoint: string, options: ApiClientOptions = {}): Promise<T> => {
      return makeRequest<T>(endpoint, options, token, logout);
    },
    [token, logout]
  );

  // Specialized DELETE method that doesn't require a return type
  const apiDelete = useCallback(
    async (
      endpoint: string,
      options?: Omit<ApiClientOptions, "method">
    ): Promise<void> => {
      await apiClient(endpoint, { ...options, method: "DELETE" });
    },
    [apiClient]
  );

  // Convenience methods for common operations
  const get = useCallback(
    async <T>(
      endpoint: string,
      options?: Omit<ApiClientOptions, "method" | "body">
    ): Promise<T> => {
      return apiClient<T>(endpoint, { ...options, method: "GET" });
    },
    [apiClient]
  );

  const post = useCallback(
    async <T>(
      endpoint: string,
      body?: unknown,
      options?: Omit<ApiClientOptions, "method" | "body">
    ): Promise<T> => {
      return apiClient<T>(endpoint, { ...options, body, method: "POST" });
    },
    [apiClient]
  );

  const put = useCallback(
    async <T>(
      endpoint: string,
      body?: unknown,
      options?: Omit<ApiClientOptions, "method" | "body">
    ): Promise<T> => {
      return apiClient<T>(endpoint, { ...options, body, method: "PUT" });
    },
    [apiClient]
  );

  const patch = useCallback(
    async <T>(
      endpoint: string,
      body?: unknown,
      options?: Omit<ApiClientOptions, "method" | "body">
    ): Promise<T> => {
      return apiClient<T>(endpoint, { ...options, body, method: "PATCH" });
    },
    [apiClient]
  );

  return {
    apiClient,
    delete: apiDelete,
    get,
    post,
    put,
    patch,
  };
};
