import { useState } from "react";
import { api, ApiError, Transaction } from "../api/client";
import { useAuth } from "../auth";
import PinSheet from "../components/PinSheet";
import { usePinStatus } from "../hooks/usePinStatus";

type Recipient = { name_masked: string; wallet_id: string };

// 0712345678 -> +254712345678, 254712345678 -> +254712345678
function normalizePhone(raw: string): string {
  const p = raw.replace(/[\s-]/g, "");
  if (p.startsWith("+")) return p;
  if (p.startsWith("0")) return "+254" + p.slice(1);
  if (p.startsWith("254")) return "+" + p;
  return p;
}

export default function SendMoney() {
  const { token } = useAuth();
  const [phone, setPhone] = useState("");
  const [recipient, setRecipient] = useState<Recipient | null>(null);
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [result, setResult] = useState<Transaction | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [finding, setFinding] = useState(false);
  const hasPin = usePinStatus(token);
  const [pinOpen, setPinOpen] = useState(false);
  const [pinError, setPinError] = useState("");

  const find = async () => {
    setError("");
    setRecipient(null);
    setFinding(true);
    try {
      const r = await api<Recipient>(
        `/wallets/lookup?phone=${encodeURIComponent(normalizePhone(phone))}`,
        { token }
      );
      setRecipient(r);
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 404
          ? "No Felpesa account found for that number"
          : e instanceof Error
          ? e.message
          : "Lookup failed"
      );
    } finally {
      setFinding(false);
    }
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!recipient) return;
    if (hasPin) setPinOpen(true);
    else void send();
  };

  const send = async (pin?: string) => {
    if (!recipient) return;
    setError("");
    setPinError("");
    setResult(null);
    setBusy(true);
    try {
      const txn = await api<Transaction>("/transfers", {
        method: "POST",
        token,
        headers: pin
          ? { "Idempotency-Key": crypto.randomUUID(), "X-Pin": pin }
          : { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({
          to_wallet_id: recipient.wallet_id,
          amount: Number(amount).toFixed(4),
          currency: "KES",
          description: description || null,
        }),
      });
      setResult(txn);
      setAmount("");
      setDescription("");
      setRecipient(null);
      setPhone("");
      setPinOpen(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Transfer failed";
      if (pin && err instanceof ApiError && (err.status === 403 || err.status === 429)) {
        setPinError(msg);
      } else {
        setError(msg);
        setPinOpen(false);
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <h3>Send money</h3>

      <label>Recipient phone</label>
      <div className="flex" style={{ alignItems: "flex-start" }}>
        <input
          inputMode="tel"
          value={phone}
          onChange={(e) => {
            setPhone(e.target.value);
            setRecipient(null);
          }}
          placeholder="0712 345 678"
        />
        <button type="button" disabled={finding || phone.length < 7} onClick={find}>
          {finding ? "..." : "Find"}
        </button>
      </div>

      {recipient && (
        <form onSubmit={submit}>
          <div className="success">
            Send to <b>{recipient.name_masked}</b>
          </div>
          <label>Amount (KES)</label>
          <input
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value.replace(/[^\d.]/g, ""))}
            placeholder="0.00"
            required
          />
          <label>Note (optional)</label>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={500}
          />
          <button type="submit" className="primary" disabled={busy || !(Number(amount) > 0)}>
            {busy ? "Sending..." : "Send"}
          </button>
        </form>
      )}

      {pinOpen && (
        <PinSheet
          busy={busy}
          error={pinError}
          onSubmit={(p) => send(p)}
          onCancel={() => setPinOpen(false)}
        />
      )}

      {error && <div className="error">{error}</div>}

      {result && (
        <div className="success mt-4">
          <b>Transfer sent</b>
          <div className="muted mt-2">
            KES {result.amount} · {result.status}
            {result.flagged_fraud && (
              <>
                {" "}
                <span className="badge flag">Flagged: {result.fraud_reason}</span>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
