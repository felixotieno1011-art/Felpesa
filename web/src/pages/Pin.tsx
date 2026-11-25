import { useState } from "react";
import { api, ApiError } from "../api/client";
import { useAuth } from "../auth";
import { usePinStatus } from "../hooks/usePinStatus";

export default function Pin() {
  const { token } = useAuth();
  const hasPin = usePinStatus(token);
  const [oldPin, setOldPin] = useState("");
  const [pin, setPin] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState(false);

  const digits = (v: string) => v.replace(/\D/g, "").slice(0, 4);
  const valid =
    pin.length === 4 && pin === again && (hasPin !== true || oldPin.length === 4);

  async function save() {
    setBusy(true);
    setError("");
    setOk(false);
    try {
      await api("/pin", {
        method: "POST",
        token,
        body: JSON.stringify({ pin, old_pin: hasPin ? oldPin : null }),
      });
      setOk(true);
      setOldPin("");
      setPin("");
      setAgain("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h3>{hasPin ? "Change PIN" : "Set PIN"}</h3>
      <p className="muted">A 4-digit PIN is required to send money, pay and withdraw.</p>

      {hasPin && (
        <>
          <label>Current PIN</label>
          <input type="password" inputMode="numeric" value={oldPin}
            onChange={(e) => setOldPin(digits(e.target.value))} />
        </>
      )}
      <label>New PIN</label>
      <input type="password" inputMode="numeric" value={pin}
        onChange={(e) => setPin(digits(e.target.value))} />
      <label>Repeat new PIN</label>
      <input type="password" inputMode="numeric" value={again}
        onChange={(e) => setAgain(digits(e.target.value))} />

      {error && <div className="error">{error}</div>}
      {ok && <div className="success">PIN saved.</div>}
      <button className="primary" style={{ width: "100%" }} disabled={busy || !valid} onClick={save}>
        {busy ? "Saving..." : "Save PIN"}
      </button>
    </div>
  );
}
