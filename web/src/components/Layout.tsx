import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth";

const TABS = [
  { to: "/", label: "Home", ico: "🏠", end: true },
  { to: "/send", label: "Send", ico: "💸", end: false },
  { to: "/pay", label: "Pay", ico: "🧾", end: false },
  { to: "/money", label: "Money", ico: "💰", end: false },
  { to: "/history", label: "History", ico: "🕘", end: false },
  { to: "/messages", label: "Inbox", ico: "✉️", end: false },
];

const cls = ({ isActive }: { isActive: boolean }) => (isActive ? "active" : "");

export default function Layout() {
  const { token, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    if (!token) return;
    let live = true;
    const tick = () =>
      api<{ unread: number }>("/notifications/unread-count", { token })
        .then((r) => live && setUnread(r.unread))
        .catch(() => {});
    tick();
    const t = setInterval(tick, 30000);
    return () => {
      live = false;
      clearInterval(t);
    };
  }, [token, loc.pathname]);

  const handleLogout = () => {
    logout();
    nav("/login");
  };

  const badge = (to: string) =>
    to === "/messages" && unread > 0 ? <span className="badge-dot">{unread > 9 ? "9+" : unread}</span> : null;

  return (
    <div className="container">
      <nav className="nav">
        <span className="nav-brand">Felpesa</span>
        {TABS.map((t) => (
          <NavLink key={t.to} to={t.to} end={t.end} className={cls}>
            {t.label}
            {badge(t.to)}
          </NavLink>
        ))}
        <NavLink to="/pin" className={cls}>PIN</NavLink>
        <NavLink to="/admin" className={cls}>Admin</NavLink>
        <span className="spacer" />
        <button onClick={handleLogout}>Logout</button>
      </nav>

      <Outlet />

      <div className="tabbar">
        {TABS.map((t) => (
          <NavLink key={t.to} to={t.to} end={t.end} className={cls}>
            <span className="ico">{t.ico}{badge(t.to)}</span>
            {t.label}
          </NavLink>
        ))}
      </div>
    </div>
  );
}
