import { useEffect, useState } from "react";
import { ArrowLeft, Bot, FolderOpen, Plus, Trash2, X } from "lucide-react";
import { api, errorText } from "../api";
import Lightbox from "../components/Lightbox";
import PhotoGrid from "../components/PhotoGrid";
import type { Dict } from "../i18n";
import type { Album } from "../types";

interface Props {
  t: Dict;
  platformIsWindows: boolean;
}

export default function AlbumsPage({ t, platformIsWindows }: Props) {
  const [albums, setAlbums] = useState<Album[]>([]);
  const [openAlbum, setOpenAlbum] = useState<Album | null>(null);
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  // A6 (live report): the album view had only "Delete album" -- a single
  // photo could not be removed, though the endpoint and the skill both
  // say the owner can.
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmRemove, setConfirmRemove] = useState(false);

  function refresh() {
    api
      .listAlbums()
      .then(setAlbums)
      .catch((e) => setError(errorText(e)));
  }

  useEffect(refresh, []);

  async function openDetail(album: Album) {
    try {
      setOpenAlbum(await api.getAlbum(album.id));
      setConfirmDelete(false);
      setSelecting(false);
      setSelected(new Set());
      setConfirmRemove(false);
    } catch (e) {
      setError(errorText(e));
    }
  }

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function removeSelected() {
    if (!openAlbum || selected.size === 0) return;
    try {
      const updated = await api.albumRemove(openAlbum.id, [...selected]);
      setOpenAlbum(updated);
      setSelected(new Set());
      setConfirmRemove(false);
      setSelecting(false);
      refresh();
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function createAlbum(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    try {
      await api.albumAdd(newName.trim(), []);
      setNewName("");
      refresh();
    } catch (err) {
      setError(errorText(err));
    }
  }

  async function deleteAlbum(album: Album) {
    try {
      await api.deleteAlbum(album.id);
      setOpenAlbum(null);
      refresh();
    } catch (err) {
      setError(errorText(err));
    }
  }

  if (openAlbum) {
    const photos = openAlbum.photos ?? [];
    return (
      <div>
        <div className="toolbar">
          <button className="btn" onClick={() => setOpenAlbum(null)}>
            <ArrowLeft size={14} /> {t.nav_albums}
          </button>
          <h2 className="section-title">{openAlbum.name}</h2>
          <span className="muted">{t.photos_count(photos.length)}</span>
          {selecting && selected.size > 0 && <span className="muted">· {t.selected} {selected.size}</span>}
          <span className="spacer" />
          {confirmRemove ? (
            <span className="confirm-inline">
              {t.confirm_remove_from_album(selected.size)}
              <button onClick={removeSelected}>{t.yes_remove}</button>
              <button onClick={() => setConfirmRemove(false)}>{t.cancel}</button>
            </span>
          ) : confirmDelete ? (
            <span className="confirm-inline">
              {t.confirm_delete_album}
              <button onClick={() => deleteAlbum(openAlbum)}>{t.yes_delete}</button>
              <button onClick={() => setConfirmDelete(false)}>{t.cancel}</button>
            </span>
          ) : (
            <>
              {selecting && selected.size > 0 && (
                <button className="btn btn-danger" onClick={() => setConfirmRemove(true)}>
                  <X size={14} /> {t.remove_selected(selected.size)}
                </button>
              )}
              <button
                className="btn"
                onClick={() => {
                  setSelecting((v) => !v);
                  setSelected(new Set());
                }}
              >
                {selecting ? t.cancel : t.select_photos}
              </button>
              {!selecting && (
                <button className="btn btn-danger" onClick={() => setConfirmDelete(true)}>
                  <Trash2 size={14} /> {t.delete_album}
                </button>
              )}
            </>
          )}
        </div>
        {photos.length === 0 ? (
          <p className="muted">{t.no_results}</p>
        ) : (
          <PhotoGrid
            photos={photos}
            onOpen={setOpenIndex}
            selectable={selecting}
            selectedIds={selected}
            onToggleSelect={toggleSelect}
          />
        )}
        {openIndex !== null && photos.length > 0 && (
          <Lightbox
            photos={photos}
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

  return (
    <div>
      <form className="toolbar" onSubmit={createAlbum}>
        <input
          className="input"
          style={{ maxWidth: 280 }}
          placeholder={t.album_name_placeholder}
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
        />
        <button className="btn btn-primary" type="submit" disabled={!newName.trim()}>
          <Plus size={14} /> {t.create}
        </button>
      </form>
      {error && <p className="error-text">{error}</p>}

      {albums.length === 0 ? (
        <div className="empty-state">
          <FolderOpen size={40} />
          <h3>{t.albums_empty}</h3>
        </div>
      ) : (
        <div className="album-grid">
          {albums.map((a) => (
            <button key={a.id} className="album-card" onClick={() => openDetail(a)}>
              <div className="album-cover">
                {a.cover_thumbnail_url ? <img src={a.cover_thumbnail_url} alt="" /> : <FolderOpen size={28} />}
              </div>
              <div className="album-info">
                <strong>{a.name}</strong>
                <span className="muted small">
                  {t.photos_count(a.photo_count)}
                  {a.created_by === "agent" && (
                    <>
                      {" · "}
                      <Bot size={12} /> {t.by_assistant}
                    </>
                  )}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
