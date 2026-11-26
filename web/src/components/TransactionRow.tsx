import { useNavigate } from "react-router-dom";
import { Transaction } from "../api/client";
import {
  ArrowDownLeft, ArrowUpFromLine, ArrowUpRight, Plus, Receipt, Send, ShoppingBag, Smartphone,
} from "./icons";

const LABEL: Record<string, string> = {
  transfer: "Transfer", deposit: "Deposit", withdrawal: "Withdrawal",
  paybill: "Pay Bill", buygoods: "Buy Goods", airtime: "Airtime",
  withdrawal_reversal: "Withdrawal reversed",
};
const ICON: Record<string, typeof Send> = {
  transfer: Send, deposit: Plus, withdrawal: ArrowUpFromLine, paybill: Receipt,
  buygoods: ShoppingBag, airtime: Smartphone,
};

const fmt = (s: string) =>
  Number(s).toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function TransactionRow({ txn, walletId }: { txn: Transaction; walletId?: string }) {
  const nav = useNavigate();
  const incoming = walletId ? txn.to_wallet_id === walletId : txn.type === "deposit";
  const Icon = ICON[txn.type] ?? (incoming ? ArrowDownLeft : ArrowUpRight);

  return (
    <div className="row tap" onClick={() => nav(`/receipt/${txn.id}`)}>
      <div className="flex" style={{ alignItems: "center", gap: 0, minWidth: 0 }}>
        <div className="tx-ico"><Icon size={18} /></div>
        <div style={{ minWidth: 0 }}>
          <div className="row-main">
            {LABEL[txn.type] ?? txn.type}
            {incoming && txn.type === "transfer" ? " received" : ""}
          </div>
          <div className="row-sub">
            {new Date(txn.created_at).toLocaleString("en-KE", {
              day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
            })}
          </div>
          {txn.message && <div className="tx-msg">{txn.message}</div>}
        </div>
      </div>
      <div style={{ textAlign: "right" }}>
        <div className={`row-value ${incoming ? "tx-in" : "tx-out"}`}>
          {incoming ? "+" : "−"}{fmt(txn.amount)}
        </div>
        <div style={{ fontSize: 12, marginTop: 4 }}>
          <span className={`badge ${txn.status}`}>{txn.status}</span>
          {txn.flagged_fraud && <span className="badge flag" style={{ marginLeft: 6 }}>flagged</span>}
        </div>
      </div>
    </div>
  );
}
