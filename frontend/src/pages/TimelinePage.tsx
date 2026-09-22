import { useEffect, useState } from "react";
import { api } from "../api";
import type { Dict } from "../i18n";
import type { TimelineResult } from "../types";

interface Props {
  t: Dict;
}

export default function TimelinePage({ t }: Props) {
  const [data, setData] = useState<TimelineResult | null>(null);

  useEffect(() => {
    api.timeline().then(setData);
  }, []);

  if (!data) return <p style={{ color: "var(--text-muted)" }}>{t.loading}</p>;

  const years = Object.keys(data.years).sort((a, b) => Number(b) - Number(a));

  return (
    <div>
      {data.on_this_day.length > 0 && (
        <div className="card" style={{ padding: 16, marginBottom: 24 }}>
          <h3 style={{ marginTop: 0 }}>{t.on_this_day}</h3>
          <p style={{ color: "var(--text-muted)", fontSize: 13 }}>{t.photos_count(data.on_this_day.length)}</p>
        </div>
      )}
      {years.length === 0 && <p>{t.no_results}</p>}
      {years.map((year) => {
        const months = data.years[year];
        const total = Object.values(months).reduce((a, b) => a + b, 0);
        return (
          <div className="timeline-year" key={year}>
            <h3>
              {year} <span style={{ color: "var(--text-muted)", fontWeight: 400, fontSize: 14 }}>{t.photos_count(total)}</span>
            </h3>
            <div className="timeline-months">
              {Object.entries(months)
                .sort(([a], [b]) => Number(a) - Number(b))
                .map(([month, count]) => (
                  <div className="month-chip" key={month}>
                    {t.month_names[Number(month) - 1]} <b>{count}</b>
                  </div>
                ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
