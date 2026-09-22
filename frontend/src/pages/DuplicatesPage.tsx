import { useEffect, useState } from "react";
import { Check, Copy, ExternalLink } from "lucide-react";
import { api, errorText, fileName, formatBytes, parentFolder } from "../api";
import Lightbox from "../components/Lightbox";
import type { Dict } from "../i18n";
import type { DuplicatesResult, Photo } from "../types";

interface Props {
  t: Dict;
  platformIsWindows: boolean;
}

export default function DuplicatesPage({ t, platformIsWindows }: Props) {
  const [kind, setKind] = useState<"exact" | "near">("exact");
  const [data, setData] = useState<DuplicatesResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [copiedGroup, setCopiedGroup] = useState<number | null>(null);
  const [open, setOpen] = useState<{ photos: Photo[]; index: number } | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .duplicates(kind, 50)
      .then(setData)
      .catch((e) => setError(errorText(e)))
      .finally(() => setLoading(false));
  }, [kind]);

  function copyPaths(photos: Photo[], keeperId: string, idx: number) {
    // A2 (live report): copying every path (keeper included) meant pasting
    // the list into a delete command also deleted the copy to keep.
    const text = photos
      .filter((p) => p.id !== keeperId)
      .map((p) => p.path)
      .join("\n");
    navigator.clipboard?.writeText(text).catch(() => {});
    setCopiedGroup(idx);
    setTimeout(() => setCopiedGroup(null), 1500);
  }

  const groups = data?.groups ?? [];

  return (
    <div>
      <div className="toolbar">
        <div className="segmented">
          <button className={kind === "exact" ? "active" : ""} onClick={() => setKind("exact")}>
            {t.exact_duplicates}
          </button>
          <button className={kind === "near" ? "active" : ""} onClick={() => setKind("near")}>
            {t.near_duplicates}
          </button>
        </div>
        {data && data.total_groups > 0 && (
          <span className="muted">
            {(kind === "near" ? t.dup_summary_near : t.dup_summary)(
              data.total_groups,
              formatBytes(data.reclaimable_bytes_total),
            )}
          </span>
        )}
      </div>

      {loading && <p className="muted">{t.loading}</p>}
      {error && <p className="error-text">{error}</p>}
      {!loading && !error && groups.length === 0 && (
        <div className="empty-state">
          <Copy size={40} />
          <h3>{t.no_results}</h3>
        </div>
      )}

      {groups.map((g, idx) => (
        <section className="duplicate-group card" key={g.keeper_id}>
          <div className="duplicate-group-header">
            <span className="muted small">
              {t.photos_count(g.photos.length)} ·{" "}
              {(kind === "near" ? t.dup_group_reclaim_near : t.dup_group_reclaim)(formatBytes(g.reclaimable_bytes))}
            </span>
            <button className="btn btn-sm" onClick={() => copyPaths(g.photos, g.keeper_id, idx)}>
              {copiedGroup === idx ? <Check size={14} /> : <Copy size={14} />}
              {copiedGroup === idx ? t.copied : t.copy_paths}
            </button>
          </div>
          <div className="duplicate-row">
            {g.photos.map((p, i) => (
              <figure key={p.id} className={`duplicate-card${p.id === g.keeper_id ? " keeper" : ""}`}>
                <button className="duplicate-img" onClick={() => setOpen({ photos: g.photos, index: i })}>
                  {p.id === g.keeper_id && <span className="keeper-badge">{t.keeper}</span>}
                  <img src={p.thumbnail_url} alt={fileName(p.path)} loading="lazy" />
                </button>
                <figcaption>
                  <span className="dup-name" title={p.path}>
                    {fileName(p.path)}
                  </span>
                  {parentFolder(p.path) && (
                    <span className="muted small dup-folder" title={p.path}>
                      {parentFolder(p.path)}
                    </span>
                  )}
                  <span className="muted small">
                    {p.width && p.height ? `${p.width}×${p.height}` : "?"} · {formatBytes(p.size)}
                  </span>
                  {platformIsWindows && (
                    <button className="link-btn" onClick={() => api.openInExplorer(p.id).catch(() => {})}>
                      <ExternalLink size={12} /> {t.open_folder}
                    </button>
                  )}
                </figcaption>
              </figure>
            ))}
          </div>
        </section>
      ))}
      {open && (
        <Lightbox
          photos={open.photos}
          index={open.index}
          onClose={() => setOpen(null)}
          onIndexChange={(i) => setOpen({ photos: open.photos, index: i })}
          t={t}
          platformIsWindows={platformIsWindows}
        />
      )}
    </div>
  );
}
