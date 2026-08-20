/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { apiRequest, clearSession, loginRequest, refreshAccessToken } from "../api/client";
import type { User } from "../api/types";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<User>;
  endLocalSession: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function loadCurrentUser(): Promise<User> {
  return apiRequest<User>("/users/me", { retryAuthentication: false });
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<User | null>(null);

  const endLocalSession = useCallback(() => {
    clearSession();
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  const refreshUser = useCallback(async () => {
    const currentUser = await loadCurrentUser();
    setUser(currentUser);
    setStatus("authenticated");
    return currentUser;
  }, []);

  useEffect(() => {
    let active = true;
    void refreshAccessToken()
      .then(loadCurrentUser)
      .then((currentUser) => {
        if (!active) return;
        setUser(currentUser);
        setStatus("authenticated");
      })
      .catch(() => {
        if (!active) return;
        clearSession();
        setUser(null);
        setStatus("unauthenticated");
      });
    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    await loginRequest(email, password);
    const currentUser = await loadCurrentUser();
    setUser(currentUser);
    setStatus("authenticated");
    return currentUser;
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiRequest<void>("/api/v1/auth/logout", {
        method: "POST",
        retryAuthentication: false,
      });
    } finally {
      endLocalSession();
    }
  }, [endLocalSession]);

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, login, logout, refreshUser, endLocalSession }),
    [endLocalSession, login, logout, refreshUser, status, user],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
