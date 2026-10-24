import { useEffect, useRef, useState } from "react";
import { useCopilotForm } from "../copilot-hooks";
import type { Dict } from "../i18n";
import type { PhotoEdits } from "../types";

const keys = ["temperature", "tint"] as const;
type Field = typeof keys[number];
type Draft = Record<Field, string>;
type Patch = Partial<Record<Field, number | null>>;
const text = (value: unknown) => typeof value === "number" ? String(value) : "";
const values = (recipe: Record<string, unknown>): Draft => ({ temperature: text(recipe.temperature), tint: text(recipe.tint) });

interface Props {
  photoId: string;
  recipe: Record<string, unknown>;
  busy: boolean;
  t: Dict;
  onSave: (patch: Patch) => Promise<PhotoEdits | undefined>;
}

export default function RecipeWhiteBalance({ photoId, recipe, busy, t, onSave }: Props) {
  const [draft, setDraft] = useState(() => values(recipe));
  const current = useRef(draft);
  current.current = draft;
  const base = useRef(values(recipe));
  const alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => {
    const next = values(recipe);
    const rebased = { ...current.current };
    for (const key of keys) if (rebased[key] === base.current[key]) rebased[key] = next[key];
    current.current = rebased;
    base.current = next;
    setDraft(rebased);
  }, [recipe.temperature, recipe.tint]); // Other recipe settings cannot reset these drafts.

  const changed = keys.filter(key => draft[key] !== text(recipe[key]));
  useCopilotForm(() => ({ kind: "photo-white-balance", object_id: photoId, dirty: changed.length > 0,
    fields: { ...draft, saved_recipe: { temperature: recipe.temperature ?? null, tint: recipe.tint ?? null } } }));

  async function save(patch: Patch) {
    const sent = { ...current.current };
    const result = await onSave(patch);
    if (!alive.current || !result || result.photo_id !== photoId) return;
    const next = values(result.recipe);
    const rebased = { ...current.current };
    for (const key of keys) if (key in patch && rebased[key] === sent[key]) rebased[key] = next[key];
    current.current = rebased;
    base.current = next;
    setDraft(rebased);
  }

  return <form className="side-section edits-form" aria-label={t.recipe_wb_title} onSubmit={event => {
    event.preventDefault();
    if (!changed.length || changed.some(key => draft[key] === "")) return;
    void save(Object.fromEntries(changed.map(key => [key, Number(draft[key])])));
  }}>
    <div className="side-label">{t.recipe_wb_title}</div>
    {keys.map(key => <div key={key}>
      <label className="small">{key === "temperature" ? t.recipe_wb_temperature : t.recipe_wb_tint}
        <input className="input" type="number" min={key === "temperature" ? 2000 : -150}
          max={key === "temperature" ? 50000 : 150} step="1" value={draft[key]}
          placeholder={t.recipe_wb_absent} onChange={event => {
            const next = { ...current.current, [key]: event.target.value };
            current.current = next; setDraft(next);
          }} />
      </label>
      <p className="muted small">{t.recipe_exposure_stored}: {typeof recipe[key] === "number"
        ? `${recipe[key]}${key === "temperature" ? " K" : ""}` : t.recipe_wb_absent}</p>
      <button className="btn" type="button" disabled={busy || typeof recipe[key] !== "number"}
        onClick={() => void save({ [key]: null })}>{key === "temperature" ? t.recipe_wb_clear_temperature : t.recipe_wb_clear_tint}</button>
    </div>)}
    <button className="btn" type="submit" disabled={busy || !changed.length || changed.some(key => draft[key] === "")}>{t.recipe_wb_save}</button>
    <p className="muted small">{t.recipe_wb_help}</p>
  </form>;
}
