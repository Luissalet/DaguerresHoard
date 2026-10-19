import { useEffect, useRef, useState } from 'react';
import { api, errorText, fileName, type ReferenceMatchResult } from '../api';
import type { Dict } from '../i18n';
import type { Photo } from '../types';
import './reference-match.css';

export default function ReferenceMatch({ photo, photos, t }: { photo: Photo; photos: Photo[]; t: Dict }) {
  const [reference, setReference] = useState('');
  const [strength, setStrength] = useState(1);
  const [batch, setBatch] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<ReferenceMatchResult | null>(null);
  const current = useRef(photo.id);
  current.current = photo.id;
  useEffect(() => { setResult(null); setError(''); }, [photo.id]);
  const candidates = photos.filter(p => !p.video_id);
  const targets = batch ? candidates.filter(p => p.id !== reference).slice(0, 20).map(p => p.id) : [photo.id];
  const run = async () => {
    const startedFor = photo.id;
    setBusy(true); setError(''); setResult(null);
    try {
      const out = await api.matchReference(reference, targets, strength);
      if (current.current === startedFor) setResult(out);
    } catch (e) { if (current.current === startedFor) setError(errorText(e)); }
    finally { setBusy(false); }
  };
  return <section className="side-section reference-match">
    <div className="side-label">{t.match_title}</div>
    <label>{t.match_reference}<select className="input" value={reference} disabled={busy} onChange={e => { setReference(e.target.value); setResult(null); }}>
      <option value="">{t.match_choose}</option>
      {candidates.map(p => <option key={p.id} value={p.id}>{fileName(p.path)}</option>)}
    </select></label>
    <button className="btn btn-block" disabled={busy} onClick={() => { setReference(photo.id); setResult(null); }}>{t.match_use_this}</button>
    {reference && <img className="craft-result-preview" src={`/photos/api/photos/${reference}/preview?size=256`} alt={t.match_reference} />}
    <label className="craft-exposure">{t.match_strength} · {Math.round(strength * 100)}%<input type="range" min="0" max="1" step="0.05" value={strength} disabled={busy} onChange={e => setStrength(Number(e.target.value))} /></label>
    <label className="reference-match__batch"><input type="checkbox" checked={batch} disabled={busy} onChange={e => { setBatch(e.target.checked); setResult(null); }} /> {t.match_batch}</label>
    <p className="muted small">{t.match_note}</p>
    <button className="btn btn-block" disabled={busy || !reference || !targets.length || (!batch && reference === photo.id)} onClick={() => void run()}>{busy ? t.craft_working : `${t.match_create} (${targets.length})`}</button>
    {error && <p className="error-text small" role="alert">{error}</p>}
    {result && <div className="craft-result" role="status">
      {result.photos.map(p => <div key={p.n}><p className="muted small">{fileName(p.path)}</p><img className="craft-result-preview" src={p.output_url} alt={t.match_result} /><a className="link-btn" href={p.output_url} target="_blank" rel="noreferrer">{t.craft_view_export}</a></div>)}
      {!!result.omitted.length && <p className="error-text small">{t.match_omitted}: {result.omitted.map(x => x.reason).join('; ')}</p>}
      <a className="link-btn" href={result.manifest_url} target="_blank" rel="noreferrer">{t.match_parameters}</a>
    </div>}
  </section>;
}
