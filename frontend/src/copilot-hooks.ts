// React glue for copilot-context.ts: views say what is open, answer the form-snapshot request and reload on turn end.
import { useEffect, useRef } from "react";
import { CONTEXT_EVENT, onRefresh, registerOpen, type EditorSnapshot, type OpenState } from "./copilot-context";

// Answer the launcher's context request with this form's snapshot (null = no form to report right now).
export function useCopilotForm(snapshot: () => EditorSnapshot | null) {
  const latest = useRef(snapshot);
  latest.current = snapshot;
  useEffect(() => {
    const handler = (e: Event) => {
      try {
        const s = latest.current();
        if (s) (e as CustomEvent).detail?.provide?.(s);
      } catch {
        // a broken snapshot must not hide the other forms
      }
    };
    window.addEventListener(CONTEXT_EVENT, handler);
    return () => window.removeEventListener(CONTEXT_EVENT, handler);
  }, []);
}

// Run `reload` (in place, no remount) when the assistant finishes a turn.
export function useCopilotRefresh(reload: () => void) {
  const latest = useRef(reload);
  latest.current = reload;
  useEffect(() => onRefresh(() => latest.current()), []);
}

// Tell the launcher what this view shows while it is open.
export function useCopilotOpen<K extends "photo" | "album" | "video" | "search">(key: K, value: OpenState[K], dep: string) {
  useEffect(() => {
    if (!value) return;
    return registerOpen(key, value as NonNullable<OpenState[K]>);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, dep]);
}
