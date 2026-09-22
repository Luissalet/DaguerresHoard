import { useState } from "react";
import { AlertTriangle, Search as SearchIcon } from "lucide-react";
import { api, errorText } from "../api";
import Lightbox from "../components/Lightbox";
import PhotoGrid from "../components/PhotoGrid";
import type { Dict } from "../i18n";
import type { Photo, SearchResult } from "../types";

interface Props {
  t: Dict;
  platformIsWindows: boolean;
  onOpenSettings: () => void;
}

export default function SearchPage({ t, platformIsWindows, onOpenSettings }: Props) {
  const [query, setQuery] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [place, setPlace] = useState("");
  const [folder, setFolder] = useState("");
  const [camera, setCamera] = useState("");
  const [orientation, setOrientation] = useState("");
  const [result, setResult] = useState<SearchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  async function runSearch(e?: React.FormEvent) {
    e?.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const filters: Record<string, unknown> = {};
      if (from) filters.taken_after = from;
      if (to) filters.taken_before = to;
      if (place.trim()) filters.place = place.trim();
      if (folder.trim()) filters.folder = folder.trim();
      if (camera.trim()) filters.camera = camera.trim();
      if (orientation) filters.orientation = orientation;
      setResult(await api.search(query.trim(), filters, 50));
    } catch (err) {
      setError(errorText(err));
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  const results: Photo[] = result?.results ?? [];

  return (
    <div>
      <form className="search-bar" onSubmit={runSearch}>
        <div className="search-input-wrap">
          <SearchIcon size={17} className="search-input-icon" />
          <input
            className="input"
            placeholder={t.search_placeholder}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
        </div>
        <button className="btn btn-primary btn-lg" type="submit" disabled={loading || !query.trim()}>
          {t.search_button}
        </button>
      </form>
      <div className="filters-panel">
        <label className="field">
          <span>{t.filter_from}</span>
          <input className="input" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </label>
        <label className="field">
          <span>{t.filter_to}</span>
          <input className="input" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </label>
        <label className="field">
          <span>{t.filter_place}</span>
          <input className="input" value={place} onChange={(e) => setPlace(e.target.value)} />
        </label>
        <label className="field">
          <span>{t.filter_folder}</span>
          <input className="input" value={folder} onChange={(e) => setFolder(e.target.value)} />
        </label>
        <label className="field">
          <span>{t.filter_camera}</span>
          <input className="input" value={camera} onChange={(e) => setCamera(e.target.value)} />
        </label>
        <label className="field">
          <span>{t.filter_orientation}</span>
          <select className="input" value={orientation} onChange={(e) => setOrientation(e.target.value)}>
            <option value="">{t.orientation_any}</option>
            <option value="landscape">{t.orientation_landscape}</option>
            <option value="portrait">{t.orientation_portrait}</option>
          </select>
        </label>
      </div>

      {result?.translated_query && (
        <p className="muted small search-translated-note">{t.searched_for(result.translated_query)}</p>
      )}
      {!result?.translated_query && result?.translate_error && (
        <p className="muted small search-translated-note" title={result.translate_error}>
          {t.not_translated}
        </p>
      )}
      {result?.note && (
        <div className="notice notice-warn">
          <AlertTriangle size={18} />
          <div>
            <strong>{t.fallback_title}</strong>
            <p>{t.fallback_body}</p>
          </div>
          <button className="btn" onClick={onOpenSettings}>
            {t.open_settings}
          </button>
        </div>
      )}
      {error && <p className="error-text">{error}</p>}

      {result === null && !loading && !error && (
        <div className="empty-state">
          <SearchIcon size={40} />
          <h3>{t.empty_search_title}</h3>
          <p>{t.empty_search_body}</p>
        </div>
      )}
      {loading && <p className="muted">{t.loading}</p>}
      {result !== null && !loading && results.length === 0 && <p className="muted">{t.no_results}</p>}
      {results.length > 0 && !loading && (
        <>
          <p className="muted result-count">
            {t.photos_count(results.length)}
            {result?.has_more ? ` / ${result.count}` : ""}
          </p>
          <PhotoGrid photos={results} onOpen={setOpenIndex} />
        </>
      )}
      {openIndex !== null && results.length > 0 && (
        <Lightbox
          photos={results}
          index={openIndex}
          onClose={() => setOpenIndex(null)}
          onIndexChange={setOpenIndex}
          t={t}
          platformIsWindows={platformIsWindows}
        />
      )}
    </div>
  );
}
