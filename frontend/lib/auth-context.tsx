"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type AuthUser } from "./api";

const STORAGE_KEY = "yeongjong_token";

interface AuthState {
  token: string | null;
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      setLoading(false);
      return;
    }
    api
      .me(stored)
      .then((u) => {
        setToken(stored);
        setUser(u);
      })
      .catch(() => localStorage.removeItem(STORAGE_KEY))
      .finally(() => setLoading(false));
  }, []);

  const applySession = (data: { access_token: string; user: AuthUser }) => {
    localStorage.setItem(STORAGE_KEY, data.access_token);
    setToken(data.access_token);
    setUser(data.user);
  };

  const login = async (email: string, password: string) => {
    applySession(await api.login({ email, password }));
  };

  const register = async (email: string, password: string, name: string) => {
    applySession(await api.register({ email, password, name, role: "BUSINESS_OWNER" }));
  };

  const logout = () => {
    localStorage.removeItem(STORAGE_KEY);
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ token, user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
