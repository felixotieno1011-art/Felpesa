import { useState } from "react";
import { api, ApiError, Transaction } from "../api/client";
import { useAuth } from "../auth";

type Mode = "deposit" | "withdraw";

export default function Money() {
  const { token } = useAuth();
  const [mode, setMode] = useState<Mode>("deposit");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState<Transaction | null>(null);

  const amt = Number(amount);

  async function submit() {
    setBusy(true);
    setError("");
    setDone(null);
    try {
      const tx = await api<Transaction>(mode === "deposit" ? "/deposits" : "/withdrawals", {
        method: "POST",
        token,
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ amount: amt, currency: "KES" }),
      });
      setDone(tx);
      setAmount("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h3>Deposit / Withdraw</h3>
      <p className="muted">Sandbox: no real money moves.</p>

      <div className="flex mb-4">
        {(["deposit", "withdraw"] as Mode[]).map((m) => (
          <button
            key={m}
            className={mode === m ? "primary" : ""}
            style={{ flex: 1 }}
            onClick={() => {
              setMode(m);
              setError("");
              setDone(null);
            }}
          >
            {m === "deposit" ? "Deposit" : "Withdraw"}
          </button>
        ))}
      </div>

      <label>Amount (KES)</label>
      <input
        inputMode="decimal"
        value={amount}
        onChange={(e) => setAmount(e.target.value.replace(/[^\d.]/g, ""))}
        placeholder="0.00"
      />
      <div className="chips">
        {[100, 500, 1000, 5000].map((n) => (
          <button key={n} className="chip" onClick={() => setAmount(String(n))}>
            {n.toLocaleString()}
          </button>
        ))}
      </div>

      {error && <div className="error">{error}</div>}
      {done && (
        <div className="success">
          {mode === "deposit" ? "Deposited" : "Withdrew"} KES{" "}
          {Number(done.amount).toLocaleString("en-KE", { minimumFractionDigits: 2 })}
        </div>
      )}

      <button
        className="primary"
        style={{ width: "100%" }}
        disabled={busy || !(amt > 0)}
        onClick={submit}
      >
        {busy ? "Working..." : mode === "deposit" ? "Deposit" : "Withdraw"}
      </button>
    </div>
  );
}
