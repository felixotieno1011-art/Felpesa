import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { refreshAccessToken, setMemoryToken } from "./api/client";

type AuthState = {
  token: string | null;
  ready: boolean;
  setToken: (t: string | null) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  const setToken = (t: string | null) => {
    setMemoryToken(t);
    setTokenState(t);
  };

  const logout = () => {
    fetch("/api/auth/logout", { method: "POST", credentials: "include" }).catch(() => {});
    setToken(null);
  };

  // On page load: try to restore the session from the refresh cookie.
  useEffect(() => {
    let live = true;
    try { localStorage.removeItem("felpesa_token"); } catch { /* old token, no longer used */ }
    refreshAccessToken().then((t) => {
      if (!live) return;
      setTokenState(t);
      setReady(true);
    });
    return () => { live = false; };
  }, []);

  useEffect(() => {
    const onExpired = () => setTokenState(null);
    const onRefreshed = (e: Event) => setTokenState((e as CustomEvent<string>).detail);
    window.addEventListener("felpesa-unauthorized", onExpired);
    window.addEventListener("felpesa-token", onRefreshed);
    return () => {
      window.removeEventListener("felpesa-unauthorized", onExpired);
      window.removeEventListener("felpesa-token", onRefreshed);
    };
  }, []);

  return (
    <AuthContext.Provider value={{ token, ready, setToken, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}
