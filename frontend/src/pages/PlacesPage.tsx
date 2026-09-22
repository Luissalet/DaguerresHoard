import { useEffect, useState } from "react";
import { MapPin } from "lucide-react";
import { api } from "../api";
import type { Dict } from "../i18n";

interface Props {
  t: Dict;
}

type Countries = Record<string, { city: string; count: number; sample_thumbnail_url: string }[]>;

export default function PlacesPage({ t }: Props) {
  const [countries, setCountries] = useState<Countries | null>(null);

  useEffect(() => {
    api.places().then((r) => setCountries(r.countries));
  }, []);

  if (!countries) return <p style={{ color: "var(--text-muted)" }}>{t.loading}</p>;

  const names = Object.keys(countries).sort();
  if (names.length === 0) {
    return (
      <div className="empty-state">
        <MapPin size={40} />
        <h3>{t.places_empty}</h3>
      </div>
    );
  }

  return (
    <div>
      {names.map((country) => (
        <div key={country} style={{ marginBottom: 26 }}>
          <h3>{country}</h3>
          <div className="places-grid">
            {countries[country].map((c) => (
              <div className="place-card" key={c.city}>
                <img src={c.sample_thumbnail_url} alt="" />
                <div className="place-info">
                  <strong>{c.city}</strong>
                  <div style={{ color: "var(--text-muted)", fontSize: 12.5 }}>{t.photos_count(c.count)}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
