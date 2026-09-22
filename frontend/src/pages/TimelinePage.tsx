import { useEffect, useState } from "react";
import { ArrowLeft, CalendarDays } from "lucide-react";
import { api, errorText } from "../api";
import Lightbox from "../components/Lightbox";
import PhotoGrid from "../components/PhotoGrid";
import type { Dict } from "../i18n";
import type { Photo, TimelineResult } from "../types";

interface Props {
  t: Dict;
  platformIsWindows: boolean;
}

export default function TimelinePage({ t, platformIsWindows }: Props) {
  const [data, setData] = useState<TimelineResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [month, setMonth] = useState<{ year: string; month: string } | null>(null);
  const [monthPhotos, setMonthPhotos] = useState<Photo[]>([]);
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  useEffect(() => {
    api
      .timeline()
      .then(setData)
      .catch((e) => setError(errorText(e)));
  }, []);

  useEffect(() => {
    if (!month) return;
    setMonthPhotos([]);
    api
      .listPhotos({ year: Number(month.year), month: Number(month.month), limit: 500 })
      .then((r) => setMonthPhotos(r.results))
      .catch((e) => setError(errorText(e)));
  }, [month]);

  if (error) return <p className="error-text">{error}</p>;
  if (!data) return <p className="muted">{t.loading}</p>;

  if (month) {
    return (
      <div>
        <div className="toolbar">
          <button className="btn" onClick={() => setMonth(null)}>
            <ArrowLeft size={14} /> {t.back_to_timeline}
          </button>
          <h2 className="section-title">
            {t.month_names[Number(month.month) - 1]} {month.year}
          </h2>
          <span className="muted">{t.photos_count(monthPhotos.length)}</span>
        </div>
        <PhotoGrid photos={monthPhotos} onOpen={setOpenIndex} />
        {openIndex !== null && (
          <Lightbox
            photos={monthPhotos}
            index={openIndex}
            onClose={() => setOpenIndex(null)}
            onIndexChange={setOpenIndex}
            t={t}
            platformIsWindows={platformIsWindows}
          />
        )}
      </div>
    );
  }

  const years = Object.keys(data.months).sort((a, b) => Number(b) - Number(a));
  if (years.length === 0) {
    return (
      <div className="empty-state">
        <CalendarDays size={40} />
        <h3>{t.no_results}</h3>
      </div>
    );
  }

  return (
    <div>
      {data.on_this_day.length > 0 && (
        <section className="card on-this-day">
          <h3>
            {t.on_this_day} <span className="muted small">{t.photos_count(data.on_this_day_count)}</span>
          </h3>
          <div className="similar-strip">
            {data.on_this_day.map((p) => (
              <img key={p.id} src={p.thumbnail_url} alt="" title={p.taken_at.slice(0, 10)} />
            ))}
          </div>
        </section>
      )}
      {years.map((year) => {
        const months = data.months[year];
        return (
          <section className="timeline-year" key={year}>
            <h3>
              {year} <span className="muted year-total">{t.photos_count(data.years[year] ?? 0)}</span>
            </h3>
            <div className="timeline-months">
              {Object.entries(months)
                .sort(([a], [b]) => Number(a) - Number(b))
                .map(([m, count]) => {
                  const samples = data.samples?.[`${year}-${m}`] ?? [];
                  return (
                    <button className="month-card" key={m} onClick={() => setMonth({ year, month: m })}>
                      <div className={`month-mosaic n${Math.min(samples.length, 4)}`}>
                        {samples.slice(0, 4).map((id) => (
                          <img key={id} src={`/api/photos/${id}/thumbnail`} alt="" loading="lazy" />
                        ))}
                      </div>
                      <div className="month-label">
                        <strong>{t.month_names[Number(m) - 1]}</strong>
                        <span className="muted small">{t.photos_count(count)}</span>
                      </div>
                    </button>
                  );
                })}
            </div>
          </section>
        );
      })}
    </div>
  );
}
