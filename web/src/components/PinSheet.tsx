import { useState } from "react";

export default function PinSheet({
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  busy: boolean;
  error: string;
  onSubmit: (pin: string) => void;
  onCancel: () => void;
}) {
  const [pin, setPin] = useState("");
  return (
    <div className="sheet-backdrop" onClick={onCancel}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <h3>Enter your PIN</h3>
        <input
          className="pin-input"
          type="password"
          inputMode="numeric"
          autoFocus
          maxLength={4}
          value={pin}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, ""))}
          placeholder="••••"
        />
        {error && <div className="error">{error}</div>}
        <button
          className="primary"
          style={{ width: "100%" }}
          disabled={busy || pin.length !== 4}
          onClick={() => {
            onSubmit(pin);
            setPin("");
          }}
        >
          {busy ? "Checking..." : "Confirm"}
        </button>
        <button className="mt-2" style={{ width: "100%" }} disabled={busy} onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}
