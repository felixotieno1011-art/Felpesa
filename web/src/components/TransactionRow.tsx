import { Transaction } from "../api/client";

const LABEL: Record<string, string> = {
  transfer: "Transfer",
  deposit: "Deposit",
  withdrawal: "Withdrawal",
  paybill: "Pay Bill",
  buygoods: "Buy Goods",
};
const ICON: Record<string, string> = {
  transfer: "💸",
  deposit: "⬇️",
  withdrawal: "⬆️",
  paybill: "🧾",
  buygoods: "🛍️",
};

const fmt = (s: string) =>
  Number(s).toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function TransactionRow({
  txn,
  walletId,
}: {
  txn: Transaction;
  walletId?: string;
}) {
  const incoming = walletId
    ? txn.to_wallet_id === walletId
    : txn.type === "deposit";

  return (
    <div className="row">
      <div className="flex" style={{ alignItems: "center", gap: 0 }}>
        <div className="tx-ico">{ICON[txn.type] ?? "💱"}</div>
        <div>
          <div className="row-main">
            {LABEL[txn.type] ?? txn.type}
            {incoming && txn.type === "transfer" ? " received" : ""}
          </div>
          <div className="row-sub">
            {new Date(txn.created_at).toLocaleString("en-KE", {
              day: "numeric",
              month: "short",
              hour: "2-digit",
              minute: "2-digit",
            })}
          </div>
          {txn.message && <div className="tx-msg">{txn.message}</div>}
        </div>
      </div>
      <div style={{ textAlign: "right" }}>
        <div className={`row-value ${incoming ? "tx-in" : "tx-out"}`}>
          {incoming ? "+" : "−"}
          {fmt(txn.amount)}
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
