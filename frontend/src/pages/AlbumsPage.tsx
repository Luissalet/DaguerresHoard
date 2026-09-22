import { useEffect, useState } from "react";
import { FolderOpen, Plus } from "lucide-react";
import { api } from "../api";
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
  const [creating, setCreating] = useState(false);

  function refresh() {
    api.listAlbums().then(setAlbums);
  }

  useEffect(refresh, []);

  async function openDetail(album: Album) {
    const full = await api.getAlbum(album.id);
    setOpenAlbum(full);
  }

  async function createAlbum(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await api.createAlbum(newName.trim(), []);
      setNewName("");
      refresh();
    } finally {
      setCreating(false);
    }
  }

  if (openAlbum) {
    return (
      <div>
        <button className="btn" style={{ marginBottom: 16 }} onClick={() => setOpenAlbum(null)}>
          &larr; {t.nav_albums}
        </button>
        <h2 style={{ marginTop: 0 }}>{openAlbum.name}</h2>
        {(openAlbum.photos?.length ?? 0) === 0 ? (
          <p style={{ color: "var(--text-muted)" }}>{t.no_results}</p>
        ) : (
          <PhotoGrid photos={openAlbum.photos!} onOpen={setOpenIndex} />
        )}
        {openIndex !== null && openAlbum.photos && (
          <Lightbox
            photos={openAlbum.photos}
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
          style={{ maxWidth: 260 }}
          placeholder={t.album_name_placeholder}
          value={newName}
          onChange={(e) => setNewName(e.target.value)}
        />
        <button className="btn btn-primary" type="submit" disabled={creating}>
          <Plus size={14} /> {t.create}
        </button>
      </form>

      {albums.length === 0 ? (
        <div className="empty-state">
          <FolderOpen size={40} />
          <h3>{t.albums_empty}</h3>
        </div>
      ) : (
        <div className="grid">
          {albums.map((a) => (
            <div key={a.id} className="card" style={{ padding: 16, cursor: "pointer" }} onClick={() => openDetail(a)}>
              <FolderOpen size={22} color="var(--accent)" />
              <div style={{ fontWeight: 700, marginTop: 8 }}>{a.name}</div>
              <div style={{ color: "var(--text-muted)", fontSize: 12.5 }}>{t.photos_count(a.photo_count ?? 0)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
