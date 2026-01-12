import React, {
  createContext,
  useState,
  useEffect,
  useContext,
  useCallback,
  type ReactNode,
} from "react";

import type { UserData } from "../types/auth";

// Auth context interface
interface AuthContextType {
  token: string | null;
  userData: UserData | null;
  login: (token: string, userData: UserData) => void;
  logout: () => void;
  isAuthenticated: () => boolean;
  updateUserData: (userData: UserData) => void;
}

// Create the context
const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Auth provider props
interface AuthProviderProps {
  children: ReactNode;
}

// Auth provider component
const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("runestone_token"));
  const [userData, setUserData] = useState<UserData | null>(() => {
    const stored = localStorage.getItem("runestone_user_data");
    if (stored) {
      try {
        return JSON.parse(stored);
      } catch (error) {
        console.error("Failed to parse stored user data:", error);
        localStorage.removeItem("runestone_user_data");
      }
    }
    return null;
  });

  // Keep in sync with localStorage if they change from other tabs
  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === "runestone_token") {
        setToken(e.newValue);
      }
      if (e.key === "runestone_user_data") {
        setUserData(e.newValue ? JSON.parse(e.newValue) : null);
      }
    };
    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, []);

  const login = useCallback((newToken: string, newUserData: UserData) => {
    setToken(newToken);
    setUserData(newUserData);

    // Store in localStorage
    localStorage.setItem("runestone_token", newToken);
    localStorage.setItem("runestone_user_data", JSON.stringify(newUserData));
  }, []);

  // Logout function
  const logout = useCallback(() => {
    setToken(null);
    setUserData(null);

    // Clear localStorage
    localStorage.removeItem("runestone_token");
    localStorage.removeItem("runestone_user_data");
  }, []);

  const isAuthenticated = useCallback((): boolean => {
    return token !== null && userData !== null;
  }, [token, userData]);

  const updateUserData = useCallback((newUserData: UserData): void => {
    setUserData(newUserData);
    localStorage.setItem("runestone_user_data", JSON.stringify(newUserData));
  }, []);

  const value = React.useMemo((): AuthContextType => ({
    token,
    userData,
    login,
    logout,
    isAuthenticated,
    updateUserData,
  }), [token, userData, login, logout, isAuthenticated, updateUserData]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

// useAuth hook
const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

// eslint-disable-next-line react-refresh/only-export-components
export { AuthProvider, AuthContext, useAuth };
export type { UserData };
