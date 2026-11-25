import { useState } from "react";
import { api, ApiError, Transaction } from "../api/client";
import { useAuth } from "../auth";
import PinSheet from "../components/PinSheet";
import { usePinStatus } from "../hooks/usePinStatus";

type Kind = "paybill" | "till";
type Step = "form" | "confirm" | "done";

const fmt = (n: number) =>
  n.toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function Pay() {
  const { token } = useAuth();
  const [kind, setKind] = useState<Kind>("paybill");
  const [number, setNumber] = useState("");
  const [account, setAccount] = useState("");
  const [amount, setAmount] = useState("");
  const [step, setStep] = useState<Step>("form");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<Transaction | null>(null);
  const [idemKey, setIdemKey] = useState("");
  const hasPin = usePinStatus(token);
  const [pinOpen, setPinOpen] = useState(false);
  const [pinError, setPinError] = useState("");

  const amt = Number(amount);
  const valid =
    /^\d{5,10}$/.test(number) &&
    amt > 0 &&
    (kind === "till" || account.trim().length > 0);

  async function pay(pin?: string) {
    setBusy(true);
    setError("");
    setPinError("");
    try {
      const tx = await api<Transaction>(
        kind === "paybill" ? "/payments/paybill" : "/payments/till",
        {
          method: "POST",
          token,
          headers: pin ? { "Idempotency-Key": idemKey, "X-Pin": pin } : { "Idempotency-Key": idemKey },
          body: JSON.stringify({
            number,
            account_ref: kind === "paybill" ? account.trim() : null,
            amount: amt.toFixed(4),
            currency: "KES",
          }),
        }
      );
      setResult(tx);
      setStep("done");
      setPinOpen(false);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Something went wrong";
      if (pin && e instanceof ApiError && (e.status === 403 || e.status === 429)) {
        setPinError(msg);
      } else {
        setError(msg);
        setStep("form");
        setPinOpen(false);
      }
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setNumber("");
    setAccount("");
    setAmount("");
    setResult(null);
    setError("");
    setStep("form");
  }

  return (
    <div className="card">
      <h3>Pay</h3>

      {step === "form" && (
        <>
          <div className="flex mb-4">
            {(["paybill", "till"] as Kind[]).map((k) => (
              <button
                key={k}
                className={kind === k ? "primary" : ""}
                style={{ flex: 1 }}
                onClick={() => setKind(k)}
              >
                {k === "paybill" ? "Pay Bill" : "Buy Goods"}
              </button>
            ))}
          </div>

          <label>{kind === "paybill" ? "Business number" : "Till number"}</label>
          <input
            inputMode="numeric"
            value={number}
            onChange={(e) => setNumber(e.target.value.replace(/\D/g, ""))}
            placeholder={kind === "paybill" ? "888880" : "500100"}
          />

          {kind === "paybill" && (
            <>
              <label>Account number</label>
              <input
                value={account}
                maxLength={30}
                onChange={(e) => setAccount(e.target.value)}
                placeholder="e.g. METER123"
              />
            </>
          )}

          <label>Amount (KES)</label>
          <input
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value.replace(/[^\d.]/g, ""))}
            placeholder="0.00"
          />

          {error && <div className="error">{error}</div>}
          <button
            className="primary"
            style={{ width: "100%" }}
            disabled={!valid}
            onClick={() => {
              setError("");
              setIdemKey(crypto.randomUUID());
              setStep("confirm");
            }}
          >
            Continue
          </button>
        </>
      )}

      {step === "confirm" && (
        <>
          <p className="muted">Please confirm this payment</p>
          <div className="success" style={{ padding: 18 }}>
            <div className="balance">
              {fmt(amt)}
              <span className="currency">KES</span>
            </div>
            <div>
              {kind === "paybill" ? "Pay Bill" : "Till"} <b>{number}</b>
              {kind === "paybill" && (
                <>
                  {" "}· Acc <b>{account}</b>
                </>
              )}
            </div>
          </div>
          <button className="primary mt-4" style={{ width: "100%" }} disabled={busy} onClick={() => (hasPin ? setPinOpen(true) : pay())}>
            {busy ? "Paying..." : "Confirm & Pay"}
          </button>
          <button className="mt-2" style={{ width: "100%" }} disabled={busy} onClick={() => setStep("form")}>
            Back
          </button>
        </>
      )}

      {pinOpen && (
        <PinSheet
          busy={busy}
          error={pinError}
          onSubmit={(p) => pay(p)}
          onCancel={() => setPinOpen(false)}
        />
      )}

      {step === "done" && result && (
        <>
          <div className="success" style={{ padding: 18 }}>
            <b>Payment successful</b>
            <p className="mt-2" style={{ fontWeight: 400 }}>
              {result.message ?? "Confirmed."}
            </p>
          </div>
          <button className="primary mt-4" style={{ width: "100%" }} onClick={reset}>
            Make another payment
          </button>
        </>
      )}
    </div>
  );
}
