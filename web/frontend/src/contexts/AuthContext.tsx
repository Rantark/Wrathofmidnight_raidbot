import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { jwtDecode } from 'jwt-decode';
import type { User } from '@/types';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isRaidLeader: boolean;
  isOfficer: boolean;
  login: (token: string, userData?: Partial<User>) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('jwt_token');
    if (token) {
      try {
        const decoded = jwtDecode<User>(token);
        const extra = JSON.parse(localStorage.getItem('user_extra') ?? '{}');
        setUser({ ...decoded, ...extra });
      } catch {
        localStorage.removeItem('jwt_token');
      }
    }
  }, []);

  const login = useCallback((token: string, userData?: Partial<User>) => {
    localStorage.setItem('jwt_token', token);
    if (userData) localStorage.setItem('user_extra', JSON.stringify(userData));
    try {
      const decoded = jwtDecode<User>(token);
      setUser({ ...decoded, ...(userData ?? {}) });
    } catch {
      // ignore
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('jwt_token');
    localStorage.removeItem('user_extra');
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isRaidLeader: user?.role === 'raid_leader' || user?.role === 'officer',
        isOfficer: user?.role === 'officer',
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
