import { useState } from "react";
import { api, ApiError, Transaction } from "../api/client";
import { useAuth } from "../auth";

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

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recipient) return;
    setError("");
    setResult(null);
    setBusy(true);
    try {
      const txn = await api<Transaction>("/transfers", {
        method: "POST",
        token,
        headers: { "Idempotency-Key": crypto.randomUUID() },
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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Transfer failed");
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
