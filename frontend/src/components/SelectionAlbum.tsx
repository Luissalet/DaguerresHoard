import { useEffect, useId, useRef, useState } from "react";
import { FolderPlus } from "lucide-react";
import { api, errorText, fileName } from "../api";
import type { Album, AlbumAddResult, Photo } from "../types";
import type { Dict } from "../i18n";
import "./selection-album.css";

export default function SelectionAlbum({ photos, t }: { photos: Photo[]; t: Dict }) {
  const [name, setName] = useState("");
  const [albums, setAlbums] = useState<Album[]>([]);
  const [saved, setSaved] = useState<{ receipt: AlbumAddResult; signature: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const listId = useId();
  const request = useRef(0);
  const signature = photos.map(photo => photo.id).join(",");
  const result = saved?.signature === signature ? saved.receipt : null;
  const current = useRef(signature);
  current.current = signature;
  useEffect(() => {
    let active = true;
    api.listAlbums().then(value => { if (active) setAlbums(value); }).catch(failure => { if (active) setError(errorText(failure)); });
    return () => { active = false; request.current++; };
  }, []);
  useEffect(() => { request.current++; setSaved(null); setError(null); setBusy(false); }, [signature]);

  async function add(event: React.FormEvent) {
    event.preventDefault();
    const version = ++request.current;
    const selection = signature;
    setBusy(true); setError(null); setSaved(null);
    try {
      const receipt = await api.albumAdd(name.trim(), photos.map(photo => photo.id));
      if (request.current === version && current.current === selection) {
        setSaved({ receipt, signature: selection });
        setAlbums(previous => [receipt, ...previous.filter(album => album.id !== receipt.id)]);
      }
    } catch (failure) {
      if (request.current === version && current.current === selection) setError(errorText(failure));
    } finally {
      if (request.current === version && current.current === selection) setBusy(false);
    }
  }

  return <section className="selection-album" aria-label={t.album_selection}>
    <h3>{t.album_selection}</h3>
    <p className="muted small">{t.album_selection_note}</p>
    {photos.length ? <details>
      <summary>{t.album_selection_review(photos.length)}</summary>
      <ul className="selection-album__photos">{photos.map(photo => <li key={photo.id}>
        <span>{fileName(photo.path)}</span><small className="muted">{photo.id}</small>
      </li>)}</ul>
    </details> : <p className="muted">{t.album_selection_empty}</p>}
    <form onSubmit={add} className="selection-album__form">
      <label><span>{t.album_name_placeholder}</span><input className="input" list={listId} required
        value={name} onChange={event => setName(event.target.value)} /></label>
      <datalist id={listId}>{albums.map(album => <option key={album.id} value={album.name} />)}</datalist>
      <button className="btn btn-primary" type="submit" disabled={busy || !name.trim() || photos.length === 0}>
        <FolderPlus size={14} /> {busy ? t.album_selection_working : t.add_to_album}
      </button>
    </form>
    {error && <p role="alert" className="error-text">{error}</p>}
    <div aria-live="polite" aria-atomic="true">{result && <div className="selection-album__result">
      <p><strong>{result.name}</strong> · {result.created ? t.album_selection_created : t.album_selection_existing}</p>
      <p>{t.album_selection_result(result.added, result.photo_count)}</p>
      <p className="muted small">ID: {result.id}</p>
      {result.unknown_ids.length > 0 && <p className="error-text">{t.album_selection_unknown}: {result.unknown_ids.join(", ")}</p>}
    </div>}</div>
  </section>;
}
