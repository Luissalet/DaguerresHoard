import { useEffect, useRef, useState } from "react";
import { Download, ExternalLink } from "lucide-react";
import { api, errorText, fileName, type SelectionExportResult } from "../api";
import type { Dict } from "../i18n";
import type { Photo } from "../types";
import "./selection-export.css";

export default function SelectionExport({ photos, t, initialTitle }: { photos: Photo[]; t: Dict; initialTitle?: string }) {
  const [title, setTitle] = useState(initialTitle ?? "");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SelectionExportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const request = useRef(0);
  const signature = photos.map(photo => photo.id).join(",");
  useEffect(() => { request.current++; setResult(null); setError(null); }, [signature]);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    const version = ++request.current;
    setBusy(true); setError(null); setResult(null);
    try {
      const output = await api.exportSelection(photos.map(photo => photo.id), title.trim());
      if (request.current === version) setResult(output);
    } catch (failure) {
      if (request.current === version) setError(errorText(failure));
    } finally { setBusy(false); }
  }

  const base = result ? `/photos/api/exports/${result.id}` : "";
  return <section className="selection-export" aria-label={t.export_selection}>
    <h3>{t.export_selection} <span className="muted">· {photos.length}/20</span></h3>
    <p className="muted small">{t.export_note}</p>
    <ol className="selection-export__photos" aria-label={t.export_choose}>
      {photos.map((photo, index) => <li key={photo.id}>
        <img src={photo.thumbnail_url} alt="" />
        <span title={fileName(photo.path)}>{index + 1}. {fileName(photo.path)}</span>
      </li>)}
    </ol>
    <form onSubmit={create} className="selection-export__form">
      <label><span>{t.export_title}</span><input className="input" required maxLength={160} value={title}
        disabled={busy} onChange={event => { setTitle(event.target.value); setResult(null); }} /></label>
      <button className="btn btn-primary" type="submit" disabled={busy || photos.length < 1 || photos.length > 20 || !title.trim()}>
        <Download size={14} /> {busy ? t.export_working : t.export_selection}
      </button>
    </form>
    {error && <p role="alert" className="error-text">{error}</p>}
    <div aria-live="polite" aria-atomic="true">
      {result && <div className="selection-export__result">
        <p>{t.export_result(result.returned, result.requested)} · {result.title}</p>
        {!result.complete && <p className="muted">{t.export_omitted(result.omitted.length)}</p>}
        <div className="toolbar">
          <a className="btn btn-primary" href={`${base}/gallery.html`} target="_blank" rel="noreferrer"><ExternalLink size={14} /> {t.export_gallery}</a>
          <a className="btn" href={`${base}/gallery.html`} download>{t.export_download}</a>
          <a className="btn" href={`${base}/contact-sheet.jpg`} download>{t.export_sheet}</a>
          <a className="btn" href={`${base}/manifest.json`} download>{t.export_manifest}</a>
        </div>
        <img className="selection-export__sheet" src={`${base}/contact-sheet.jpg`} alt={result.title} />
      </div>}
    </div>
  </section>;
}
