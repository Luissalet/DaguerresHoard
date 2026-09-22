import { useEffect, useState } from "react";
import { AlertTriangle, Brain, Download, MapPin, MessageSquareText, Plus, RefreshCw, Trash2 } from "lucide-react";
import { api, errorText, formatBytes } from "../api";
import type { Dict } from "../i18n";
import type { LibraryStatus, ModelStatus, Root } from "../types";

interface Props {
  t: Dict;
  status: LibraryStatus | null;
  onChanged: () => void;
}

function parseGlobs(text: string): string[] {
  return text
    .split(/[,\n]/)
    .map((g) => g.trim())
    .filter(Boolean);
}

export default function SettingsPage({ t, status, onChanged }: Props) {
  const [model, setModel] = useState<ModelStatus | null>(null);
  const [newPath, setNewPath] = useState("");
  const [newGlobs, setNewGlobs] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmRemove, setConfirmRemove] = useState<number | null>(null);
  const [editing, setEditing] = useState<{ id: number; text: string } | null>(null);
  const [ollamaUrl, setOllamaUrl] = useState("");
  const [ollamaModel, setOllamaModel] = useState("");
  const [ollamaMsg, setOllamaMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  useEffect(() => {
    if (status && !ollamaUrl && !ollamaModel) {
      setOllamaUrl(status.ollama.base_url);
      setOllamaModel(status.ollama.model);
    }
  }, [status, ollamaUrl, ollamaModel]);

  const running = status?.recent_jobs.find((j) => j.status === "running");
  const lastIndex = status?.recent_jobs.find((j) => j.kind === "index" && j.status !== "running");

  useEffect(() => {
    api
      .modelStatus()
      .then(setModel)
      .catch(() => {});
  }, [running?.id, status?.embedder.name]);

  // keep polling while a job we care about runs (App polls the status too)
  useEffect(() => {
    if (!running) return;
    const id = setInterval(onChanged, 1500);
    return () => clearInterval(id);
  }, [running, onChanged]);

  async function act(fn: () => Promise<unknown>, done?: string) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      if (done) {
        setFlash(done);
        setTimeout(() => setFlash(null), 2500);
      }
      onChanged();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  function addFolder(e: React.FormEvent) {
    e.preventDefault();
    if (!newPath.trim()) return;
    act(async () => {
      const root = await api.addRoot(newPath.trim(), parseGlobs(newGlobs));
      await api.startScan(root.id);
      setNewPath("");
      setNewGlobs("");
    }, t.job_started);
  }

  function saveGlobs(root: Root) {
    if (!editing) return;
    act(async () => {
      await api.updateRoot(root.id, parseGlobs(editing.text));
      setEditing(null);
    });
  }

  if (!status) return <p className="muted">{t.loading}</p>;

  return (
    <div className="settings">
      {error && (
        <div className="notice notice-error">
          <AlertTriangle size={18} />
          <div>{error}</div>
        </div>
      )}
      {flash && <div className="notice notice-ok">{flash}</div>}

      <section className="card settings-section">
        <h3>{t.roots}</h3>
        {status.roots.length === 0 && <p className="muted">{t.empty_library_body}</p>}
        {status.roots.map((r) => (
          <div className="root-row" key={r.id}>
            <div className="root-main">
              <div className="path">{r.path}</div>
              <div className="muted small">
                {t.photos_count(r.photo_count)}
                {!r.exists && <span className="badge badge-fail">{t.folder_unreachable}</span>}
                {r.added_by === "agent" && <> · {t.by_assistant}</>}
              </div>
              {editing?.id === r.id ? (
                <div className="inline-form">
                  <input
                    className="input"
                    value={editing.text}
                    placeholder={t.excluded_placeholder}
                    onChange={(e) => setEditing({ id: r.id, text: e.target.value })}
                  />
                  <button className="btn btn-sm" onClick={() => saveGlobs(r)}>
                    {t.save}
                  </button>
                  <button className="btn btn-sm" onClick={() => setEditing(null)}>
                    {t.cancel}
                  </button>
                </div>
              ) : (
                <div className="muted small">
                  {t.excluded_globs}: {r.excluded_globs.length ? r.excluded_globs.join(", ") : "–"}{" "}
                  <button className="link-btn" onClick={() => setEditing({ id: r.id, text: r.excluded_globs.join(", ") })}>
                    {t.edit}
                  </button>
                </div>
              )}
            </div>
            <div className="root-actions">
              <button className="btn btn-sm" onClick={() => act(() => api.startScan(r.id), t.job_started)} disabled={busy}>
                <RefreshCw size={13} /> {t.scan_now}
              </button>
              {confirmRemove === r.id ? (
                <span className="confirm-inline">
                  {t.confirm_remove}
                  <button onClick={() => act(() => api.removeRoot(r.id)).then(() => setConfirmRemove(null))}>
                    {t.yes_remove}
                  </button>
                  <button onClick={() => setConfirmRemove(null)}>{t.cancel}</button>
                </span>
              ) : (
                <button className="btn btn-sm btn-danger" onClick={() => setConfirmRemove(r.id)}>
                  <Trash2 size={13} /> {t.remove}
                </button>
              )}
            </div>
          </div>
        ))}
        {running && (
          <div className="job-progress">
            <div className="progress-bar">
              <div style={{ width: `${Math.round(running.progress * 100)}%` }} />
            </div>
            <span className="muted small">{running.message}</span>
          </div>
        )}
        {!running && lastIndex?.stats?.errors ? (
          <details className="muted small job-errors">
            <summary>{t.job_errors(lastIndex.stats.errors)}</summary>
            <ul>
              {(lastIndex.stats.error_samples ?? []).map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </details>
        ) : null}
        {!status.heic_support && <p className="muted small">{t.heic_missing}</p>}
        <form className="add-root-form" onSubmit={addFolder}>
          <input
            className="input"
            placeholder={t.folder_path_placeholder}
            value={newPath}
            onChange={(e) => setNewPath(e.target.value)}
          />
          <input
            className="input"
            placeholder={`${t.excluded_globs} (${t.excluded_placeholder})`}
            value={newGlobs}
            onChange={(e) => setNewGlobs(e.target.value)}
          />
          <button className="btn btn-primary" type="submit" disabled={busy || !newPath.trim()}>
            <Plus size={14} /> {t.add}
          </button>
        </form>
      </section>

      <section className="card settings-section">
        <h3>
          <Brain size={17} /> {t.model_status}
        </h3>
        <div className="meta-row">
          <span className="k">{t.model_active}</span>
          <span className="v">
            <span className={`badge ${status.embedder.semantic ? "badge-ok" : "badge-warn"}`}>
              {status.embedder.semantic ? t.model_semantic : t.model_fallback}
            </span>
          </span>
        </div>
        {status.embedder.stale_photos > 0 && !running && (
          <p className="muted small">{t.stale_photos(status.embedder.stale_photos)}</p>
        )}
        {model?.clip_downloaded ? (
          <p className="muted small">{t.model_downloaded(formatBytes(model.cache_bytes))}</p>
        ) : (
          <>
            <p className="muted small">{t.model_note}</p>
            <button
              className="btn btn-primary"
              disabled={busy || !!model?.downloading}
              onClick={() => act(() => api.downloadModel(), t.job_started)}
            >
              <Download size={14} /> {model?.downloading ? t.model_downloading : t.model_download}
            </button>
          </>
        )}
      </section>

      <section className="card settings-section">
        <h3>
          <MapPin size={17} /> {t.geocoder_status}
        </h3>
        <div className="meta-row">
          <span className="k">{t.geocoder_status}</span>
          <span className="v">
            {status.geocoder_source === "geonames-cities1000" ? t.geocoder_full : t.geocoder_bundled}
          </span>
        </div>
        {status.geocoder_source !== "geonames-cities1000" && (
          <>
            <p className="muted small">{t.geocoder_note}</p>
            <button className="btn" disabled={busy} onClick={() => act(() => api.downloadGeocoder(), t.job_started)}>
              <Download size={14} /> {t.download_geonames}
            </button>
          </>
        )}
      </section>

      <section className="card settings-section">
        <h3>
          <MessageSquareText size={17} /> {t.ollama_model}
        </h3>
        <div className="form-grid">
          <label className="field">
            <span>{t.ollama_url}</span>
            <input className="input" value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} />
          </label>
          <label className="field">
            <span>{t.ollama_model}</span>
            <input className="input" value={ollamaModel} onChange={(e) => setOllamaModel(e.target.value)} />
          </label>
        </div>
        <div className="toolbar">
          <button
            className="btn btn-primary"
            disabled={busy}
            onClick={() => act(() => api.setSettings({ ollama_base_url: ollamaUrl, ollama_model: ollamaModel }), t.saved)}
          >
            {t.save}
          </button>
          <button
            className="btn"
            onClick={async () => {
              setOllamaMsg(null);
              try {
                const r = await api.testOllama();
                setOllamaMsg({ ok: r.ok, text: r.ok ? t.connection_ok : `${t.connection_failed}: ${r.error ?? ""}` });
              } catch (e) {
                setOllamaMsg({ ok: false, text: errorText(e) });
              }
            }}
          >
            {t.test_connection}
          </button>
          {ollamaMsg && <span className={`badge ${ollamaMsg.ok ? "badge-ok" : "badge-fail"}`}>{ollamaMsg.text}</span>}
        </div>
        <p className="muted small">{t.captions_note}</p>
        <button className="btn" disabled={busy || !!running} onClick={() => act(() => api.captionBatch(), t.job_started)}>
          <MessageSquareText size={14} /> {t.captions_batch}
        </button>
      </section>
    </div>
  );
}
