import { useEffect, useState } from "react";
import { api } from "../api/client";

/** true = PIN set, false = no PIN, null = still loading / unknown */
export function usePinStatus(token: string | null | undefined): boolean | null {
  const [has, setHas] = useState<boolean | null>(null);
  useEffect(() => {
    if (!token) return;
    api<{ has_pin: boolean }>("/pin/status", { token })
      .then((r) => setHas(r.has_pin))
      .catch(() => setHas(null));
  }, [token]);
  return has;
}
