import { useEffect, useState } from "react";
import { Eye } from "lucide-react";
import { api } from "../api";
import type { Dict } from "../i18n";
import type { AgentCall } from "../types";

interface Props {
  t: Dict;
}

export default function ActivityPage({ t }: Props) {
  const [calls, setCalls] = useState<AgentCall[]>([]);

  useEffect(() => {
    const load = () =>
      api
        .agentCalls(50)
        .then(setCalls)
        .catch(() => {});
    load();
    const interval = setInterval(load, 4000);
    return () => clearInterval(interval);
  }, []);

  if (calls.length === 0) {
    return (
      <div className="empty-state">
        <Eye size={40} />
        <h3>{t.assistant_activity_empty}</h3>
      </div>
    );
  }

  return (
    <div className="card table-card">
    <table className="activity-table">
      <thead>
        <tr>
          <th>{t.tool}</th>
          <th>{t.when}</th>
          <th>{t.duration}</th>
          <th>{t.result}</th>
        </tr>
      </thead>
      <tbody>
        {calls.map((c) => (
          <tr key={c.id}>
            <td>
              <code>{c.tool}</code>
              <div className="args">{c.args_summary}</div>
            </td>
            <td>{new Date(c.created_at).toLocaleString()}</td>
            <td>{Math.round(c.duration_ms)} ms</td>
            <td>
              <span className={`badge ${c.ok ? "badge-ok" : "badge-fail"}`}>{c.ok ? t.ok : t.failed}</span>
              {c.error && <div className="error-text small">{c.error}</div>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}
