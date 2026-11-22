import { useEffect, useState } from "react";
import { api, Paginated, Transaction, Wallet } from "../api/client";
import { useAuth } from "../auth";
import TransactionRow from "../components/TransactionRow";

export default function Dashboard() {
  const { token } = useAuth();
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [txns, setTxns] = useState<Transaction[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const w = await api<Wallet>("/wallets/me", { token });
        setWallet(w);
        const t = await api<Paginated<Transaction>>("/transactions?limit=5", { token });
        setTxns(t.items);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
      }
    })();
  }, [token]);

  return (
    <div>
      {error && <div className="error">{error}</div>}
      <div className="card">
        <div className="muted">Balance</div>
        <div className="balance">
          {wallet ? `${wallet.balance} ${wallet.currency}` : "—"}
        </div>
        <div className="muted">Wallet status: {wallet?.status ?? "—"}</div>
      </div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Recent activity</h3>
        {txns.length === 0 ? (
          <p className="muted">No transactions yet.</p>
        ) : (
          txns.map((t) => <TransactionRow key={t.id} txn={t} />)
        )}
      </div>
    </div>
  );
}
