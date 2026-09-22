import { useEffect, useState } from "react";
import { api } from "./api";
import type { BackendStatus, ResolutionInfo } from "./types";

// One shared copy of GET /api/backend for every screen that has a model
// control (Settings, the lightbox caption button, the search box). The
// server already caches probes for 30 s, so reusing an answer for that
// long costs nothing and avoids re-probing on every lightbox open.
const TTL_MS = 30_000;
let cached: { at: number; value: BackendStatus } | null = null;
let inflight: Promise<BackendStatus> | null = null;
const listeners = new Set<(s: BackendStatus) => void>();

export function publishBackend(status: BackendStatus): void {
  cached = { at: Date.now(), value: status };
  listeners.forEach((listener) => listener(status));
}

export function loadBackend(force = false): Promise<BackendStatus> {
  if (!force && cached && Date.now() - cached.at < TTL_MS) return Promise.resolve(cached.value);
  if (!force && inflight) return inflight;
  inflight = api
    .getBackend()
    .then((status) => {
      publishBackend(status);
      return status;
    })
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

export function useBackend(): BackendStatus | null {
  const [status, setStatus] = useState<BackendStatus | null>(cached?.value ?? null);
  useEffect(() => {
    listeners.add(setStatus);
    loadBackend().catch(() => {});
    return () => {
      listeners.delete(setStatus);
    };
  }, []);
  return status;
}

/** The reason to show when a capability is missing, or null when it resolved
 * (or the status has not loaded yet, in which case the control stays usable
 * and the server's own error message still applies). */
export function missingReason(res: ResolutionInfo | undefined, emptyState: string): string | null {
  if (!res || res.state === "resolved") return null;
  return res.reason ? `${emptyState} (${res.reason})` : emptyState;
}
