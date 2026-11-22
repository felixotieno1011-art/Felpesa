import { Transaction } from "../api/client";

export default function TransactionRow({ txn }: { txn: Transaction }) {
  return (
    <div className="row">
      <div>
        <div style={{ fontWeight: 500 }}>{txn.type}</div>
        <div className="muted">
          {new Date(txn.created_at).toLocaleString()}
          {txn.description ? ` · ${txn.description}` : ""}
        </div>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ fontWeight: 600 }}>
          {txn.amount} {txn.currency}
        </div>
        <div style={{ fontSize: 12, marginTop: 4 }}>
          <span className={`badge ${txn.status}`}>{txn.status}</span>
          {txn.flagged_fraud && (
            <span className="badge flag" style={{ marginLeft: 6 }}>
              flagged
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
