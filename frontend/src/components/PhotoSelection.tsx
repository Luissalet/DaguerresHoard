import { useState } from "react";
import { Columns2, Download, FolderPlus, X } from "lucide-react";
import type { Photo } from "../types";
import type { Dict } from "../i18n";
import PhotoGrid from "./PhotoGrid";
import SelectionExport from "./SelectionExport";
import PhotoComparison from "./PhotoComparison";
import SelectionAlbum from "./SelectionAlbum";

export default function PhotoSelection({ photos, onOpen, t }: { photos: Photo[]; onOpen: (index: number) => void; t: Dict }) {
  const [mode, setMode] = useState<"export" | "album" | null>(null);
  const selecting = mode !== null;
  const [selected, setSelected] = useState<string[]>([]);
  const [comparing, setComparing] = useState(false);
  const available = new Map(photos.map(photo => [photo.id, photo]));
  const chosen = selected.flatMap(id => available.has(id) ? [available.get(id)!] : []);
  function toggle(id: string) { setSelected(current => current.includes(id) ? current.filter(item => item !== id) : [...current, id]); }
  return <>
    <div className="toolbar selection-toolbar">
      <button className="btn" type="button" aria-pressed={comparing} onClick={() => setComparing(!comparing)}><Columns2 size={14} /> {t.compare_title}</button>
      <button className="btn" type="button" aria-pressed={mode === "export"} onClick={() => setMode("export")}>
        <Download size={14} /> {t.export_selection}
      </button>
      <button className="btn" type="button" aria-pressed={mode === "album"} onClick={() => setMode("album")}><FolderPlus size={14} /> {t.album_selection}</button>
      {selecting && <>
        <button className="btn" type="button" onClick={() => { setMode(null); setSelected([]); }}><X size={14} /> {t.cancel}</button>
        <span className="muted">{chosen.length} {t.selected}{mode === "export" ? ` · ${t.export_choose}` : ""}</span>
        <button className="btn" type="button" onClick={() => setSelected(photos.slice(0, 20).map(photo => photo.id))}>{t.export_first}</button>
        {chosen.length > 0 && <button className="btn" type="button" onClick={() => setSelected([])}>{t.export_clear}</button>}
      </>}
    </div>
    {mode === "export" && chosen.length > 0 && <SelectionExport photos={chosen} t={t} />}
    {mode === "album" && <SelectionAlbum photos={chosen} t={t} />}
    <PhotoComparison photos={photos} onOpen={onOpen} open={comparing} onClose={() => setComparing(false)} t={t} />
    <PhotoGrid photos={photos} onOpen={onOpen} selectable={selecting} selectedIds={new Set(selected)} onToggleSelect={toggle} />
  </>;
}
