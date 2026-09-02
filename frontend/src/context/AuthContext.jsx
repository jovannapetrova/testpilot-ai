import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import api, {
  getCurrentUser,
  loginUser,
  logoutUser,
  refreshSession,
  registerUser,
  setAuthSession,
} from "../api/client";

const AuthContext = createContext(null);
const LOCAL_SESSION_KEY = "testpilot-session";
const SESSION_SESSION_KEY = "testpilot-session-memory";
const SESSION_NOTICE_KEY = "testpilot-auth-notice";

const storedSession = () => {
  try {
    const local = JSON.parse(localStorage.getItem(LOCAL_SESSION_KEY) || "null");
    if (local) return { session: local, remember: true };
    const session = JSON.parse(sessionStorage.getItem(SESSION_SESSION_KEY) || "null");
    if (session) return { session, remember: false };
  } catch {
    // Corrupt browser storage should not block rendering the signed-out app.
  }
  return { session: null, remember: true };
};

export function AuthProvider({ children }) {
  const initial = storedSession();
  const [session, setSession] = useState(initial.session);
  const [rememberSession, setRememberSession] = useState(initial.remember);
  const [loading, setLoading] = useState(true);
  const [authNotice, setAuthNotice] = useState(() => {
    try {
      const notice = sessionStorage.getItem(SESSION_NOTICE_KEY) || "";
      sessionStorage.removeItem(SESSION_NOTICE_KEY);
      return notice;
    } catch {
      return "";
    }
  });

  const persistSession = useCallback((nextSession, remember = true) => {
    const normalized = nextSession ? { ...nextSession, remember_me: remember } : null;
    setSession(normalized);
    setRememberSession(Boolean(remember));
    setAuthSession(normalized);

    localStorage.removeItem(LOCAL_SESSION_KEY);
    sessionStorage.removeItem(SESSION_SESSION_KEY);

    if (normalized && remember) {
      localStorage.setItem(LOCAL_SESSION_KEY, JSON.stringify(normalized));
    } else if (normalized) {
      sessionStorage.setItem(SESSION_SESSION_KEY, JSON.stringify(normalized));
    }
  }, []);

  const expireSession = useCallback((message = "Your session has expired. Please sign in again.") => {
    persistSession(null, false);
    setAuthNotice(message);
    try {
      sessionStorage.setItem(SESSION_NOTICE_KEY, message);
    } catch {
      // Storage may be disabled; the in-memory notice still covers the current view.
    }
  }, [persistSession]);

  const refreshStoredSession = useCallback(async (currentSession, remember) => {
    const refreshed = await refreshSession(currentSession.refresh_token);
    persistSession(refreshed, remember);
    return refreshed;
  }, [persistSession]);

  useEffect(() => {
    let cancelled = false;

    const validateStoredSession = async () => {
      const stored = storedSession();
      if (!stored.session?.access_token) {
        persistSession(null, false);
        if (!cancelled) setLoading(false);
        return;
      }

      setAuthSession(stored.session);
      setRememberSession(stored.remember);

      try {
        const profile = await getCurrentUser();
        if (!cancelled) {
          persistSession({ ...stored.session, user: profile.user }, stored.remember);
        }
      } catch {
        try {
          if (!stored.session.refresh_token) throw new Error("No refresh token");
          await refreshStoredSession(stored.session, stored.remember);
        } catch {
          if (!cancelled) expireSession();
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    validateStoredSession();
    return () => {
      cancelled = true;
    };
  }, [expireSession, persistSession, refreshStoredSession]);

  useEffect(() => {
    if (!authNotice) return;
    const timer = setTimeout(() => setAuthNotice(""), 7000);
    return () => clearTimeout(timer);
  }, [authNotice]);

  useEffect(() => {
    const id = api.interceptors.response.use(
      (response) => response,
      async (error) => {
        const original = error.config;
        if (error.response?.status !== 401 || original?._retry || !session?.refresh_token) {
          return Promise.reject(error);
        }

        original._retry = true;
        try {
          const refreshed = await refreshStoredSession(session, rememberSession);
          original.headers.Authorization = `Bearer ${refreshed.access_token}`;
          return api(original);
        } catch {
          expireSession();
          return Promise.reject(error);
        }
      },
    );

    return () => api.interceptors.response.eject(id);
  }, [expireSession, refreshStoredSession, rememberSession, session]);

  const login = useCallback(async (payload) => {
    const result = await loginUser(payload);
    persistSession(result, payload.remember_me);
    setAuthNotice("");
    return result;
  }, [persistSession]);

  const register = useCallback(async (payload) => {
    const result = await registerUser(payload);
    persistSession(result, true);
    setAuthNotice("");
    return result;
  }, [persistSession]);

  const acceptSession = useCallback((nextSession, remember = true) => {
    persistSession(nextSession, remember);
    setAuthNotice("");
  }, [persistSession]);

  const logout = useCallback(async () => {
    try {
      if (session?.access_token) await logoutUser();
    } finally {
      persistSession(null, false);
      setAuthNotice("");
    }
  }, [persistSession, session?.access_token]);

  const value = useMemo(
    () => ({
      session,
      user: session?.user || null,
      isAuthenticated: Boolean(session?.access_token),
      loading,
      authNotice,
      login,
      register,
      logout,
      setSession: acceptSession,
      clearAuthNotice: () => setAuthNotice(""),
    }),
    [acceptSession, authNotice, loading, login, logout, register, session],
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
