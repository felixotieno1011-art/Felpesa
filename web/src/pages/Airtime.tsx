import { useState } from "react";
import { api, ApiError, Transaction } from "../api/client";
import { useAuth } from "../auth";
import PinSheet from "../components/PinSheet";
import { usePinStatus } from "../hooks/usePinStatus";

function normalizePhone(raw: string): string {
  const p = raw.replace(/[\s-]/g, "");
  if (p.startsWith("+")) return p;
  if (p.startsWith("0")) return "+254" + p.slice(1);
  if (p.startsWith("254")) return "+" + p;
  return p;
}

export default function Airtime() {
  const { token } = useAuth();
  const hasPin = usePinStatus(token);
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pinOpen, setPinOpen] = useState(false);
  const [pinError, setPinError] = useState("");
  const [done, setDone] = useState<Transaction | null>(null);

  const amt = Number(amount);
  const to = normalizePhone(phone);
  const valid = /^\+[1-9]\d{9,14}$/.test(to) && amt >= 5 && amt <= 5000;

  async function buy(pin?: string) {
    setBusy(true);
    setError("");
    setPinError("");
    try {
      const idem = crypto.randomUUID();
      const tx = await api<Transaction>("/airtime", {
        method: "POST",
        token,
        headers: pin ? { "Idempotency-Key": idem, "X-Pin": pin } : { "Idempotency-Key": idem },
        body: JSON.stringify({ phone: to, amount: amt.toFixed(4), currency: "KES" }),
      });
      setDone(tx);
      setPinOpen(false);
      setAmount("");
      setPhone("");
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
      <h3>Buy airtime</h3>

      <label>Phone number</label>
      <input
        inputMode="tel"
        value={phone}
        onChange={(e) => setPhone(e.target.value)}
        placeholder="0712 345 678"
      />

      <label>Amount (KES 5 – 5,000)</label>
      <input
        inputMode="decimal"
        value={amount}
        onChange={(e) => setAmount(e.target.value.replace(/[^\d.]/g, ""))}
        placeholder="0.00"
      />
      <div className="chips">
        {[20, 50, 100, 250, 500].map((n) => (
          <button key={n} className="chip" onClick={() => setAmount(String(n))}>
            {n}
          </button>
        ))}
      </div>

      {pinOpen && (
        <PinSheet
          busy={busy}
          error={pinError}
          onSubmit={(p) => buy(p)}
          onCancel={() => setPinOpen(false)}
        />
      )}

      {error && <div className="error">{error}</div>}
      {done && (
        <div className="success">
          <b>Airtime sent</b>
          <p className="mt-2" style={{ fontWeight: 400 }}>{done.message ?? "Confirmed."}</p>
        </div>
      )}

      <button
        className="primary"
        style={{ width: "100%" }}
        disabled={busy || !valid}
        onClick={() => {
          setDone(null);
          if (hasPin) setPinOpen(true);
          else void buy();
        }}
      >
        {busy ? "Working..." : "Buy airtime"}
      </button>
    </div>
  );
}
