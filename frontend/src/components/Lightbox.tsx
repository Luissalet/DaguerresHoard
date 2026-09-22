import { useEffect, useRef, useState } from "react";
import { Check, ChevronLeft, ChevronRight, ExternalLink, FolderPlus, Minus, Plus, Sparkles, X } from "lucide-react";
import { api, errorText, fileName, formatBytes } from "../api";
import type { Dict } from "../i18n";
import type { Album, Photo, PhotoDetail } from "../types";

interface Props {
  photos: Photo[];
  index: number;
  onClose: () => void;
  onIndexChange: (i: number) => void;
  t: Dict;
  platformIsWindows: boolean;
}

const MAX_ZOOM = 8;

export default function Lightbox({ photos, index, onClose, onIndexChange, t, platformIsWindows }: Props) {
  // A photo opened from the "Similar" strip may not be in `photos`; show it
  // on its own until the user navigates with the arrows again.
  const [detached, setDetached] = useState<Photo | null>(null);
  const photo = detached ?? photos[index];
  const [detail, setDetail] = useState<PhotoDetail | null>(null);
  const [similar, setSimilar] = useState<Photo[]>([]);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [fullLoaded, setFullLoaded] = useState(false);
  const [fullFailed, setFullFailed] = useState(false);
  const [captioning, setCaptioning] = useState(false);
  const [captionError, setCaptionError] = useState<string | null>(null);
  const [albums, setAlbums] = useState<Album[]>([]);
  const [albumName, setAlbumName] = useState("");
  const [albumMsg, setAlbumMsg] = useState<string | null>(null);
  const drag = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);
  const areaRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    api.listAlbums().then(setAlbums).catch(() => {});
  }, []);

  useEffect(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setDetail(null);
    setSimilar([]);
    setFullLoaded(false);
    setFullFailed(false);
    setCaptionError(null);
    setAlbumMsg(null);
    if (!photo) return;
    api.getPhoto(photo.id).then(setDetail).catch(() => {});
    api
      .similar(photo.id, 12)
      .then((r) => setSimilar(r.results))
      .catch(() => {});
  }, [photo?.id]);

  function go(delta: number) {
    const next = index + delta;
    if (next < 0 || next >= photos.length) return;
    setDetached(null);
    onIndexChange(next);
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement) return;
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowLeft") go(-1);
      else if (e.key === "ArrowRight") go(1);
      else if (e.key === "+" || e.key === "=") setZoom((z) => Math.min(MAX_ZOOM, z * 1.25));
      else if (e.key === "-") setZoom((z) => Math.max(1, z / 1.25));
      else if (e.key === "0") {
        setZoom(1);
        setPan({ x: 0, y: 0 });
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  // Wheel / trackpad-pinch zoom needs a non-passive listener to stop the page scrolling.
  useEffect(() => {
    const el = areaRef.current;
    if (!el) return;
    function onWheel(e: WheelEvent) {
      e.preventDefault();
      setZoom((z) => {
        const next = Math.min(MAX_ZOOM, Math.max(1, z * Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.0015))));
        if (next === 1) setPan({ x: 0, y: 0 });
        return next;
      });
    }
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  if (!photo) return null;

  function onPointerDown(e: React.PointerEvent) {
    if (zoom <= 1) return;
    (e.target as Element).setPointerCapture?.(e.pointerId);
    drag.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y };
  }
  function onPointerMove(e: React.PointerEvent) {
    if (!drag.current) return;
    setPan({ x: drag.current.panX + e.clientX - drag.current.x, y: drag.current.panY + e.clientY - drag.current.y });
  }
  function onPointerUp() {
    drag.current = null;
  }

  async function generateCaption() {
    setCaptioning(true);
    setCaptionError(null);
    try {
      const updated = await api.caption(photo.id);
      setDetail(updated);
      if (updated.caption_error) setCaptionError(updated.caption_error);
    } catch (e) {
      setCaptionError(errorText(e));
    } finally {
      setCaptioning(false);
    }
  }

  async function addToAlbum(e: React.FormEvent) {
    e.preventDefault();
    const name = albumName.trim();
    if (!name) return;
    try {
      const album = await api.albumAdd(name, [photo.id]);
      setAlbumMsg(t.added_to(album.name));
      setAlbumName("");
      api.listAlbums().then(setAlbums).catch(() => {});
    } catch (err) {
      setAlbumMsg(errorText(err));
    }
  }

  const d = detail;
  const exposure = [
    d?.f_number ? `f/${d.f_number}` : null,
    d?.exposure_time ?? null,
    d?.iso ? `ISO ${d.iso}` : null,
    d?.focal_length ? `${d.focal_length} mm` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  const hasPrev = !detached && index > 0;
  const hasNext = !detached && index < photos.length - 1;

  return (
    <div className="lightbox-overlay" role="dialog" aria-modal="true">
      <div
        className={`lightbox-image-area${zoom > 1 ? " zoomed" : ""}`}
        ref={areaRef}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onDoubleClick={() => {
          setZoom((z) => (z > 1 ? 1 : 2.5));
          setPan({ x: 0, y: 0 });
        }}
      >
        <button className="lightbox-close" onClick={onClose} aria-label={t.close}>
          <X size={18} />
        </button>
        {hasPrev && (
          <button className="lightbox-nav-btn left" onClick={() => go(-1)} aria-label="Previous">
            <ChevronLeft />
          </button>
        )}
        {hasNext && (
          <button className="lightbox-nav-btn right" onClick={() => go(1)} aria-label="Next">
            <ChevronRight />
          </button>
        )}
        <div
          className="lightbox-stage"
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
        >
          {!fullLoaded && <img src={photo.thumbnail_url} alt="" draggable={false} className="lightbox-img" />}
          {!fullFailed && (
            <img
              key={photo.id}
              src={api.previewUrl(photo.id)}
              alt={fileName(photo.path)}
              draggable={false}
              className="lightbox-img"
              style={{ display: fullLoaded ? "block" : "none" }}
              onLoad={() => setFullLoaded(true)}
              onError={() => setFullFailed(true)}
            />
          )}
        </div>
        <div className="zoom-controls">
          <button onClick={() => setZoom((z) => Math.max(1, z / 1.25))} aria-label="Zoom out">
            <Minus size={15} />
          </button>
          <span>{Math.round(zoom * 100)}%</span>
          <button onClick={() => setZoom((z) => Math.min(MAX_ZOOM, z * 1.25))} aria-label="Zoom in">
            <Plus size={15} />
          </button>
        </div>
      </div>
      <aside className="lightbox-side">
        <h3 className="lightbox-title" title={photo.path}>
          {fileName(photo.path)}
        </h3>
        {fullFailed && <p className="error-text">{t.missing_file}</p>}
        <div className="meta-row">
          <span className="k">{t.taken}</span>
          <span className="v">
            {photo.taken_at ? `${photo.taken_at.slice(0, 10)} · ${photo.taken_at.slice(11, 16)}` : "–"}
            {d?.date_source === "file_mtime" && <span className="muted small"> ({t.file_date})</span>}
          </span>
        </div>
        {photo.place && (
          <div className="meta-row">
            <span className="k">{t.filter_place}</span>
            <span className="v">{photo.place}</span>
          </div>
        )}
        {(d?.make || d?.model) && (
          <div className="meta-row">
            <span className="k">{t.camera}</span>
            <span className="v">{[d?.make, d?.model].filter(Boolean).join(" ")}</span>
          </div>
        )}
        {d?.lens && (
          <div className="meta-row">
            <span className="k">{t.lens}</span>
            <span className="v">{d.lens}</span>
          </div>
        )}
        {exposure && (
          <div className="meta-row">
            <span className="k">{t.exposure}</span>
            <span className="v">{exposure}</span>
          </div>
        )}
        <div className="meta-row">
          <span className="k">{t.path}</span>
          <span className="v path-value" title={photo.path}>
            {photo.path}
          </span>
        </div>
        <div className="meta-row">
          <span className="k">{photo.width && photo.height ? `${photo.width} × ${photo.height}` : ""}</span>
          <span className="v">{formatBytes(photo.size)}</span>
        </div>

        {platformIsWindows && (
          <button className="btn btn-block" onClick={() => api.openInExplorer(photo.id).catch(() => {})}>
            <ExternalLink size={14} /> {t.open_in_explorer}
          </button>
        )}

        <section className="side-section">
          <div className="side-label">{t.caption}</div>
          {d?.caption ? (
            <p className="caption-text">{d.caption}</p>
          ) : (
            <button className="btn btn-block" onClick={generateCaption} disabled={captioning}>
              <Sparkles size={14} /> {captioning ? t.generating : t.generate_caption}
            </button>
          )}
          {captionError && <p className="error-text small">{captionError}</p>}
        </section>

        <section className="side-section">
          <div className="side-label">{t.add_to_album}</div>
          <form className="inline-form" onSubmit={addToAlbum}>
            <input
              className="input"
              list="argus-albums"
              placeholder={t.album_input_placeholder}
              value={albumName}
              onChange={(e) => setAlbumName(e.target.value)}
            />
            <datalist id="argus-albums">
              {albums.map((a) => (
                <option key={a.id} value={a.name} />
              ))}
            </datalist>
            <button className="btn" type="submit" disabled={!albumName.trim()} aria-label={t.add_to_album}>
              <FolderPlus size={14} />
            </button>
          </form>
          {albumMsg && (
            <p className="muted small">
              <Check size={12} /> {albumMsg}
            </p>
          )}
        </section>

        {similar.length > 0 && (
          <section className="side-section">
            <div className="side-label">{t.similar_photos}</div>
            <div className="similar-strip">
              {similar.map((s) => (
                <button
                  key={s.id}
                  className="similar-thumb"
                  title={fileName(s.path)}
                  onClick={() => {
                    const i = photos.findIndex((p) => p.id === s.id);
                    if (i >= 0) {
                      setDetached(null);
                      onIndexChange(i);
                    } else {
                      setDetached(s);
                    }
                  }}
                >
                  <img src={s.thumbnail_url} alt="" loading="lazy" />
                </button>
              ))}
            </div>
          </section>
        )}
      </aside>
    </div>
  );
}
