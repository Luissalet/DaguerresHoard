import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, ExternalLink, Sparkles, X } from "lucide-react";
import { api } from "../api";
import type { Dict } from "../i18n";
import type { Photo, PhotoDetail } from "../types";

interface Props {
  photos: Photo[];
  index: number;
  onClose: () => void;
  onIndexChange: (i: number) => void;
  t: Dict;
  platformIsWindows: boolean;
}

export default function Lightbox({ photos, index, onClose, onIndexChange, t, platformIsWindows }: Props) {
  const photo = photos[index];
  const [detail, setDetail] = useState<PhotoDetail | null>(null);
  const [similar, setSimilar] = useState<Photo[]>([]);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [captioning, setCaptioning] = useState(false);
  const dragState = useRef<{ startX: number; startY: number; panX: number; panY: number } | null>(null);

  useEffect(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setDetail(null);
    setSimilar([]);
    if (!photo) return;
    api.describe(photo.id).then(setDetail).catch(() => {});
    api
      .similar(photo.id, 8)
      .then((r) => setSimilar(r.results.filter((p) => p.id !== photo.id)))
      .catch(() => {});
  }, [photo?.id]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowLeft" && index > 0) onIndexChange(index - 1);
      else if (e.key === "ArrowRight" && index < photos.length - 1) onIndexChange(index + 1);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, photos.length, onClose, onIndexChange]);

  if (!photo) return null;

  function onWheel(e: React.WheelEvent) {
    e.preventDefault();
    setZoom((z) => Math.min(6, Math.max(1, z - e.deltaY * 0.0015 * z)));
  }

  function onMouseDown(e: React.MouseEvent) {
    if (zoom <= 1) return;
    dragState.current = { startX: e.clientX, startY: e.clientY, panX: pan.x, panY: pan.y };
  }
  function onMouseMove(e: React.MouseEvent) {
    if (!dragState.current) return;
    const dx = e.clientX - dragState.current.startX;
    const dy = e.clientY - dragState.current.startY;
    setPan({ x: dragState.current.panX + dx, y: dragState.current.panY + dy });
  }
  function onMouseUp() {
    dragState.current = null;
  }

  async function generateCaption() {
    setCaptioning(true);
    try {
      const updated = await api.describe(photo.id, true);
      setDetail(updated);
    } finally {
      setCaptioning(false);
    }
  }

  return (
    <div className="lightbox-overlay">
      <div
        className="lightbox-image-area"
        onWheel={onWheel}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={onMouseUp}
      >
        <button className="lightbox-close" onClick={onClose} aria-label={t.close}>
          <X size={18} />
        </button>
        {index > 0 && (
          <button
            className="lightbox-nav-btn"
            style={{ left: 16 }}
            onClick={() => onIndexChange(index - 1)}
            aria-label="Previous"
          >
            <ChevronLeft />
          </button>
        )}
        {index < photos.length - 1 && (
          <button
            className="lightbox-nav-btn"
            style={{ right: 16 }}
            onClick={() => onIndexChange(index + 1)}
            aria-label="Next"
          >
            <ChevronRight />
          </button>
        )}
        <img
          src={photo.thumbnail_url}
          alt=""
          draggable={false}
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`, cursor: zoom > 1 ? "grab" : "auto" }}
        />
      </div>
      <div className="lightbox-side">
        <h3 style={{ marginTop: 0 }}>{t.photo_details}</h3>
        <div className="meta-row">
          <span className="k">{t.taken}</span>
          <span className="v">{photo.taken_at?.slice(0, 19).replace("T", " ") ?? "–"}</span>
        </div>
        {photo.place && (
          <div className="meta-row">
            <span className="k">{t.filter_place}</span>
            <span className="v">{photo.place}</span>
          </div>
        )}
        {detail?.model && (
          <div className="meta-row">
            <span className="k">{t.camera}</span>
            <span className="v">
              {detail.make} {detail.model}
            </span>
          </div>
        )}
        {detail?.lens && (
          <div className="meta-row">
            <span className="k">{t.lens}</span>
            <span className="v">{detail.lens}</span>
          </div>
        )}
        {(detail?.f_number || detail?.exposure_time || detail?.iso) && (
          <div className="meta-row">
            <span className="k">{t.exposure}</span>
            <span className="v">
              {detail?.f_number ? `f/${detail.f_number}` : ""} {detail?.exposure_time ?? ""}{" "}
              {detail?.iso ? `ISO${detail.iso}` : ""}
            </span>
          </div>
        )}
        <div className="meta-row">
          <span className="k">{t.path}</span>
          <span className="v" title={photo.path}>
            {photo.path}
          </span>
        </div>

        <div style={{ marginTop: 14 }}>
          <div className="meta-row" style={{ border: "none" }}>
            <span className="k">{t.caption}</span>
          </div>
          {detail?.caption ? (
            <p style={{ fontSize: 13, marginTop: 0 }}>{detail.caption}</p>
          ) : (
            <button className="btn" onClick={generateCaption} disabled={captioning}>
              <Sparkles size={14} /> {captioning ? t.generating : t.generate_caption}
            </button>
          )}
        </div>

        {platformIsWindows && (
          <button className="btn" style={{ marginTop: 14 }} onClick={() => api.openInExplorer(photo.id).catch(() => {})}>
            <ExternalLink size={14} /> {t.open_in_explorer}
          </button>
        )}

        {similar.length > 0 && (
          <div style={{ marginTop: 20 }}>
            <div className="meta-row" style={{ border: "none" }}>
              <span className="k">{t.similar_photos}</span>
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {similar.map((s) => (
                <img
                  key={s.id}
                  src={s.thumbnail_url}
                  alt=""
                  style={{ width: 56, height: 56, objectFit: "cover", borderRadius: 6, cursor: "pointer" }}
                  onClick={() => {
                    const newIndex = photos.findIndex((p) => p.id === s.id);
                    if (newIndex >= 0) onIndexChange(newIndex);
                  }}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
