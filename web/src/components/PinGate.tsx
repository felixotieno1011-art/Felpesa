import { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth";
import { usePinStatus } from "../hooks/usePinStatus";

export default function PinGate({ children }: { children: ReactNode }) {
  const { token } = useAuth();
  const hasPin = usePinStatus(token);
  if (hasPin === null) return <div className="card"><p className="muted">Loading...</p></div>;
  if (!hasPin)
    return (
      <div className="card">
        <h3>Set your PIN first</h3>
        <p className="muted">A 4-digit PIN is required to send money, pay and buy airtime.</p>
        <Link to="/pin"><button className="primary" style={{ width: "100%" }}>Set PIN</button></Link>
      </div>
    );
  return <>{children}</>;
}
