import { createContext, useContext, useEffect, useState, ReactNode } from "react";

type AuthState = {
  token: string | null;
  setToken: (t: string | null) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

const KEY = "felpesa_token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => localStorage.getItem(KEY));

  const setToken = (t: string | null) => {
    setTokenState(t);
    if (t) localStorage.setItem(KEY, t);
    else localStorage.removeItem(KEY);
  };

  const logout = () => setToken(null);

  useEffect(() => {
    // Storage events keep tabs in sync if the user logs out elsewhere.
    const onStorage = (e: StorageEvent) => {
      if (e.key === KEY) setTokenState(e.newValue);
    };
    const onExpired = () => setToken(null);
    window.addEventListener("storage", onStorage);
    window.addEventListener("felpesa-unauthorized", onExpired);
    return () => {
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("felpesa-unauthorized", onExpired);
    };
  }, []);

  return (
    <AuthContext.Provider value={{ token, setToken, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}
