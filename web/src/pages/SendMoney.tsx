import { useState } from "react";
import { api, Transaction } from "../api/client";
import { useAuth } from "../auth";

export default function SendMoney() {
  const { token } = useAuth();
  const [toWallet, setToWallet] = useState("");
  const [amount, setAmount] = useState("10.0000");
  const [description, setDescription] = useState("");
  const [result, setResult] = useState<Transaction | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setResult(null);
    setBusy(true);
    try {
      // New Idempotency-Key per submission — double-submits are prevented by disabling the button
      const key = crypto.randomUUID();
      const txn = await api<Transaction>("/transfers", {
        method: "POST",
        token,
        headers: { "Idempotency-Key": key },
        body: JSON.stringify({
          to_wallet_id: toWallet,
          amount,
          currency: "KES",
          description: description || null,
        }),
      });
      setResult(txn);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Transfer failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>Send money</h3>
      <form onSubmit={submit}>
        <label>Recipient wallet ID</label>
        <input
          value={toWallet}
          onChange={(e) => setToWallet(e.target.value)}
          placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
          required
        />
        <label>Amount (KES)</label>
        <input
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          required
        />
        <label>Description (optional)</label>
        <input
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={500}
        />
        {error && <div className="error">{error}</div>}
        <button type="submit" className="primary" disabled={busy}>
          {busy ? "Sending..." : "Send"}
        </button>
      </form>

      {result && (
        <div style={{ marginTop: 24 }}>
          <div style={{ color: "#137333", fontWeight: 600 }}>Transfer sent</div>
          <div className="muted" style={{ marginTop: 8 }}>
            ID: {result.id}
            <br />
            Amount: {result.amount} {result.currency}
            <br />
            Status: {result.status}
            {result.flagged_fraud && (
              <>
                <br />
                <span className="badge flag">Flagged: {result.fraud_reason}</span>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
