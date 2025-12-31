import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import api from '../lib/api';

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('auth_token') || '');
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('auth_user') || 'null');
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(!!token);

  useEffect(() => {
    let cancelled = false;
    async function boot() {
      if (!token) return;
      try {
        const { user } = await api.auth.me(token);
        if (!cancelled) setUser(user);
      } catch {
        if (!cancelled) {
          setToken('');
          setUser(null);
          localStorage.removeItem('auth_token');
          localStorage.removeItem('auth_user');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    boot();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const value = useMemo(
    () => ({
      token,
      user,
      loading,
      isLoggedIn: !!token && !!user, // ✅ bandera global usada por ProductCard
      login({ token, user }) {
        setToken(token);
        setUser(user);
        localStorage.setItem('auth_token', token);
        localStorage.setItem('auth_user', JSON.stringify(user));
      },
      logout() {
        setToken('');
        setUser(null);
        localStorage.removeItem('auth_token');
        localStorage.removeItem('auth_user');
      },
    }),
    [token, user, loading]
  );

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error('useAuth debe usarse dentro de <AuthProvider>');
  return ctx;
}
