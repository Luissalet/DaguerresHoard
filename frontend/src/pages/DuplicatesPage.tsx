import { useEffect, useState } from "react";
import { Check, Copy } from "lucide-react";
import { api } from "../api";
import type { Dict } from "../i18n";
import type { DuplicateGroup } from "../types";

interface Props {
  t: Dict;
}

export default function DuplicatesPage({ t }: Props) {
  const [kind, setKind] = useState<"exact" | "near">("exact");
  const [groups, setGroups] = useState<DuplicateGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [copiedGroup, setCopiedGroup] = useState<number | null>(null);

  useEffect(() => {
    setLoading(true);
    api
      .duplicates(kind, 20)
      .then((r) => setGroups(r.groups))
      .finally(() => setLoading(false));
  }, [kind]);

  function copyPaths(group: DuplicateGroup, idx: number) {
    const text = group.photos.map((p) => p.path).join("\n");
    navigator.clipboard?.writeText(text).catch(() => {});
    setCopiedGroup(idx);
    setTimeout(() => setCopiedGroup(null), 1500);
  }

  return (
    <div>
      <div className="toolbar">
        <button className={`btn${kind === "exact" ? " btn-primary" : ""}`} onClick={() => setKind("exact")}>
          {t.exact_duplicates}
        </button>
        <button className={`btn${kind === "near" ? " btn-primary" : ""}`} onClick={() => setKind("near")}>
          {t.near_duplicates}
        </button>
      </div>

      {loading && <p style={{ color: "var(--text-muted)" }}>{t.loading}</p>}
      {!loading && groups.length === 0 && (
        <div className="empty-state">
          <Copy size={40} />
          <h3>{t.no_results}</h3>
        </div>
      )}

      {groups.map((g, idx) => (
        <div className="duplicate-group" key={idx}>
          <div className="duplicate-group-header">
            <span style={{ color: "var(--text-muted)", fontSize: 13 }}>{t.photos_count(g.photos.length)}</span>
            <button className="btn" onClick={() => copyPaths(g, idx)}>
              {copiedGroup === idx ? <Check size={14} /> : <Copy size={14} />}
              {copiedGroup === idx ? t.copied : t.copy_paths}
            </button>
          </div>
          <div className="duplicate-row">
            {g.photos.map((p) => (
              <div key={p.id} className={`duplicate-card${p.id === g.keeper_id ? " keeper" : ""}`}>
                {p.id === g.keeper_id && <span className="keeper-badge">{t.keeper}</span>}
                <img src={p.thumbnail_url} alt="" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
