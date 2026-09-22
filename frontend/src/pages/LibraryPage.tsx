import { useCallback, useEffect, useRef, useState } from "react";
import { Images } from "lucide-react";
import { api } from "../api";
import Lightbox from "../components/Lightbox";
import PhotoGrid from "../components/PhotoGrid";
import type { Dict } from "../i18n";
import type { Photo } from "../types";

interface Props {
  t: Dict;
  platformIsWindows: boolean;
  totalPhotoCount: number;
}

export default function LibraryPage({ t, platformIsWindows, totalPhotoCount }: Props) {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(0);
  const [loading, setLoading] = useState(false);
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  const loadMore = useCallback(async () => {
    if (loading || nextOffset === null) return;
    setLoading(true);
    try {
      const result = await api.listPhotos({ offset: nextOffset, limit: 60 });
      setPhotos((prev) => (nextOffset === 0 ? result.results : [...prev, ...result.results]));
      setNextOffset(result.next_offset);
    } finally {
      setLoading(false);
    }
  }, [loading, nextOffset]);

  useEffect(() => {
    setPhotos([]);
    setNextOffset(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [totalPhotoCount]);

  useEffect(() => {
    if (nextOffset === 0) loadMore();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nextOffset]);

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) loadMore();
      },
      { rootMargin: "400px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [loadMore]);

  if (photos.length === 0 && !loading) {
    return (
      <div className="empty-state">
        <Images size={40} />
        <h3>{t.empty_library_title}</h3>
        <p>{t.empty_library_body}</p>
      </div>
    );
  }

  return (
    <div>
      <PhotoGrid photos={photos} onOpen={setOpenIndex} />
      <div ref={sentinelRef} style={{ height: 1 }} />
      {loading && <p style={{ textAlign: "center", color: "var(--text-muted)" }}>{t.loading}</p>}
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
