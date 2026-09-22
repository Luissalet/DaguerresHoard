import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Bot,
  Brain,
  Cpu,
  Download,
  Eye,
  MapPin,
  MessageSquareText,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";
import { api, errorText, formatBytes } from "../api";
import type { Dict } from "../i18n";
import type { BackendConfigInput, BackendStatus, LibraryStatus, ModelStatus, Root } from "../types";

interface Props {
  t: Dict;
  status: LibraryStatus | null;
  onChanged: () => void;
}

function BackendPanel({ t }: { t: Dict }) {
  const [backend, setBackend] = useState<BackendStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [faustusUrl, setFaustusUrl] = useState("");
  const [faustusToken, setFaustusToken] = useState("");
  const [visionUrl, setVisionUrl] = useState("");
  const [visionModel, setVisionModel] = useState("");
  const [llmUrl, setLlmUrl] = useState("");
  const [llmModel, setLlmModel] = useState("");

  const load = useCallback(() => {
    api
      .getBackend()
      .then(setBackend)
      .catch((e) => setError(errorText(e)));
  }, []);

  useEffect(load, [load]);

  async function recheck() {
    setBusy(true);
    setError(null);
    try {
      setBackend(await api.recheckBackend());
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  async function saveOverrides(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body: BackendConfigInput = {};
      if (faustusUrl) body.faustus_url = faustusUrl;
      if (faustusToken) body.faustus_token = faustusToken;
      if (visionUrl) body.vision_url = visionUrl;
      if (visionModel) body.vision_model = visionModel;
      if (llmUrl) body.llm_url = llmUrl;
      if (llmModel) body.llm_model = llmModel;
      setBackend(await api.setBackendConfig(body));
      setFaustusToken("");
      setFlash(t.saved);
      setTimeout(() => setFlash(null), 2500);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  if (!backend) return null;

  const rows: { key: "vision" | "llm"; label: string; icon: React.ReactNode }[] = [
    { key: "vision", label: t.backend_row_vision, icon: <Eye size={15} /> },
    { key: "llm", label: t.backend_row_llm, icon: <Bot size={15} /> },
  ];

  return (
    <section className="card settings-section">
      <h3>
        <Cpu size={17} /> {t.shared_models}
      </h3>
      <p className="muted small">{t.shared_models_note}</p>
      {error && (
        <div className="notice notice-error">
          <AlertTriangle size={18} />
          <div>{error}</div>
        </div>
      )}
      {flash && <div className="notice notice-ok">{flash}</div>}
      {rows.map((row) => {
        const res = backend[row.key];
        return (
          <div className="meta-row" key={row.key}>
            <span className="k">
              {row.icon} {row.label}
            </span>
            <span className="v">
              <span className={`badge ${res.state === "resolved" ? "badge-ok" : "badge-warn"}`}>
                {res.state === "resolved" ? t.backend_resolved : t.backend_unavailable}
              </span>
              {res.model ? ` · ${res.model}` : ""}
            </span>
          </div>
        );
      })}
      {rows.map((row) => (
        <p className="muted small" key={`${row.key}-reason`}>
          {backend[row.key].reason}
        </p>
      ))}
      <button className="btn btn-sm" disabled={busy} onClick={recheck}>
        <RefreshCw size={13} /> {t.backend_recheck}
      </button>

      <form className="form-grid" onSubmit={saveOverrides}>
        <label className="field">
          <span>{t.backend_faustus_url}</span>
          <input
            className="input"
            placeholder="http://127.0.0.1:7000"
            value={faustusUrl}
            onChange={(e) => setFaustusUrl(e.target.value)}
          />
        </label>
        <label className="field">
          <span>
            {t.backend_faustus_token} {backend.token_set && <span className="badge badge-ok">{t.backend_token_set}</span>}
          </span>
          <input
            className="input"
            type="password"
            placeholder={t.backend_token_placeholder}
            value={faustusToken}
            onChange={(e) => setFaustusToken(e.target.value)}
          />
        </label>
        <label className="field">
          <span>
            {t.backend_row_vision} {t.backend_override_url}
          </span>
          <input className="input" placeholder={backend.vision.url ?? ""} value={visionUrl} onChange={(e) => setVisionUrl(e.target.value)} />
        </label>
        <label className="field">
          <span>
            {t.backend_row_vision} {t.backend_override_model}
          </span>
          <input
            className="input"
            placeholder={backend.vision.model ?? ""}
            value={visionModel}
            onChange={(e) => setVisionModel(e.target.value)}
          />
        </label>
        <label className="field">
          <span>
            {t.backend_row_llm} {t.backend_override_url}
          </span>
          <input className="input" placeholder={backend.llm.url ?? ""} value={llmUrl} onChange={(e) => setLlmUrl(e.target.value)} />
        </label>
        <label className="field">
          <span>
            {t.backend_row_llm} {t.backend_override_model}
          </span>
          <input className="input" placeholder={backend.llm.model ?? ""} value={llmModel} onChange={(e) => setLlmModel(e.target.value)} />
        </label>
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {t.backend_save_overrides}
        </button>
      </form>
    </section>
  );
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
  const [translateSearch, setTranslateSearch] = useState<boolean | null>(null);

  useEffect(() => {
    if (status && !ollamaUrl && !ollamaModel) {
      setOllamaUrl(status.ollama.base_url);
      setOllamaModel(status.ollama.model);
    }
  }, [status, ollamaUrl, ollamaModel]);

  useEffect(() => {
    api
      .getSettings()
      .then((s) => setTranslateSearch(s.translate_search))
      .catch(() => {});
  }, []);

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

      <BackendPanel t={t} />

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
        {translateSearch !== null && (
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={translateSearch}
              onChange={(e) => {
                const next = e.target.checked;
                setTranslateSearch(next);
                act(() => api.setSettings({ translate_search: next }));
              }}
            />
            {t.translate_search_label}
          </label>
        )}
      </section>
    </div>
  );
}
