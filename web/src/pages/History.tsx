import { useEffect, useState } from "react";
import { api, Paginated, Transaction, Wallet } from "../api/client";
import { useAuth } from "../auth";
import TransactionRow from "../components/TransactionRow";

const FILTERS = [
  { key: "", label: "All" },
  { key: "transfer", label: "Transfers" },
  { key: "paybill", label: "Pay Bill" },
  { key: "buygoods", label: "Buy Goods" },
  { key: "airtime", label: "Airtime" },
  { key: "deposit", label: "Deposits" },
  { key: "withdrawal", label: "Withdrawals" },
];

export default function History() {
  const { token } = useAuth();
  const [items, setItems] = useState<Transaction[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [limit] = useState(20);
  const [type, setType] = useState("");
  const [walletId, setWalletId] = useState<string | undefined>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!token) return;
    api<Wallet>("/wallets/me", { token })
      .then((w) => setWalletId(w.id))
      .catch(() => {});
  }, [token]);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    setError("");
    const q = `limit=${limit}&offset=${offset}${type ? `&type=${type}` : ""}`;
    api<Paginated<Transaction>>(`/transactions?${q}`, { token })
      .then((r) => {
        setItems(r.items);
        setTotal(r.meta.total);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [token, offset, limit, type]);

  return (
    <div className="card">
      <h3>Transaction history</h3>

      <div className="chips">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            className={`chip ${type === f.key ? "on" : ""}`}
            onClick={() => {
              setType(f.key);
              setOffset(0);
            }}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && <div className="error">{error}</div>}
      {loading ? (
        <p className="muted">Loading...</p>
      ) : items.length === 0 ? (
        <p className="muted">No transactions.</p>
      ) : (
        items.map((t) => <TransactionRow key={t.id} txn={t} walletId={walletId} />)
      )}

      <div className="flex-between mt-4">
        <button onClick={() => setOffset(Math.max(0, offset - limit))} disabled={offset === 0}>
          ← Newer
        </button>
        <span className="muted">
          {total === 0 ? 0 : offset + 1}–{Math.min(offset + limit, total)} of {total}
        </span>
        <button onClick={() => setOffset(offset + limit)} disabled={offset + limit >= total}>
          Older →
        </button>
      </div>
    </div>
  );
}
