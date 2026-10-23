import { useState } from "react";
import { Columns2, Download, X } from "lucide-react";
import type { Photo } from "../types";
import type { Dict } from "../i18n";
import PhotoGrid from "./PhotoGrid";
import SelectionExport from "./SelectionExport";
import PhotoComparison from "./PhotoComparison";

export default function PhotoSelection({ photos, onOpen, t }: { photos: Photo[]; onOpen: (index: number) => void; t: Dict }) {
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [comparing, setComparing] = useState(false);
  const available = new Map(photos.map(photo => [photo.id, photo]));
  const chosen = selected.flatMap(id => available.has(id) ? [available.get(id)!] : []);
  function toggle(id: string) { setSelected(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id]); }
  return <>
    <div className="toolbar selection-toolbar">
      <button className="btn" type="button" aria-pressed={comparing} onClick={() => setComparing(!comparing)}><Columns2 size={14} /> {t.compare_title}</button>
      <button className="btn" type="button" aria-pressed={selecting} onClick={() => { setSelecting(!selecting); setSelected([]); }}>
        {selecting ? <X size={14} /> : <Download size={14} />} {selecting ? t.cancel : t.export_selection}
      </button>
      {selecting && <>
        <span className="muted">{chosen.length} {t.selected} · {t.export_choose}</span>
        <button className="btn" type="button" onClick={() => setSelected(photos.slice(0, 20).map(photo => photo.id))}>{t.export_first}</button>
        {chosen.length > 0 && <button className="btn" type="button" onClick={() => setSelected([])}>{t.export_clear}</button>}
      </>}
    </div>
    {selecting && chosen.length > 0 && <SelectionExport photos={chosen} t={t} />}
    <PhotoComparison photos={photos} onOpen={onOpen} open={comparing} onClose={() => setComparing(false)} t={t} />
    <PhotoGrid photos={photos} onOpen={onOpen} selectable={selecting} selectedIds={new Set(selected)} onToggleSelect={toggle} />
  </>;
}
