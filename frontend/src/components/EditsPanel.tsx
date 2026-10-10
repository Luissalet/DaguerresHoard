import { useEffect, useState } from "react";
import { FileText, RefreshCw, Save, Star } from "lucide-react";
import { api, errorText } from "../api";
import type { Dict } from "../i18n";
import type { PhotoEdits } from "../types";

interface Props {
  photoId: string;
  t: Dict;
  // the recipe's exposure becomes the starting point of the exposure slider below
  onExposure?: (ev: number) => void;
}

function recipeSummary(recipe: Record<string, unknown>): string[] {
  return Object.entries(recipe).map(([key, value]) => {
    if (key === "crop" && value && typeof value === "object") return "crop";
    if (typeof value === "number") return `${key} ${value > 0 && key !== "temperature" ? "+" : ""}${value}`;
    return `${key} ${String(value)}`;
  });
}

export default function EditsPanel({ photoId, t, onExposure }: Props) {
  const [edits, setEdits] = useState<PhotoEdits | null>(null);
  const [label, setLabel] = useState("");
  const [keywords, setKeywords] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function adopt(e: PhotoEdits) {
    setEdits(e);
    setLabel(e.label ?? "");
    setKeywords((e.keywords ?? []).join(", "));
    const ev = e.recipe.exposure;
    if (typeof ev === "number" && onExposure) onExposure(Math.max(-3, Math.min(3, ev)));
  }

  useEffect(() => {
    setEdits(null);
    setMsg(null);
    setError(null);
    let alive = true;
    api
      .getEdits(photoId)
      .then((e) => alive && adopt(e))
      .catch(() => {});
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [photoId]);

  async function run(fn: () => Promise<PhotoEdits>) {
    setBusy(true);
    setMsg(null);
    setError(null);
    try {
      const updated = await fn();
      adopt(updated);
      if (updated.sidecar_write?.written) setMsg(t.sidecar_written);
      else if (updated.sidecar_write?.error) setError(updated.sidecar_write.error);
      else setMsg(t.edits_saved);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  if (!edits) return null;
  const rating = edits.rating ?? 0;
  const recipe = recipeSummary(edits.recipe);
  const sidecar = edits.sidecar;
  const importedCount = edits.imported_not_applied ? Object.keys(edits.imported_not_applied.crs).length : 0;

  return (
    <section className="side-section edits-panel">
      <div className="side-label">{t.edits_title}</div>
      <div className="star-row" role="group" aria-label={t.edits_rating}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            className={`star-btn ${n <= rating ? "on" : ""}`}
            disabled={busy}
            aria-label={`${n}`}
            aria-pressed={n <= rating}
            onClick={() => run(() => api.setEdits(photoId, { rating: rating === n ? 0 : n }))}
          >
            <Star size={16} fill={n <= rating ? "currentColor" : "none"} />
          </button>
        ))}
        {rating < 0 && <span className="muted small">{t.edits_rejected}</span>}
      </div>
      <form
        className="edits-form"
        onSubmit={(e) => {
          e.preventDefault();
          run(() =>
            api.setEdits(photoId, {
              label,
              keywords: keywords
                .split(",")
                .map((k) => k.trim())
                .filter(Boolean),
            }),
          );
        }}
      >
        <input className="input" placeholder={t.edits_label} value={label} onChange={(e) => setLabel(e.target.value)} maxLength={64} />
        <input className="input" placeholder={t.edits_keywords} value={keywords} onChange={(e) => setKeywords(e.target.value)} />
        <button className="btn" type="submit" disabled={busy}>
          <Save size={14} /> {t.edits_save}
        </button>
      </form>
      <p className="muted small edits-recipe" title={t.edits_recipe}>
        {recipe.length ? `${t.edits_recipe}: ${recipe.join(" · ")}` : t.edits_no_recipe}
      </p>
      {importedCount > 0 && (
        <p className="muted small" title={Object.keys(edits.imported_not_applied?.crs ?? {}).join(", ")}>
          {t.imported_not_applied(importedCount)}
        </p>
      )}
      <div className="sidecar-row">
        <FileText size={14} />
        <span className="small">
          <strong>{t.sidecar_title}</strong>:{" "}
          {!sidecar.exists
            ? t.sidecar_none
            : sidecar.written_by === "daguerre"
              ? t.sidecar_by_daguerre
              : sidecar.written_by === "invalid"
                ? t.sidecar_invalid
                : t.sidecar_by_foreign}
          {sidecar.exists && sidecar.changed_on_disk && <span className="muted"> {t.sidecar_changed}</span>}
        </span>
      </div>
      <div className="sidecar-actions">
        <button className="btn" disabled={busy || !sidecar.exists} onClick={() => run(() => api.readSidecar(photoId))}>
          <RefreshCw size={14} /> {t.sidecar_reread}
        </button>
        <button
          className="btn"
          disabled={busy || !edits.write_sidecars}
          title={!edits.write_sidecars ? t.sidecar_write_off : undefined}
          onClick={() => run(() => api.writeSidecar(photoId))}
        >
          <FileText size={14} /> {t.sidecar_write}
        </button>
      </div>
      {!edits.write_sidecars && <p className="muted small">{t.sidecar_write_off}</p>}
      {msg && <p className="muted small">{msg}</p>}
      {error && <p className="error-text small">{error}</p>}
    </section>
  );
}
