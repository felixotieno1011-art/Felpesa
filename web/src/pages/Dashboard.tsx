import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Paginated, Transaction, Wallet } from "../api/client";
import { useAuth } from "../auth";
import TransactionRow from "../components/TransactionRow";
import { Eye, EyeOff, Plus, Receipt, Send, ShieldCheck, Smartphone } from "../components/icons";
import { usePinStatus } from "../hooks/usePinStatus";

const KEY = "felpesa-hide-balance";

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

export default function Dashboard() {
  const { token } = useAuth();
  const hasPin = usePinStatus(token);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [txns, setTxns] = useState<Transaction[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [hidden, setHidden] = useState(() => {
    try { return localStorage.getItem(KEY) === "1"; } catch { return false; }
  });

  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        setWallet(await api<Wallet>("/wallets/me", { token }));
        const t = await api<Paginated<Transaction>>("/transactions?limit=5", { token });
        setTxns(t.items);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  useEffect(() => {
    const h = () => {
      if (!token) return;
      api<Wallet>("/wallets/me", { token }).then(setWallet).catch(() => {});
      api<Paginated<Transaction>>("/transactions?limit=5", { token })
        .then((t) => setTxns(t.items)).catch(() => {});
    };
    window.addEventListener("felpesa-live", h);
    return () => window.removeEventListener("felpesa-live", h);
  }, [token]);

  function toggle() {
    const next = !hidden;
    setHidden(next);
    try { localStorage.setItem(KEY, next ? "1" : "0"); } catch { /* ignore */ }
  }

  const bal = wallet
    ? Number(wallet.balance).toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : "—";

  return (
    <div>
      <h1 className="greet">{greeting()}</h1>
      <p className="muted" style={{ marginBottom: 16 }}>Here's your wallet today.</p>

      {error && <div className="error">{error}</div>}
      {hasPin === false && (
        <div className="notice">
          <ShieldCheck size={18} /> <span>Secure your wallet: <Link to="/pin">set a 4-digit PIN</Link></span>
        </div>
      )}

      <div className="bal-card">
        <div className="bal-top">
          <span>Available balance</span>
          <button className="bal-eye" onClick={toggle} aria-label={hidden ? "Show balance" : "Hide balance"}>
            {hidden ? <EyeOff size={20} /> : <Eye size={20} />}
          </button>
        </div>
        <div className="bal-amount">
          {hidden ? "••••••" : bal}
          <span className="bal-cur">{wallet?.currency ?? "KES"}</span>
        </div>
        <div className="bal-foot">Wallet {wallet?.status ?? "—"}</div>
      </div>

      <div className="qa-row">
        <Link to="/send" className="qa"><span className="qa-circle"><Send size={22} /></span>Send</Link>
        <Link to="/pay" className="qa"><span className="qa-circle"><Receipt size={22} /></span>Pay bill</Link>
        <Link to="/airtime" className="qa"><span className="qa-circle"><Smartphone size={22} /></span>Airtime</Link>
        <Link to="/money" className="qa"><span className="qa-circle"><Plus size={22} /></span>Top up</Link>
      </div>

      <div className="card">
        <div className="flex-between">
          <h3>Recent activity</h3>
          <Link to="/history">See all</Link>
        </div>
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
