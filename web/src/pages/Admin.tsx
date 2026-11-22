import { useState } from "react";
import { api, Paginated } from "../api/client";
import { useAuth } from "../auth";

type Reconciliation = {
  ok: boolean;
  checked_transactions: number;
  checked_wallets: number;
  unbalanced_transactions: unknown[];
  wallet_mismatches: unknown[];
  checked_at: string;
};

type AuditEntry = {
  id: number;
  actor_id: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  created_at: string;
};

export default function Admin() {
  const { token } = useAuth();
  const [rec, setRec] = useState<Reconciliation | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const runReconciliation = async () => {
    setError("");
    setBusy(true);
    try {
      const r = await api<Reconciliation>("/reconciliation", { token });
      setRec(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  const loadAudit = async () => {
    setError("");
    setBusy(true);
    try {
      const r = await api<Paginated<AuditEntry>>("/audit?limit=20", { token });
      setAudit(r.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="card">
        <h3 style={{ marginTop: 0 }}>Reconciliation</h3>
        <p className="muted">Prove every transaction balances and every wallet matches its ledger.</p>
        <button className="primary" onClick={runReconciliation} disabled={busy}>
          {busy ? "Running..." : "Run reconciliation"}
        </button>
        {rec && (
          <div style={{ marginTop: 16 }}>
            <div style={{ fontSize: 24, fontWeight: 700, color: rec.ok ? "#137333" : "#c5221f" }}>
              {rec.ok ? "✓ Ledger balances" : "✗ Anomalies found"}
            </div>
            <div className="muted" style={{ marginTop: 8 }}>
              Checked {rec.checked_transactions} transactions, {rec.checked_wallets} wallets.
              <br />
              {rec.unbalanced_transactions.length} unbalanced transactions,
              {" "}{rec.wallet_mismatches.length} wallet mismatches.
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Audit log</h3>
        <button onClick={loadAudit} disabled={busy}>Load recent</button>
        {audit.length > 0 && (
          <div style={{ marginTop: 16 }}>
            {audit.map((a) => (
              <div key={a.id} className="row">
                <div>
                  <div style={{ fontWeight: 500 }}>{a.action}</div>
                  <div className="muted">
                    {a.entity_type ?? "—"} {a.entity_id?.slice(0, 8) ?? ""}
                  </div>
                </div>
                <div className="muted">{new Date(a.created_at).toLocaleString()}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {error && <div className="error">{error}</div>}
    </div>
  );
}
