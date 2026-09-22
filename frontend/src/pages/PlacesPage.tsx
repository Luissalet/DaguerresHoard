import { useEffect, useState } from "react";
import { AlertTriangle, ArrowLeft, MapPin } from "lucide-react";
import { api, errorText } from "../api";
import Lightbox from "../components/Lightbox";
import PhotoGrid from "../components/PhotoGrid";
import type { Dict } from "../i18n";
import type { Photo } from "../types";

interface Props {
  t: Dict;
  platformIsWindows: boolean;
  onOpenSettings: () => void;
}

type Countries = Record<string, { city: string; count: number; sample_thumbnail_url: string }[]>;

export default function PlacesPage({ t, platformIsWindows, onOpenSettings }: Props) {
  const [countries, setCountries] = useState<Countries | null>(null);
  const [approximateCount, setApproximateCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [city, setCity] = useState<string | null>(null);
  const [cityPhotos, setCityPhotos] = useState<Photo[]>([]);
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  useEffect(() => {
    api
      .places()
      .then((r) => {
        setCountries(r.countries);
        setApproximateCount(r.approximate_count ?? 0);
      })
      .catch((e) => setError(errorText(e)));
  }, []);

  useEffect(() => {
    if (!city) return;
    setCityPhotos([]);
    api
      .listPhotos({ place: city, limit: 500 })
      .then((r) => setCityPhotos(r.results))
      .catch((e) => setError(errorText(e)));
  }, [city]);

  if (error) return <p className="error-text">{error}</p>;
  if (!countries) return <p className="muted">{t.loading}</p>;

  if (city) {
    return (
      <div>
        <div className="toolbar">
          <button className="btn" onClick={() => setCity(null)}>
            <ArrowLeft size={14} /> {t.nav_places}
          </button>
          <h2 className="section-title">{city}</h2>
          <span className="muted">{t.photos_count(cityPhotos.length)}</span>
        </div>
        <PhotoGrid photos={cityPhotos} onOpen={setOpenIndex} />
        {openIndex !== null && (
          <Lightbox
            photos={cityPhotos}
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

  const names = Object.keys(countries).sort();
  const approximateNotice = approximateCount > 0 && (
    <div className="notice notice-warn">
      <AlertTriangle size={18} />
      <div>
        <p>{t.places_approximate_note(approximateCount)}</p>
      </div>
      <button className="btn" onClick={onOpenSettings}>
        {t.open_settings}
      </button>
    </div>
  );

  if (names.length === 0) {
    return (
      <div>
        {approximateNotice}
        <div className="empty-state">
          <MapPin size={40} />
          <h3>{t.places_empty}</h3>
        </div>
      </div>
    );
  }

  return (
    <div className="places-columns">
      {approximateNotice}
      {names.map((country) => {
        const cities = countries[country];
        const total = cities.reduce((a, c) => a + c.count, 0);
        return (
          <section key={country} className="country-block">
            <h3>
              {country} <span className="muted small">{t.photos_count(total)}</span>
            </h3>
            <div className="places-grid">
              {cities.map((c) => (
                <button className="place-card" key={c.city} onClick={() => setCity(c.city)}>
                  <img src={c.sample_thumbnail_url} alt="" loading="lazy" />
                  <div className="place-info">
                    <MapPin size={13} />
                    <strong>{c.city}</strong>
                    <span className="muted small">{t.photos_count(c.count)}</span>
                  </div>
                </button>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
