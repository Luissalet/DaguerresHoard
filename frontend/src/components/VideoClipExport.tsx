import { useEffect, useRef, useState } from "react";
import { Download, Scissors } from "lucide-react";
import { api, errorText, formatBytes, type VideoClipResult } from "../api";
import { useCopilotForm } from "../copilot-hooks";
import type { Dict } from "../i18n";
import type { VideoDetail } from "../types";
import "./video-clip.css";

interface Props {
  video: VideoDetail;
  t: Dict;
  positionReady: boolean;
  getPosition: () => number | null;
}

const nativeUrl = (url: string) => url.startsWith("/photos/") ? url : `/photos${url}`;

export default function VideoClipExport({ video, t, positionReady, getPosition }: Props) {
  const [start, setStart] = useState("0");
  const [end, setEnd] = useState(video.duration == null ? "" : String(video.duration));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<VideoClipResult | null>(null);
  const [requested, setRequested] = useState<{ start_s: number; end_s: number } | null>(null);
  const owner = useRef(video.id);
  owner.current = video.id;
  const alive = useRef(false);
  const serial = useRef(0);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const valid = start !== "" && end !== "" && Number.isFinite(Number(start)) && Number.isFinite(Number(end))
    && Number(start) >= 0 && Number(end) > Number(start);
  const receipt = result?.video_id === video.id ? result : null;
  useCopilotForm(() => ({ kind: "video-clip-export", object_id: video.id,
    dirty: start !== "0" || end !== (video.duration == null ? "" : String(video.duration)),
    fields: { start_s: start, end_s: end, requested, busy, error,
      export: receipt ? { id: receipt.id, requested: receipt.requested, measured: receipt.measured, video_url: receipt.video_url } : null } }));

  function position(field: "start" | "end") {
    const time = getPosition();
    if (time === null || !Number.isFinite(time)) return;
    if (field === "start") setStart(String(time)); else setEnd(String(time));
  }

  async function submit() {
    if (!valid || busy) return;
    const id = video.id, ticket = ++serial.current;
    const sent = { start_s: Number(start), end_s: Number(end) };
    const current = () => alive.current && owner.current === id && ticket === serial.current;
    setBusy(true); setError(null); setResult(null); setRequested(sent);
    try {
      const answer = await api.exportVideoClip(id, sent.start_s, sent.end_s);
      if (current()) setResult(answer);
    } catch (err) {
      if (current()) setError(errorText(err));
    } finally {
      if (current()) setBusy(false);
    }
  }

  return <section className="video-clip" aria-label={t.clip_title}>
    <h3><Scissors size={16} aria-hidden="true" /> {t.clip_title}</h3>
    <p className="muted small">{t.clip_help}</p>
    <form onSubmit={event => { event.preventDefault(); void submit(); }}>
      <div className="video-clip-fields">
        <div>
          <label>{t.clip_start}<input className="input" type="number" min="0" step="any" required
            value={start} onChange={event => setStart(event.target.value)} /></label>
          <button className="btn btn-sm" type="button" disabled={!positionReady} onClick={() => position("start")}>{t.clip_use_position}</button>
        </div>
        <div>
          <label>{t.clip_end}<input className="input" type="number" min="0" step="any" required
            value={end} onChange={event => setEnd(event.target.value)} /></label>
          <button className="btn btn-sm" type="button" disabled={!positionReady} onClick={() => position("end")}>{t.clip_use_position}</button>
        </div>
      </div>
      <p className="small muted">{valid ? `${t.clip_target}: ${Number(end) - Number(start)} s` : t.clip_interval_help}</p>
      <button className="btn btn-primary" disabled={!valid || busy}>{busy ? t.clip_busy : t.clip_export}</button>
    </form>
    {busy && <p role="status" className="small">{t.clip_pending}</p>}
    {error && <div role="alert"><p className="error-text">{error}</p><button className="btn" disabled={!valid || busy} onClick={() => void submit()}>{t.clip_retry}</button></div>}
    {receipt && <div className="video-clip-receipt" role="status">
      <h4>{receipt.source_name}</h4>
      <p className="small">{t.clip_requested}: {receipt.requested.start_s}–{receipt.requested.end_s} s
        <br />{t.clip_measured}: {receipt.measured.duration_s} s · {receipt.measured.width} × {receipt.measured.height} · {formatBytes(receipt.bytes)}</p>
      <p className="small muted">{t.clip_timing_note}</p>
      <video className="video-player" controls preload="metadata" src={nativeUrl(receipt.video_url)} aria-label={t.clip_preview} />
      <div className="toolbar">
        <a className="btn btn-primary" href={nativeUrl(receipt.video_url)} download={`clip-${receipt.id}.mp4`}><Download size={14} /> {t.clip_download}</a>
        <a className="btn" href={nativeUrl(receipt.manifest_url)} download={`clip-${receipt.id}.json`}>{t.clip_receipt}</a>
      </div>
    </div>}
  </section>;
}
