import { useEffect, useRef, useState } from "react";
import { api, errorText, fileName } from "../api";
import { useCopilotForm } from "../copilot-hooks";
import type { Dict } from "../i18n";
import type { Photo, SearchResult } from "../types";
import "./similar-photos.css";

export default function SimilarPhotos({ photo, t, onOpen }: { photo: Photo; t: Dict; onOpen: (photo: Photo) => void }) {
  const [items, setItems] = useState<Photo[]>([]);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const request = useRef(0);
  const nextOffset = result?.has_more ? result.next_offset ?? null : null;

  async function load(offset: number) {
    const ticket = ++request.current;
    setBusy(true); setError(null);
    try {
      const page = await api.similar(photo.id, 12, offset);
      if (ticket !== request.current) return;
      setItems(previous => offset === 0 ? page.results : [...previous, ...page.results]);
      setResult(page);
    } catch (e) {
      if (ticket === request.current) setError(errorText(e));
    } finally {
      if (ticket === request.current) setBusy(false);
    }
  }

  useEffect(() => {
    void load(0);
    return () => { request.current++; };
    // The parent keys this component by photo.id: pages belong to this source only.
  }, []);

  useCopilotForm(() => ({ kind: "similar-photos", object_id: photo.id, dirty: false,
    fields: { source_photo_id: photo.id, source_path: photo.path, shown_ids: items.map(item => item.id),
      indexed_total: result?.indexed_total ?? null, next_offset: nextOffset, embedder: result?.embedder ?? null,
      note: result?.note ?? null, loading: busy, error } }));

  return <section className="side-section similar-photos" aria-label={t.similar_photos}>
    <h3 className="side-label">{t.similar_photos}</h3>
    <p className="muted small similar-photos__source">{t.similar_source}: {fileName(photo.path)}</p>
    {result && <p className="small" role="status">{t.similar_progress(items.length, result.indexed_total)}</p>}
    {result?.note && <p className="muted small">{result.note}</p>}
    {result?.embedder && <p className="muted small similar-photos__model">{t.similar_index}: {result.embedder}</p>}
    {items.length > 0 && <ol className="similar-photos__list">
      {items.map((item, index) => <li key={item.id}>
        <button type="button" className="similar-photos__item" onClick={() => onOpen(item)} title={item.path}>
          <img src={item.thumbnail_url} alt="" loading="lazy" />
          <span className="similar-photos__text"><strong>{fileName(item.path)}</strong>
            <span className="muted small">{item.path.replace(/[\\/][^\\/]*$/, "")}</span>
            <span className="muted small">{index + 1}{item.relevance ? ` · ${t.similar_band[item.relevance]}` : ""}</span>
          </span>
        </button>
      </li>)}
    </ol>}
    {result && items.length === 0 && <p className="muted small">{t.similar_empty}</p>}
    {error && <p className="error-text small" role="alert">{error}</p>}
    {busy && <p className="muted small" role="status">{t.loading}</p>}
    {(error || nextOffset !== null) && <button type="button" className="btn" disabled={busy}
      onClick={() => void load(nextOffset ?? 0)}>{error ? t.similar_retry : t.similar_more}</button>}
  </section>;
}
