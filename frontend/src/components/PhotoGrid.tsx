import { fileName } from "../api";
import type { Photo } from "../types";

interface Props {
  photos: Photo[];
  onOpen: (index: number) => void;
}

export default function PhotoGrid({ photos, onOpen }: Props) {
  return (
    <div className="grid">
      {photos.map((p, i) => (
        <button key={p.id} className="thumb" onClick={() => onOpen(i)} title={fileName(p.path)}>
          <img src={p.thumbnail_url} alt={fileName(p.path)} loading="lazy" decoding="async" />
          <div className="meta">
            <span>{p.taken_at ? p.taken_at.slice(0, 10) : ""}</span>
            {p.place && <span className="meta-place">{p.place}</span>}
          </div>
        </button>
      ))}
    </div>
  );
}
