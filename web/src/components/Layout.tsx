import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

const TABS = [
  { to: "/", label: "Home", ico: "🏠", end: true },
  { to: "/send", label: "Send", ico: "💸", end: false },
  { to: "/pay", label: "Pay", ico: "🧾", end: false },
  { to: "/money", label: "Money", ico: "💰", end: false },
  { to: "/history", label: "History", ico: "🕘", end: false },
];

const cls = ({ isActive }: { isActive: boolean }) => (isActive ? "active" : "");

export default function Layout() {
  const { logout } = useAuth();
  const nav = useNavigate();

  const handleLogout = () => {
    logout();
    nav("/login");
  };

  return (
    <div className="container">
      <nav className="nav">
        <span className="nav-brand">Felpesa</span>
        {TABS.map((t) => (
          <NavLink key={t.to} to={t.to} end={t.end} className={cls}>
            {t.label}
          </NavLink>
        ))}
        <NavLink to="/admin" className={cls}>
          Admin
        </NavLink>
        <span className="spacer" />
        <button onClick={handleLogout}>Logout</button>
      </nav>

      <Outlet />

      <div className="tabbar">
        {TABS.map((t) => (
          <NavLink key={t.to} to={t.to} end={t.end} className={cls}>
            <span className="ico">{t.ico}</span>
            {t.label}
          </NavLink>
        ))}
      </div>
    </div>
  );
}
