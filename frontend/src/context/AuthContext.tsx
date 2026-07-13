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
  login: (username: string) => Promise<{ success: boolean; error?: string }>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const TOKEN_KEY = 'auth_token';
const USER_KEY = 'auth_user';

const BACKEND_URL = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount: check stored token
  useEffect(() => {
    const storedToken = localStorage.getItem(TOKEN_KEY);
    const storedUser = localStorage.getItem(USER_KEY);

    if (storedToken && storedUser) {
      // Verify token with backend
      fetch(`${BACKEND_URL}/api/auth/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: storedToken }),
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.valid && data.user) {
            setToken(storedToken);
            setUser(data.user);
            localStorage.setItem(USER_KEY, JSON.stringify(data.user));
          } else {
            localStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(USER_KEY);
          }
        })
        .catch(() => {
          // Network error — use stored user as fallback
          try {
            const parsed = JSON.parse(storedUser);
            setToken(storedToken);
            setUser(parsed);
          } catch {
            localStorage.removeItem(TOKEN_KEY);
            localStorage.removeItem(USER_KEY);
          }
        })
        .finally(() => setIsLoading(false));
    } else {
      setIsLoading(false);
    }
  }, []);

  const login = useCallback(async (username: string): Promise<{ success: boolean; error?: string }> => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username }),
      });
      const data = await res.json();
      if (data.token && data.user) {
        setToken(data.token);
        setUser(data.user);
        localStorage.setItem(TOKEN_KEY, data.token);
        localStorage.setItem(USER_KEY, JSON.stringify(data.user));
        return { success: true };
      }
      return { success: false, error: data.error || 'Login failed' };
    } catch (e) {
      return { success: false, error: String(e) };
    }
  }, []);

  const logout = useCallback(() => {
    if (token) {
      fetch(`${BACKEND_URL}/api/auth/logout`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      }).catch(() => {});
    }
    setToken(null);
    setUser(null);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }, [token]);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!user && !!token,
        isLoading,
        login,
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
