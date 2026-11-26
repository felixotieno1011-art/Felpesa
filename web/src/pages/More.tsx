import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import {
  ArrowUpFromLine, ChevronRight, LogOut, Mail, Plus, ShieldCheck, Smartphone, UserCog,
} from "../components/icons";

const ITEMS = [
  { to: "/messages", label: "Inbox", Icon: Mail },
  { to: "/mpesa", label: "Top up with M-Pesa (test)", Icon: Plus },
  { to: "/money", label: "Deposit / Withdraw", Icon: ArrowUpFromLine },
  { to: "/airtime", label: "Buy airtime", Icon: Smartphone },
  { to: "/pin", label: "PIN & security", Icon: ShieldCheck },
  { to: "/admin", label: "Admin", Icon: UserCog },
];

export default function More() {
  const { logout } = useAuth();
  const nav = useNavigate();
  return (
    <div className="card flush">
      <h3 style={{ padding: "20px 20px 4px" }}>More</h3>
      <div className="menu-list">
        {ITEMS.map(({ to, label, Icon }) => (
          <Link key={to} to={to} className="menu-item">
            <span className="menu-ico"><Icon size={20} /></span>
            <span style={{ flex: 1 }}>{label}</span>
            <ChevronRight size={18} />
          </Link>
        ))}
        <button className="menu-item menu-out" onClick={() => { logout(); nav("/login"); }}>
          <span className="menu-ico"><LogOut size={20} /></span>
          <span style={{ flex: 1, textAlign: "left" }}>Log out</span>
        </button>
      </div>
    </div>
  );
}
