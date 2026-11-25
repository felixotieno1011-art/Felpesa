import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, Transaction } from "../api/client";
import { useAuth } from "../auth";
import PinSheet from "../components/PinSheet";
import { usePinStatus } from "../hooks/usePinStatus";

type Mode = "deposit" | "withdraw";

export default function Money() {
  const { token } = useAuth();
  const [mode, setMode] = useState<Mode>("deposit");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState<Transaction | null>(null);
  const hasPin = usePinStatus(token);
  const [pinOpen, setPinOpen] = useState(false);
  const [pinError, setPinError] = useState("");

  const amt = Number(amount);

  async function submit(pin?: string) {
    setBusy(true);
    setError("");
    setPinError("");
    setDone(null);
    try {
      const tx = await api<Transaction>(mode === "deposit" ? "/deposits" : "/withdrawals", {
        method: "POST",
        token,
        headers: pin
          ? { "Idempotency-Key": crypto.randomUUID(), "X-Pin": pin }
          : { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ amount: amt, currency: "KES" }),
      });
      setDone(tx);
      setPinOpen(false);
      setAmount("");
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Something went wrong";
      if (pin && e instanceof ApiError && (e.status === 403 || e.status === 429)) {
        setPinError(msg);
      } else {
        setError(msg);
        setPinOpen(false);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h3>Deposit / Withdraw</h3>
      <p className="muted">Sandbox: no real money moves.</p>
      <p><Link to="/mpesa">Top up via M-Pesa (Daraja sandbox) →</Link></p>

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

      {pinOpen && (
        <PinSheet
          busy={busy}
          error={pinError}
          onSubmit={(p) => submit(p)}
          onCancel={() => setPinOpen(false)}
        />
      )}

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
        onClick={() => (mode === "withdraw" && hasPin ? setPinOpen(true) : submit())}
      >
        {busy ? "Working..." : mode === "deposit" ? "Deposit" : "Withdraw"}
      </button>
    </div>
  );
}
