import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, clearSession, loadSession, saveSession, setUnauthorizedHandler } from "../api/client.js";

const AuthContext = createContext(null);

export function homePath(user) {
  return user?.role === "ADMIN" ? "/admin" : "/teacher";
}

export function AuthProvider({ children }) {
  const [session, setSession] = useState(loadSession);
  const queryClient = useQueryClient();

  const logout = useCallback(() => {
    clearSession();
    setSession(null);
    queryClient.clear();
  }, [queryClient]);

  useEffect(() => setUnauthorizedHandler(logout), [logout]);

  // Tự đăng xuất khi token hết hạn
  useEffect(() => {
    if (!session) return undefined;
    const timer = setTimeout(logout, Math.max(0, session.expiresAt - Date.now()));
    return () => clearTimeout(timer);
  }, [session, logout]);

  const login = useCallback(async (username, password) => {
    const { data } = await api.post("/auth/login", { username, password });
    const next = { token: data.access_token, user: data.user, expiresAt: Date.now() + data.expires_in * 1000 };
    queryClient.clear();
    saveSession(next);
    setSession(next);
    return next.user;
  }, [queryClient]);

  const value = useMemo(() => ({ user: session?.user ?? null, login, logout }), [session, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
