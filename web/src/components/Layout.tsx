import { Link, Outlet, useNavigate } from "react-router-dom";
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
        <strong>Felpesa</strong>
        <Link to="/">Dashboard</Link>
        <Link to="/send">Send</Link>
        <Link to="/history">History</Link>
        <Link to="/admin">Admin</Link>
        <span className="spacer" />
        <button onClick={handleLogout}>Logout</button>
      </nav>
      <Outlet />
    </div>
  );
}
