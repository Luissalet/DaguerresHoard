import { useEffect, useState } from "react";
import { Download, Plus, RefreshCw, Trash2 } from "lucide-react";
import { api } from "../api";
import type { Dict } from "../i18n";
import type { LibraryStatus, Root } from "../types";

interface Props {
  t: Dict;
  onLibraryChanged: () => void;
}

export default function SettingsPage({ t, onLibraryChanged }: Props) {
  const [status, setStatus] = useState<LibraryStatus | null>(null);
  const [newPath, setNewPath] = useState("");
  const [adding, setAdding] = useState(false);
  const [scanningRoot, setScanningRoot] = useState<number | null>(null);
  const [confirmRemove, setConfirmRemove] = useState<number | null>(null);
  const [ollamaUrl, setOllamaUrl] = useState("");
  const [ollamaModel, setOllamaModel] = useState("");
  const [ollamaTest, setOllamaTest] = useState<string | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);
  const [geoDownloading, setGeoDownloading] = useState(false);

  function refresh() {
    api.libraryStatus().then((s) => {
      setStatus(s);
      setOllamaUrl(s.ollama.base_url);
      setOllamaModel(s.ollama.model);
    });
  }

  useEffect(refresh, []);

  useEffect(() => {
    const running = status?.recent_jobs.some((j) => j.status === "running");
    if (!running) return;
    const interval = setInterval(refresh, 1000);
    return () => clearInterval(interval);
  }, [status]);

  async function addFolder(e: React.FormEvent) {
    e.preventDefault();
    if (!newPath.trim()) return;
    setAdding(true);
    try {
      const root = await api.addRoot(newPath.trim());
      await api.startScan(root.id);
      setNewPath("");
      refresh();
      onLibraryChanged();
    } finally {
      setAdding(false);
    }
  }

  async function scanRoot(root: Root) {
    setScanningRoot(root.id);
    try {
      await api.startScan(root.id);
      refresh();
      onLibraryChanged();
    } finally {
      setScanningRoot(null);
    }
  }

  async function removeRoot(root: Root) {
    await api.removeRoot(root.id);
    setConfirmRemove(null);
    refresh();
    onLibraryChanged();
  }

  async function saveOllama() {
    await api.setSettings({ ollama_base_url: ollamaUrl, ollama_model: ollamaModel });
    setSavedFlash(true);
    setTimeout(() => setSavedFlash(false), 1500);
  }

  async function testOllama() {
    setOllamaTest(null);
    const r = await api.testOllama();
    setOllamaTest(r.ok ? "ok" : r.error ?? "error");
  }

  async function downloadGeo() {
    setGeoDownloading(true);
    try {
      const { job_id } = await api.downloadGeocoder();
      const poll = setInterval(async () => {
        const job = await api.getJob(job_id);
        if (job.status !== "running") {
          clearInterval(poll);
          setGeoDownloading(false);
          refresh();
        }
      }, 800);
    } catch {
      setGeoDownloading(false);
    }
  }

  if (!status) return <p style={{ color: "var(--text-muted)" }}>{t.loading}</p>;

  return (
    <div>
      <div className="card settings-section">
        <h3>{t.roots}</h3>
        {status.roots.map((r) => {
          const runningJob = status.recent_jobs.find((j) => j.status === "running");
          return (
            <div className="root-row" key={r.id}>
              <div>
                <div className="path">{r.path}</div>
                <div style={{ color: "var(--text-muted)", fontSize: 12 }}>{t.photos_count(r.photo_count)}</div>
              </div>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <button className="btn" onClick={() => scanRoot(r)} disabled={scanningRoot === r.id}>
                  <RefreshCw size={13} /> {t.scan_now}
                </button>
                {confirmRemove === r.id ? (
                  <span className="confirm-inline">
                    {t.confirm_remove}
                    <button onClick={() => removeRoot(r)}>{t.yes_remove}</button>
                    <button onClick={() => setConfirmRemove(null)}>{t.cancel}</button>
                  </span>
                ) : (
                  <button className="btn btn-danger" onClick={() => setConfirmRemove(r.id)}>
                    <Trash2 size={13} /> {t.remove}
                  </button>
                )}
              </div>
              {runningJob && (
                <div className="progress-bar" style={{ flexBasis: "100%" }}>
                  <div style={{ width: `${Math.round(runningJob.progress * 100)}%` }} />
                </div>
              )}
            </div>
          );
        })}
        <form className="toolbar" style={{ marginTop: 14 }} onSubmit={addFolder}>
          <input
            className="input"
            placeholder={t.folder_path_placeholder}
            value={newPath}
            onChange={(e) => setNewPath(e.target.value)}
          />
          <button className="btn btn-primary" type="submit" disabled={adding}>
            <Plus size={14} /> {t.add}
          </button>
        </form>
      </div>

      <div className="card settings-section">
        <h3>{t.model_status}</h3>
        <p style={{ fontSize: 13.5 }}>
          {status.embedder.name} ({status.embedder.dim}-d)
        </p>
      </div>

      <div className="card settings-section">
        <h3>{t.geocoder_status}</h3>
        <p style={{ fontSize: 13.5 }}>{status.geocoder_source}</p>
        <button className="btn" onClick={downloadGeo} disabled={geoDownloading}>
          <Download size={14} /> {geoDownloading ? t.scanning : t.download_geonames}
        </button>
      </div>

      <div className="card settings-section">
        <h3>{t.ollama_model}</h3>
        <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 380 }}>
          <label>
            {t.ollama_url}
            <input className="input" value={ollamaUrl} onChange={(e) => setOllamaUrl(e.target.value)} />
          </label>
          <label>
            {t.ollama_model}
            <input className="input" value={ollamaModel} onChange={(e) => setOllamaModel(e.target.value)} />
          </label>
          <div className="toolbar">
            <button className="btn btn-primary" onClick={saveOllama}>
              {savedFlash ? t.saved : t.save}
            </button>
            <button className="btn" onClick={testOllama}>
              {t.test_connection}
            </button>
            {ollamaTest && (
              <span className={`badge ${ollamaTest === "ok" ? "badge-ok" : "badge-fail"}`}>
                {ollamaTest === "ok" ? t.connection_ok : `${t.connection_failed}: ${ollamaTest}`}
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
