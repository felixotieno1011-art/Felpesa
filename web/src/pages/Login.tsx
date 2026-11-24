import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, TokenResponse } from "../api/client";
import { useAuth } from "../auth";

export default function Login() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [phone, setPhone] = useState("+254712345678");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const { setToken } = useAuth();
  const nav = useNavigate();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "register") {
        await api("/auth/register", {
          method: "POST",
          body: JSON.stringify({ phone, full_name: fullName, password }),
        });
      }
      const tok = await api<TokenResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ phone, password }),
      });
      setToken(tok.access_token);
      nav("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-brand">
          <div className="auth-logo">₣</div>
          <div className="auth-title">Felpesa</div>
          <div className="auth-tagline">Mobile money, secured</div>
        </div>

        <form onSubmit={submit}>
          <label htmlFor="phone">Phone</label>
          <input
            id="phone"
            type="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+254712345678"
            required
            autoComplete="tel"
          />

          {mode === "register" && (
            <>
              <label htmlFor="full_name">Full name</label>
              <input
                id="full_name"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Your name"
                minLength={2}
                required
                autoComplete="name"
              />
            </>
          )}

          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="At least 8 characters"
            minLength={8}
            required
            autoComplete={mode === "login" ? "current-password" : "new-password"}
          />

          {error && <div className="error">{error}</div>}

          <button
            type="submit"
            className="primary"
            style={{ width: "100%", marginTop: 8 }}
            disabled={busy}
          >
            {busy
              ? mode === "login"
                ? "Signing in…"
                : "Creating account…"
              : mode === "login"
              ? "Sign in"
              : "Create account"}
          </button>
        </form>

        <div className="auth-toggle">
          {mode === "login" ? (
            <>
              New to Felpesa?{" "}
              <button
                type="button"
                className="link"
                onClick={() => {
                  setMode("register");
                  setError("");
                }}
              >
                Create an account
              </button>
            </>
          ) : (
            <>
              Already have an account?{" "}
              <button
                type="button"
                className="link"
                onClick={() => {
                  setMode("login");
                  setError("");
                }}
              >
                Sign in
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
