import { useEffect, useState } from "react";
import { api, Paginated, Transaction } from "../api/client";
import { useAuth } from "../auth";
import TransactionRow from "../components/TransactionRow";

export default function History() {
  const { token } = useAuth();
  const [items, setItems] = useState<Transaction[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [limit] = useState(20);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    setError("");
    api<Paginated<Transaction>>(`/transactions?limit=${limit}&offset=${offset}`, { token })
      .then((r) => {
        setItems(r.items);
        setTotal(r.meta.total);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [token, offset, limit]);

  return (
    <div className="card">
      <h3 style={{ marginTop: 0 }}>Transaction history</h3>
      {error && <div className="error">{error}</div>}
      {loading ? (
        <p className="muted">Loading...</p>
      ) : items.length === 0 ? (
        <p className="muted">No transactions.</p>
      ) : (
        items.map((t) => <TransactionRow key={t.id} txn={t} />)
      )}
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 16 }}>
        <button onClick={() => setOffset(Math.max(0, offset - limit))} disabled={offset === 0}>
          ← Newer
        </button>
        <span className="muted">
          {offset + 1}–{Math.min(offset + limit, total)} of {total}
        </span>
        <button onClick={() => setOffset(offset + limit)} disabled={offset + limit >= total}>
          Older →
        </button>
      </div>
    </div>
  );
}
