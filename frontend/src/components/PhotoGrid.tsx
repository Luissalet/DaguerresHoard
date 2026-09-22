import type { Photo } from "../types";

interface Props {
  photos: Photo[];
  selectable?: boolean;
  selected?: Set<string>;
  onToggleSelect?: (id: string) => void;
  onOpen: (index: number) => void;
}

export default function PhotoGrid({ photos, selectable, selected, onToggleSelect, onOpen }: Props) {
  return (
    <div className="grid">
      {photos.map((p, i) => (
        <div
          key={p.id}
          className={`thumb${selected?.has(p.id) ? " selected" : ""}`}
          onClick={() => {
            if (selectable && onToggleSelect) onToggleSelect(p.id);
            else onOpen(i);
          }}
          onDoubleClick={() => onOpen(i)}
        >
          <img src={p.thumbnail_url} alt="" loading="lazy" />
          {selectable && <div className="select-dot" />}
          <div className="meta">
            {p.taken_at ? p.taken_at.slice(0, 10) : ""}
            {p.place ? ` · ${p.place}` : ""}
          </div>
        </div>
      ))}
    </div>
  );
}
