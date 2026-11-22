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
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="container" style={{ maxWidth: 400, marginTop: 80 }}>
      <div className="card">
        <h1>Felpesa</h1>
        <p className="muted">
          {mode === "login" ? "Sign in to your wallet" : "Create a wallet"}
        </p>
        <form onSubmit={submit}>
          <label>Phone</label>
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+254712345678"
            required
          />
          {mode === "register" && (
            <>
              <label>Full name</label>
              <input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                minLength={2}
                required
              />
            </>
          )}
          <label>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
          {error && <div className="error">{error}</div>}
          <button type="submit" className="primary" style={{ width: "100%", marginTop: 8 }} disabled={busy}>
            {busy ? "..." : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>
        <p className="muted" style={{ marginTop: 16, textAlign: "center" }}>
          {mode === "login" ? (
            <button
              type="button"
              style={{ border: "none", background: "none", color: "#0070f3", padding: 0 }}
              onClick={() => setMode("register")}
            >
              Create an account
            </button>
          ) : (
            <button
              type="button"
              style={{ border: "none", background: "none", color: "#0070f3", padding: 0 }}
              onClick={() => setMode("login")}
            >
              Back to sign in
            </button>
          )}
        </p>
      </div>
    </div>
  );
}
