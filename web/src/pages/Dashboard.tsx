import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Paginated, Transaction, Wallet } from "../api/client";
import { useAuth } from "../auth";
import TransactionRow from "../components/TransactionRow";
import { usePinStatus } from "../hooks/usePinStatus";

export default function Dashboard() {
  const { token } = useAuth();
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [txns, setTxns] = useState<Transaction[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const hasPin = usePinStatus(token);

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
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  const bal = wallet
    ? Number(wallet.balance).toLocaleString("en-KE", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      })
    : "—";

  return (
    <div>
      {error && <div className="error">{error}</div>}
      {hasPin === false && (
        <div className="error" style={{ background: "var(--warning-soft)", color: "var(--warning)" }}>
          Secure your wallet: <Link to="/pin">set a 4-digit PIN</Link>
        </div>
      )}

      <div className="card hero">
        <div className="muted">Available balance</div>
        <div className="balance">
          {bal}
          <span className="currency">{wallet?.currency ?? "KES"}</span>
        </div>
        <div className="muted">Wallet {wallet?.status ?? "—"}</div>
      </div>

      <div className="actions">
        <Link to="/send" className="action">
          <span className="ico">💸</span>Send
        </Link>
        <Link to="/pay" className="action">
          <span className="ico">🧾</span>Pay
        </Link>
        <Link to="/money" className="action">
          <span className="ico">💰</span>Money
        </Link>
        <Link to="/history" className="action">
          <span className="ico">🕘</span>History
        </Link>
      </div>

      <div className="card">
        <h3>Recent activity</h3>
        {loading ? (
          <p className="muted">Loading...</p>
        ) : txns.length === 0 ? (
          <p className="muted">No transactions yet.</p>
        ) : (
          txns.map((t) => <TransactionRow key={t.id} txn={t} walletId={wallet?.id} />)
        )}
      </div>
    </div>
  );
}
