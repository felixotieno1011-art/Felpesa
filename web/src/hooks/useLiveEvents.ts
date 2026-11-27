import { useEffect, useRef } from "react";

/** Holds a stream open to the API and calls onEvent when something changes. Reconnects with backoff. */
export function useLiveEvents(token: string | null | undefined, onEvent: () => void) {
  const cb = useRef(onEvent);
  cb.current = onEvent;

  useEffect(() => {
    if (!token) return;
    let stop = false;
    let ctrl: AbortController | null = null;

    async function run() {
      let delay = 1000;
      while (!stop) {
        ctrl = new AbortController();
        try {
          const res = await fetch("/api/notifications/stream", {
            headers: { Authorization: `Bearer ${token}` },
            signal: ctrl.signal,
          });
          if (res.status === 401) {
            window.dispatchEvent(new Event("felpesa-unauthorized"));
            return;
          }
          if (res.ok && res.body) {
            delay = 1000;
            const reader = res.body.getReader();
            const dec = new TextDecoder();
            let buf = "";
            while (!stop) {
              const { done, value } = await reader.read();
              if (done) break;
              buf += dec.decode(value, { stream: true });
              let i: number;
              while ((i = buf.indexOf("\n\n")) >= 0) {
                const chunk = buf.slice(0, i);
                buf = buf.slice(i + 2);
                if (chunk.includes("data:")) cb.current();
              }
            }
          }
        } catch {
          /* dropped: reconnect */
        }
        if (stop) return;
        await new Promise((r) => setTimeout(r, delay));
        delay = Math.min(delay * 2, 30000);
      }
    }
    void run();
    return () => {
      stop = true;
      ctrl?.abort();
    };
  }, [token]);
}
