import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import api, {
  loginUser,
  logoutUser,
  refreshSession,
  registerUser,
  setAuthSession,
} from "../api/client";

const AuthContext = createContext(null);

const storedSession = () => {
  try {
    return JSON.parse(localStorage.getItem("testpilot-session") || "null");
  } catch {
    return null;
  }
};

export function AuthProvider({ children }) {
  const [session, setSession] = useState(storedSession);
  const [loading, setLoading] = useState(true);

  const persistSession = useCallback((nextSession, remember = true) => {
    setSession(nextSession);
    setAuthSession(nextSession);
    if (nextSession && remember) {
      localStorage.setItem("testpilot-session", JSON.stringify(nextSession));
    } else {
      localStorage.removeItem("testpilot-session");
    }
  }, []);

  useEffect(() => {
    setAuthSession(session);
    setLoading(false);
  }, [session]);

  useEffect(() => {
    const id = api.interceptors.response.use(
      (response) => response,
      async (error) => {
        const original = error.config;
        if (error.response?.status !== 401 || original?._retry || !session?.refresh_token) {
          return Promise.reject(error);
        }

        original._retry = true;
        const refreshed = await refreshSession(session.refresh_token);
        persistSession(refreshed, true);
        original.headers.Authorization = `Bearer ${refreshed.access_token}`;
        return api(original);
      },
    );

    return () => api.interceptors.response.eject(id);
  }, [persistSession, session]);

  const login = async (payload) => {
    const result = await loginUser(payload);
    persistSession(result, payload.remember_me);
    return result;
  };

  const register = async (payload) => {
    const result = await registerUser(payload);
    persistSession(result, true);
    return result;
  };

  const logout = async () => {
    try {
      if (session?.access_token) await logoutUser();
    } finally {
      persistSession(null, false);
    }
  };

  const value = useMemo(
    () => ({
      session,
      user: session?.user || null,
      isAuthenticated: Boolean(session?.access_token),
      loading,
      login,
      register,
      logout,
      setSession: persistSession,
    }),
    [loading, persistSession, session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return context;
}
