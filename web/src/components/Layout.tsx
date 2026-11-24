import { Link, NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";

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
        <NavLink to="/" end>
          {({ isActive }) => (
            <span className={isActive ? "active" : ""} style={{ padding: "8px 14px", borderRadius: 8, display: "inline-block" }}>
              Dashboard
            </span>
          )}
        </NavLink>
        <NavLink to="/send">
          {({ isActive }) => (
            <span className={isActive ? "active" : ""} style={{ padding: "8px 14px", borderRadius: 8, display: "inline-block" }}>
              Send
            </span>
          )}
        </NavLink>
        <NavLink to="/history">
          {({ isActive }) => (
            <span className={isActive ? "active" : ""} style={{ padding: "8px 14px", borderRadius: 8, display: "inline-block" }}>
              History
            </span>
          )}
        </NavLink>
        <NavLink to="/admin">
          {({ isActive }) => (
            <span className={isActive ? "active" : ""} style={{ padding: "8px 14px", borderRadius: 8, display: "inline-block" }}>
              Admin
            </span>
          )}
        </NavLink>
        <span className="spacer" />
        <button onClick={handleLogout}>Logout</button>
      </nav>
      <Outlet />
    </div>
  );
}
