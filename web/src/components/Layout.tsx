import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth";
import { useLiveEvents } from "../hooks/useLiveEvents";
import {
  ArrowUpFromLine, History, Home, LogOut, Mail, MoreHorizontal, Plus, Receipt,
  Send, ShieldCheck, Smartphone, UserCog,
} from "./icons";

const MAIN = [
  { to: "/", label: "Home", Icon: Home, end: true },
  { to: "/send", label: "Send", Icon: Send, end: false },
  { to: "/pay", label: "Pay", Icon: Receipt, end: false },
  { to: "/history", label: "Activity", Icon: History, end: false },
  { to: "/messages", label: "Inbox", Icon: Mail, end: false },
];
const MORE = [
  { to: "/mpesa", label: "Top up (M-Pesa)", Icon: Plus },
  { to: "/money", label: "Deposit / Withdraw", Icon: ArrowUpFromLine },
  { to: "/airtime", label: "Airtime", Icon: Smartphone },
  { to: "/pin", label: "PIN & security", Icon: ShieldCheck },
  { to: "/admin", label: "Admin", Icon: UserCog },
];
const BOTTOM = [
  { to: "/", label: "Home", Icon: Home, end: true },
  { to: "/send", label: "Send", Icon: Send, end: false },
  { to: "/pay", label: "Pay", Icon: Receipt, end: false },
  { to: "/history", label: "Activity", Icon: History, end: false },
  { to: "/more", label: "More", Icon: MoreHorizontal, end: false },
];

const side = ({ isActive }: { isActive: boolean }) => "side-link" + (isActive ? " active" : "");
const tab = ({ isActive }: { isActive: boolean }) => "tab-link" + (isActive ? " active" : "");

export default function Layout() {
  const { token, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [unread, setUnread] = useState(0);

  const refresh = () => {
    if (!token) return;
    api<{ unread: number }>("/notifications/unread-count", { token })
      .then((r) => setUnread(r.unread))
      .catch(() => {});
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 30000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, loc.pathname]);

  useLiveEvents(token, () => {
    refresh();
    window.dispatchEvent(new Event("felpesa-live"));
  });

  const out = () => {
    logout();
    nav("/login");
  };
  const badge = unread > 0 ? <span className="badge-dot">{unread > 9 ? "9+" : unread}</span> : null;

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="side-brand">Felpesa</div>
        {MAIN.map(({ to, label, Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={side}>
            <Icon size={18} /> <span>{label}</span>
            {to === "/messages" && badge}
          </NavLink>
        ))}
        <div className="side-sep" />
        {MORE.map(({ to, label, Icon }) => (
          <NavLink key={to} to={to} className={side}>
            <Icon size={18} /> <span>{label}</span>
          </NavLink>
        ))}
        <button className="side-logout" onClick={out}>
          <LogOut size={18} /> Log out
        </button>
      </aside>

      <main className="main">
        <Outlet />
      </main>

      <nav className="bottombar">
        {BOTTOM.map(({ to, label, Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={tab}>
            <span className="tab-ico">
              <Icon size={22} />
              {to === "/more" && badge}
            </span>
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
