import { useEffect, useState } from "react";
import { api, ApiError } from "../api/client";
import { useAuth } from "../auth";

type MStatus = {
  status: "pending" | "completed" | "cancelled" | "failed" | "needs_review";
  result_desc: string | null;
  mpesa_receipt: string | null;
  amount: string;
};

function normalizePhone(raw: string): string {
  const p = raw.replace(/[\s-]/g, "");
  if (p.startsWith("+")) return p;
  if (p.startsWith("0")) return "+254" + p.slice(1);
  if (p.startsWith("254")) return "+" + p;
  return p;
}

export default function Mpesa() {
  const { token } = useAuth();
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [checkout, setCheckout] = useState<string | null>(null);
  const [st, setSt] = useState<MStatus | null>(null);
  const [timedOut, setTimedOut] = useState(false);

  const to = normalizePhone(phone);
  const amt = Number(amount);
  const valid = /^\+254[17]\d{8}$/.test(to) && Number.isInteger(amt) && amt >= 1;

  useEffect(() => {
    if (!checkout || !token) return;
    let tries = 0;
    const t = setInterval(async () => {
      tries++;
      try {
        const s = await api<MStatus>(`/mpesa/status/${checkout}`, { token });
        setSt(s);
        if (s.status !== "pending") clearInterval(t);
      } catch {
        /* keep polling */
      }
      if (tries >= 30) {
        clearInterval(t);
        setTimedOut(true);
      }
    }, 3000);
    return () => clearInterval(t);
  }, [checkout, token]);

  async function start() {
    setBusy(true);
    setError("");
    setSt(null);
    setTimedOut(false);
    try {
      const r = await api<{ checkout_request_id: string }>("/mpesa/stk", {
        method: "POST",
        token,
        body: JSON.stringify({ phone: to, amount: amt }),
      });
      setCheckout(r.checkout_request_id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setCheckout(null);
    setSt(null);
    setTimedOut(false);
    setAmount("");
  }

  const pending = checkout && (!st || st.status === "pending");

  return (
    <div className="card">
      <h3>Top up with M-Pesa</h3>
      <p className="muted">Test only. Use the Daraja test number, never your own phone.</p>

      {!checkout && (
        <>
          <label>M-Pesa phone number</label>
          <input inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="0712 345 678" />
          <label>Amount (whole KES)</label>
          <input inputMode="numeric" value={amount}
            onChange={(e) => setAmount(e.target.value.replace(/\D/g, ""))} placeholder="100" />
          <div className="chips">
            {[10, 50, 100, 500, 1000].map((n) => (
              <button key={n} className="chip" onClick={() => setAmount(String(n))}>{n}</button>
            ))}
          </div>
          {error && <div className="error">{error}</div>}
          <button className="primary" style={{ width: "100%" }} disabled={busy || !valid} onClick={start}>
            {busy ? "Sending..." : "Send M-Pesa prompt"}
          </button>
        </>
      )}

      {pending && (
        <div className="success">
          <b>Waiting for M-Pesa confirmation...</b>
          <p className="mt-2" style={{ fontWeight: 400 }}>
            {timedOut ? "Still no response. Check History later; your balance updates when it arrives." : "This can take up to a minute."}
          </p>
        </div>
      )}
      {st?.status === "completed" && (
        <div className="success">
          <b>Top-up complete</b>
          <p className="mt-2" style={{ fontWeight: 400 }}>
            KES {Number(st.amount).toLocaleString("en-KE", { minimumFractionDigits: 2 })} · Receipt {st.mpesa_receipt}
          </p>
        </div>
      )}
      {st && ["cancelled", "failed", "needs_review"].includes(st.status) && (
        <div className="error">
          {st.status === "cancelled" ? "Cancelled on the phone." : st.status === "needs_review" ? "Payment needs review." : "Payment failed."}{" "}
          {st.result_desc}
        </div>
      )}
      {checkout && !pending && (
        <button className="primary mt-4" style={{ width: "100%" }} onClick={reset}>Done</button>
      )}
    </div>
  );
}
