import { useEffect, useState } from "react";
import { ArrowLeftRight, Columns2, X } from "lucide-react";
import { api, fileName, formatBytes, parentFolder } from "../api";
import { useCopilotForm, useCopilotRefresh } from "../copilot-hooks";
import type { Dict } from "../i18n";
import type { Photo } from "../types";
import { loadComparisonPhoto, type ComparisonResult } from "./comparison-state";
import "./photo-comparison.css";

function PhotoSide({ photo, slot, t, onOpen }: { photo?: Photo; slot: string; t: Dict; onOpen: () => void }) {
  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [failedPreview, setFailedPreview] = useState<string | null>(null);
  useCopilotRefresh(() => setRefresh(value => value + 1));
  useEffect(() => {
    setResult(null); setFailedPreview(null);
    if (photo) return loadComparisonPhoto(photo.id, api.getPhoto, setResult);
  }, [photo?.id, refresh]);
  // Effects clear old requests after render: this identity check also protects that first render.
  const current = result?.id === photo?.id ? result : null;
  const detail = current?.detail?.id === photo?.id ? current?.detail : undefined;
  useCopilotForm(() => photo ? { kind: "photo-comparison-side", object_id: photo.id, dirty: false,
    fields: { slot, photo_id: photo.id, loading: !current, error: current?.error,
      ...(detail ? { path: detail.path, taken_at: detail.taken_at, width: detail.width, height: detail.height,
        size: detail.size, make: detail.make, model: detail.model, lens: detail.lens,
        f_number: detail.f_number, exposure_time: detail.exposure_time, iso: detail.iso, focal_length: detail.focal_length } : {}) } } : null);
  if (!photo) return <p className="muted comparison-empty">{t.compare_choose}</p>;
  const exposure = detail ? [detail.f_number ? `f/${detail.f_number}` : null, detail.exposure_time, detail.iso ? `ISO ${detail.iso}` : null, detail.focal_length ? `${detail.focal_length} mm` : null].filter(Boolean).join(" · ") : "";
  return <div className="comparison-photo">
    <p className="comparison-path">{photo.path}</p>
    <div className="comparison-preview">
      {failedPreview === photo.id ? <p className="error-text">{t.missing_file}</p> :
        <img key={`${photo.id}:${refresh}`} src={api.previewUrl(photo.id)} alt={`${slot}: ${fileName(photo.path)}`} onError={() => setFailedPreview(photo.id)} />}
    </div>
    <p className="muted small">{t.compare_preview}</p>
    {!current && <p className="muted" role="status">{t.loading}</p>}
    {current?.error && <p className="error-text" role="alert">{current.error}</p>}
    {detail && <dl className="comparison-metadata">
      <dt>{t.compare_dimensions}</dt><dd>{detail.width && detail.height ? `${detail.width} × ${detail.height}` : t.compare_not_recorded}</dd>
      <dt>{t.compare_size}</dt><dd>{formatBytes(detail.size)}</dd>
      <dt>{t.when}</dt><dd>{detail.taken_at || t.compare_not_recorded}{detail.date_source === "file_mtime" && ` (${t.file_date})`}</dd>
      <dt>{t.compare_camera}</dt><dd>{[detail.make, detail.model, detail.lens].filter(Boolean).join(" · ") || t.compare_not_recorded}</dd>
      <dt>{t.compare_exposure}</dt><dd>{exposure || t.compare_not_recorded}</dd>
    </dl>}
    <div className="comparison-actions">
      <button type="button" className="btn" onClick={onOpen}>{t.compare_open} {slot}</button>
      {(current?.error || failedPreview === photo.id) && <button type="button" className="btn" onClick={() => setRefresh(value => value + 1)}>{t.compare_retry}</button>}
    </div>
  </div>;
}

export default function PhotoComparison({ photos, onOpen, open, onClose, t }: { photos: Photo[]; onOpen: (index: number) => void; open: boolean; onClose: () => void; t: Dict }) {
  const [a, setA] = useState(photos[0]?.id ?? "");
  const [b, setB] = useState(photos[1]?.id ?? "");
  const available = new Map(photos.map(photo => [photo.id, photo]));
  useCopilotForm(() => open ? { kind: "photo-comparison", object_id: null, dirty: false,
    fields: { scope: "currently_loaded_photos", photo_ids: [a, b], a_visible: available.has(a), b_visible: available.has(b) } } : null);
  if (!open) return null;
  return <section className="photo-comparison" aria-label={t.compare_title}>
    <div className="comparison-heading"><h3><Columns2 size={17} /> {t.compare_title}</h3>
      <div className="comparison-actions">
        <button type="button" className="btn" onClick={() => { setA(b); setB(a); }}><ArrowLeftRight size={14} /> {t.compare_swap}</button>
        <button type="button" className="btn" onClick={onClose}><X size={14} /> {t.close}</button>
      </div>
    </div>
    <p className="muted small">{t.compare_scope}</p>
    <div className="comparison-columns">
      {([["A", a, setA], ["B", b, setB]] as const).map(([slot, id, setId]) => <div className="comparison-side" key={slot}>
        <label>{t.compare_photo} {slot}<select value={id} onChange={event => setId(event.target.value)}>
          <option value="">{t.compare_choose}</option>
          {id && !available.has(id) && <option value={id}>{t.compare_not_visible}</option>}
          {photos.map(photo => <option value={photo.id} key={photo.id}>{fileName(photo.path)} · {parentFolder(photo.path)}</option>)}
        </select></label>
        {id && !available.has(id) && <p className="muted" role="status">{t.compare_not_visible}</p>}
        <PhotoSide photo={available.get(id)} slot={slot} t={t} onOpen={() => { const index = photos.findIndex(photo => photo.id === id); if (index >= 0) onOpen(index); }} />
      </div>)}
    </div>
  </section>;
}
