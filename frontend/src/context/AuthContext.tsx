import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';

export interface AuthUser {
  user_id: string;
  username: string;
  email: string;
  provider: string;
  avatar_url: string;
}

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<{ success: boolean; error?: string }>;
  loginWithToken: (externalToken: string) => Promise<{ success: boolean; error?: string }>;
  getLoginUrl: () => Promise<string>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const TOKEN_KEY = 'auth_token';
const USER_KEY = 'auth_user';

// Backend API runs on port 8000 — in dev mode frontend is on 5173,
// so window.location.origin would point to the wrong port.
// In production both are served from the same origin.
const BACKEND_URL = typeof window !== 'undefined' && window.location.port === '5173'
  ? 'http://localhost:8000'
  : (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000');

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const setSession = useCallback((newToken: string, newUser: AuthUser) => {
    setToken(newToken);
    setUser(newUser);
    localStorage.setItem(TOKEN_KEY, newToken);
    localStorage.setItem(USER_KEY, JSON.stringify(newUser));
  }, []);

  const clearSession = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }, []);

  const loginWithToken = useCallback(async (externalToken: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: externalToken }),
      });
      const data = await res.json();
      if (data.token && data.user) {
        setSession(data.token, data.user);
        return { success: true };
      }
      return { success: false, error: data.error || 'Token login failed' };
    } catch (e) {
      return { success: false, error: String(e) };
    }
  }, [setSession]);

  const getLoginUrl = useCallback(async (): Promise<string> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/login-url`);
      const data = await res.json();
      return data.login_url || '';
    } catch {
      return '';
    }
  }, []);

  // On mount: handle OAuth redirect token, then verify stored token
  useEffect(() => {
    let handled = false;

    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const oauthToken = params.get('token');
      if (oauthToken) {
        handled = true;
        // Remove token from URL to avoid replay on refresh
        const cleanUrl = window.location.pathname + window.location.hash;
        window.history.replaceState({}, document.title, cleanUrl);
        loginWithToken(oauthToken).finally(() => setIsLoading(false));
      }
    }

    if (!handled) {
      const storedToken = localStorage.getItem(TOKEN_KEY);
      const storedUser = localStorage.getItem(USER_KEY);

      if (storedToken && storedUser) {
        fetch(`${BACKEND_URL}/api/auth/verify`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token: storedToken }),
        })
          .then((res) => res.json())
          .then((data) => {
            if (data.valid && data.user) {
              setSession(storedToken, data.user);
            } else {
              clearSession();
            }
          })
          .catch(() => {
            // Network error — use stored user as fallback
            try {
              const parsed = JSON.parse(storedUser);
              setSession(storedToken, parsed);
            } catch {
              clearSession();
            }
          })
          .finally(() => setIsLoading(false));
      } else {
        setIsLoading(false);
      }
    }
  }, [loginWithToken, setSession, clearSession]);

  const login = useCallback(async (username: string, password: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (data.token && data.user) {
        setSession(data.token, data.user);
        return { success: true };
      }
      return { success: false, error: data.error || 'Login failed' };
    } catch (e) {
      return { success: false, error: String(e) };
    }
  }, [setSession]);

  const logout = useCallback(() => {
    if (token) {
      fetch(`${BACKEND_URL}/api/auth/logout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      }).catch(() => {});
    }
    clearSession();
  }, [token, clearSession]);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user && !!token,
        isLoading,
        login,
        loginWithToken,
        getLoginUrl,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
