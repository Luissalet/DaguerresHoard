import { useEffect, useRef, useState } from "react";
import { useCopilotForm } from "../copilot-hooks";
import type { Dict } from "../i18n";
import type { PhotoEdits } from "../types";

interface Props {
  photoId: string;
  value: unknown;
  busy: boolean;
  t: Dict;
  onSave: (value: number | null) => Promise<PhotoEdits | undefined>;
}

const text = (value: unknown) => typeof value === "number" ? String(value) : "";

export default function RecipeExposure({ photoId, value, busy, t, onSave }: Props) {
  const [draft, setDraft] = useState(text(value));
  const current = useRef(draft);
  current.current = draft;
  const base = useRef(text(value));
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    const next = text(value);
    if (current.current === base.current) { current.current = next; setDraft(next); }
    base.current = next;
  }, [value]);
  useCopilotForm(() => ({ kind: "photo-exposure", object_id: photoId, dirty: draft !== base.current, fields: { exposure: draft } }));

  async function save(value: number | null) {
    const sent = current.current;
    const result = await onSave(value);
    if (!mounted.current || !result || result.photo_id !== photoId) return;
    const next = text(result.recipe.exposure);
    if (current.current === sent) { current.current = next; setDraft(next); }
    base.current = next;
  }

  return <form className="edits-form" onSubmit={(event) => { event.preventDefault(); if (draft !== "") void save(Number(draft)); }}>
    <label className="small">{t.recipe_exposure}
      <input className="input" type="number" min={-5} max={5} step="0.01" value={draft}
        placeholder={t.recipe_exposure_absent} onChange={(event) => { current.current = event.target.value; setDraft(event.target.value); }} />
    </label>
    <p className="muted small">{t.recipe_exposure_stored}: {typeof value === "number" ? `${value > 0 ? "+" : ""}${value} EV` : t.recipe_exposure_absent}</p>
    <div className="sidecar-actions">
      <button className="btn" type="submit" disabled={busy || draft === "" || draft === text(value)}>{t.recipe_exposure_save}</button>
      <button className="btn" type="button" disabled={busy || typeof value !== "number"} onClick={() => void save(null)}>{t.recipe_exposure_clear}</button>
    </div>
    <p className="muted small">{t.recipe_exposure_help}</p>
  </form>;
}
