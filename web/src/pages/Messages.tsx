import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth";

type Msg = {
  id: string; kind: string; title: string; body: string;
  transaction_id: string | null; is_read: boolean; created_at: string;
};

export default function Messages() {
  const { token } = useAuth();
  const nav = useNavigate();
  const [items, setItems] = useState<Msg[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const r = await api<{ items: Msg[]; unread: number }>("/notifications", { token });
      setItems(r.items);
      setUnread(r.unread);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { if (token) void load(); }, [token, load]);

  async function open(m: Msg) {
    if (!m.is_read) {
      await api(`/notifications/${m.id}/read`, { method: "POST", token }).catch(() => {});
    }
    if (m.transaction_id) nav(`/receipt/${m.transaction_id}`);
    else void load();
  }

  async function remove(m: Msg) {
    await api(`/notifications/${m.id}`, { method: "DELETE", token }).catch(() => {});
    setItems((xs) => xs.filter((x) => x.id !== m.id));
    if (!m.is_read) setUnread((u) => Math.max(0, u - 1));
  }

  async function readAll() {
    await api("/notifications/read-all", { method: "POST", token }).catch(() => {});
    void load();
  }

  return (
    <div className="card">
      <div className="flex-between">
        <h3>Messages{unread > 0 ? ` (${unread})` : ""}</h3>
        {unread > 0 && <button className="link" onClick={readAll}>Mark all read</button>}
      </div>
      {error && <div className="error">{error}</div>}
      {loading ? (
        <p className="muted">Loading...</p>
      ) : items.length === 0 ? (
        <p className="muted">No messages yet.</p>
      ) : (
        items.map((m) => (
          <div className="row" key={m.id}>
            <div style={{ flex: 1, minWidth: 0, cursor: "pointer" }} onClick={() => open(m)}>
              <div className="row-main">
                {!m.is_read && <span style={{ color: "var(--green)" }}>● </span>}
                {m.title}
              </div>
              <div className="tx-msg" style={{ maxWidth: "100%" }}>{m.body}</div>
              <div className="row-sub">
                {new Date(m.created_at).toLocaleString("en-KE", {
                  day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
                })}
              </div>
            </div>
            <button aria-label="Delete message" onClick={() => remove(m)} style={{ padding: 8 }}>
              ✕
            </button>
          </div>
        ))
      )}
    </div>
  );
}
