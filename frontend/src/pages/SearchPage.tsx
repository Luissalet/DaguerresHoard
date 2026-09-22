import { useState } from "react";
import { Search as SearchIcon } from "lucide-react";
import { api } from "../api";
import Lightbox from "../components/Lightbox";
import PhotoGrid from "../components/PhotoGrid";
import type { Dict } from "../i18n";
import type { Photo } from "../types";

interface Props {
  t: Dict;
  platformIsWindows: boolean;
}

export default function SearchPage({ t, platformIsWindows }: Props) {
  const [query, setQuery] = useState("");
  const [year, setYear] = useState("");
  const [place, setPlace] = useState("");
  const [folder, setFolder] = useState("");
  const [camera, setCamera] = useState("");
  const [orientation, setOrientation] = useState("");
  const [results, setResults] = useState<Photo[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  async function runSearch(e?: React.FormEvent) {
    e?.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    try {
      const filters: Record<string, unknown> = {};
      if (year) filters.year = Number(year);
      if (place) filters.place = place;
      if (folder) filters.folder = folder;
      if (camera) filters.camera = camera;
      if (orientation) filters.orientation = orientation;
      const r = await api.search(query, filters, 60);
      setResults(r.results);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <form className="search-bar" onSubmit={runSearch}>
        <input
          className="input"
          placeholder={t.search_placeholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button className="btn btn-primary" type="submit" disabled={loading}>
          <SearchIcon size={15} /> {t.search_button}
        </button>
      </form>
      <div className="filters-panel">
        <input className="input" placeholder={t.filter_year} value={year} onChange={(e) => setYear(e.target.value)} />
        <input
          className="input"
          placeholder={t.filter_place}
          value={place}
          onChange={(e) => setPlace(e.target.value)}
        />
        <input
          className="input"
          placeholder={t.filter_folder}
          value={folder}
          onChange={(e) => setFolder(e.target.value)}
        />
        <input
          className="input"
          placeholder={t.filter_camera}
          value={camera}
          onChange={(e) => setCamera(e.target.value)}
        />
        <select className="input" value={orientation} onChange={(e) => setOrientation(e.target.value)}>
          <option value="">{t.orientation_any}</option>
          <option value="landscape">{t.orientation_landscape}</option>
          <option value="portrait">{t.orientation_portrait}</option>
        </select>
      </div>

      {results === null && !loading && (
        <div className="empty-state">
          <SearchIcon size={40} />
          <h3>{t.empty_search_title}</h3>
          <p>{t.empty_search_body}</p>
        </div>
      )}
      {loading && <p style={{ color: "var(--text-muted)" }}>{t.loading}</p>}
      {results !== null && !loading && results.length === 0 && <p>{t.no_results}</p>}
      {results !== null && results.length > 0 && (
        <>
          <p style={{ color: "var(--text-muted)", marginTop: 0 }}>{t.photos_count(results.length)}</p>
          <PhotoGrid photos={results} onOpen={setOpenIndex} />
        </>
      )}
      {results && openIndex !== null && (
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
