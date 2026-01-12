import React, {
  createContext,
  useState,
  useEffect,
  useContext,
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
  const [token, setToken] = useState<string | null>(null);
  const [userData, setUserData] = useState<UserData | null>(null);

  // Load token and user data from localStorage on mount
  useEffect(() => {
    const storedToken = localStorage.getItem("runestone_token");
    const storedUserData = localStorage.getItem("runestone_user_data");

    if (storedToken) {
      setToken(storedToken);
    }

    if (storedUserData) {
      try {
        setUserData(JSON.parse(storedUserData));
      } catch (error) {
        console.error("Failed to parse stored user data:", error);
        localStorage.removeItem("runestone_user_data");
      }
    }
  }, []);

  const login = (newToken: string, newUserData: UserData) => {
    setToken(newToken);
    setUserData(newUserData);

    // Store in localStorage
    localStorage.setItem("runestone_token", newToken);
    localStorage.setItem("runestone_user_data", JSON.stringify(newUserData));
  };

  // Logout function
  const logout = () => {
    setToken(null);
    setUserData(null);

    // Clear localStorage
    localStorage.removeItem("runestone_token");
    localStorage.removeItem("runestone_user_data");
  };

  const isAuthenticated = (): boolean => {
    return token !== null && userData !== null;
  };

  const updateUserData = (newUserData: UserData): void => {
    setUserData(newUserData);
    localStorage.setItem("runestone_user_data", JSON.stringify(newUserData));
  };

  const value: AuthContextType = {
    token,
    userData,
    login,
    logout,
    isAuthenticated,
    updateUserData,
  };

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
