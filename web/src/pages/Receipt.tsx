import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, Transaction } from "../api/client";
import { useAuth } from "../auth";

const LABEL: Record<string, string> = {
  transfer: "Transfer", deposit: "Deposit", withdrawal: "Withdrawal",
  paybill: "Pay Bill", buygoods: "Buy Goods", airtime: "Airtime",
};

export default function Receipt() {
  const { id } = useParams();
  const { token } = useAuth();
  const [tx, setTx] = useState<Transaction | null>(null);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!token || !id) return;
    api<Transaction>(`/transactions/${id}`, { token })
      .then(setTx)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, [token, id]);

  if (error) return <div className="card"><div className="error">{error}</div></div>;
  if (!tx) return <div className="card"><p className="muted">Loading...</p></div>;

  const ref = tx.id.replace(/-/g, "").slice(0, 10).toUpperCase();
  const text = tx.message ?? `${LABEL[tx.type] ?? tx.type} KES ${tx.amount} (${ref})`;

  async function share() {
    try {
      if (navigator.share) await navigator.share({ title: "Felpesa receipt", text });
      else {
        await navigator.clipboard.writeText(text);
        setCopied(true);
      }
    } catch { /* user cancelled */ }
  }

  return (
    <div className="card">
      <h3>Receipt</h3>
      <div className="success" style={{ padding: 18 }}>
        <div className="balance">
          {Number(tx.amount).toLocaleString("en-KE", { minimumFractionDigits: 2 })}
          <span className="currency">{tx.currency}</span>
        </div>
        <div>{LABEL[tx.type] ?? tx.type} · {tx.status}</div>
      </div>
      <div className="row"><span className="muted">Reference</span><span className="mono">{ref}</span></div>
      <div className="row"><span className="muted">Date</span>
        <span>{new Date(tx.created_at).toLocaleString("en-KE")}</span></div>
      {tx.description && (
        <div className="row"><span className="muted">Details</span><span>{tx.description}</span></div>
      )}
      {tx.message && <p className="muted mt-4">{tx.message}</p>}
      <button className="primary mt-4" style={{ width: "100%" }} onClick={share}>
        {copied ? "Copied" : "Share / copy"}
      </button>
      <Link to="/history"><button className="mt-2" style={{ width: "100%" }}>Back to activity</button></Link>
    </div>
  );
}
