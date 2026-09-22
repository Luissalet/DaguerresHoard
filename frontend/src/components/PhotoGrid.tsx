import { fileName } from "../api";
import type { Photo } from "../types";

interface Props {
  photos: Photo[];
  onOpen: (index: number) => void;
  // A6 (live report): a single photo could not be removed from an album in
  // the UI, though the endpoint and the skill both say the owner can.
  // Selecting one or several photos here, instead of opening the lightbox,
  // is how AlbumsPage offers that control.
  selectable?: boolean;
  selectedIds?: Set<string>;
  onToggleSelect?: (id: string) => void;
}

export default function PhotoGrid({ photos, onOpen, selectable, selectedIds, onToggleSelect }: Props) {
  return (
    <div className="grid">
      {photos.map((p, i) => {
        const selected = selectable && selectedIds?.has(p.id);
        return (
          <button
            key={p.id}
            className={`thumb${selected ? " selected" : ""}`}
            onClick={() => (selectable ? onToggleSelect?.(p.id) : onOpen(i))}
            title={fileName(p.path)}
            aria-pressed={selectable ? selected : undefined}
          >
            <img src={p.thumbnail_url} alt={fileName(p.path)} loading="lazy" decoding="async" />
            {selectable && <span className="select-dot" />}
            {!selectable && p.relevance && (
              // B2 (live report): `score` alone did not say how confident a
              // match was; this mirrors the `relevance` band an agent gets.
              <span className={`relevance-dot relevance-${p.relevance}`} title={`relevance: ${p.relevance}`} />
            )}
            <div className="meta">
              <span>{p.taken_at ? p.taken_at.slice(0, 10) : ""}</span>
              {p.place && <span className="meta-place">{p.place}</span>}
            </div>
          </button>
        );
      })}
    </div>
  );
}
