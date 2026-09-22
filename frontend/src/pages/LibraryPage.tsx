import { useCallback, useEffect, useRef, useState } from "react";
import { Images, Settings } from "lucide-react";
import { api, errorText } from "../api";
import Lightbox from "../components/Lightbox";
import PhotoGrid from "../components/PhotoGrid";
import type { Dict } from "../i18n";
import type { LibraryStatus, Photo } from "../types";

interface Props {
  t: Dict;
  platformIsWindows: boolean;
  status: LibraryStatus | null;
  onOpenSettings: () => void;
}

const PAGE = 90;

export default function LibraryPage({ t, platformIsWindows, status, onOpenSettings }: Props) {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const busy = useRef(false);
  const photoCount = status?.photo_count ?? 0;

  const loadMore = useCallback(
    async (offset: number | null, replace = false) => {
      if (busy.current || offset === null) return;
      busy.current = true;
      setLoading(true);
      try {
        const result = await api.listPhotos({ offset, limit: PAGE });
        setPhotos((prev) => (replace ? result.results : [...prev, ...result.results]));
        setNextOffset(result.next_offset);
        setError(null);
      } catch (e) {
        setError(errorText(e));
      } finally {
        busy.current = false;
        setLoading(false);
      }
    },
    [],
  );

  // First page, and a refresh whenever the indexed count changes (a scan
  // in progress adds photos) -- but never while the lightbox is open.
  useEffect(() => {
    if (openIndex !== null) return;
    loadMore(0, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [photoCount, loadMore]);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) loadMore(nextOffset);
      },
      { rootMargin: "600px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [loadMore, nextOffset]);

  if (photos.length === 0 && !loading) {
    return (
      <div className="empty-state">
        <Images size={40} />
        <h3>{error ? t.error_generic : status?.indexing ? t.indexing_now : t.empty_library_title}</h3>
        <p>{error ?? t.empty_library_body}</p>
        {!error && !status?.indexing && (
          <button className="btn btn-primary" onClick={onOpenSettings}>
            <Settings size={14} /> {t.open_settings}
          </button>
        )}
      </div>
    );
  }

  return (
    <div>
      <PhotoGrid photos={photos} onOpen={setOpenIndex} />
      <div ref={sentinelRef} style={{ height: 1 }} />
      {loading && <p className="muted center">{t.loading}</p>}
      {error && <p className="error-text">{error}</p>}
      {openIndex !== null && (
        <Lightbox
          photos={photos}
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
