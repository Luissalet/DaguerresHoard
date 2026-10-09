import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Play, Video as VideoIcon } from "lucide-react";
import { api, errorText, formatBytes } from "../api";
import FrameStrip from "../components/FrameStrip";
import Lightbox from "../components/Lightbox";
import type { Dict } from "../i18n";
import { frameAsPhoto, type LibraryStatus, type VideoDetail, type VideoSummary } from "../types";

interface Props {
  t: Dict;
  platformIsWindows: boolean;
  status: LibraryStatus | null;
}

export default function VideosPage({ t, platformIsWindows, status }: Props) {
  const [videos, setVideos] = useState<VideoSummary[]>([]);
  const [note, setNote] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<VideoDetail | null>(null);
  const [playing, setPlaying] = useState(false);
  const [playerFailed, setPlayerFailed] = useState(false);
  const [lightIndex, setLightIndex] = useState<number | null>(null);
  const playerRef = useRef<HTMLVideoElement | null>(null);
  const pendingSeek = useRef<number | null>(null);

  useEffect(() => {
    if (open) return;
    api
      .listVideos({ limit: 200 })
      .then((r) => {
        setVideos(r.results);
        setNote(r.note ?? null);
        setError(null);
      })
      .catch((e) => setError(errorText(e)))
      .finally(() => setLoaded(true));
  }, [open, status?.video_count, status?.indexing]);

  async function openVideo(v: VideoSummary) {
    try {
      setOpen(await api.getVideo(v.id));
      setPlaying(false);
      setPlayerFailed(false);
      setError(null);
    } catch (e) {
      setError(errorText(e));
    }
  }

  function seekTo(ts: number) {
    const el = playerRef.current;
    if (el) {
      el.currentTime = ts;
    } else {
      pendingSeek.current = ts;
    }
  }

  if (open) {
    const photos = open.frames.map((f) => frameAsPhoto(open, f));
    return (
      <div>
        <button className="btn" onClick={() => setOpen(null)}>
          <ArrowLeft size={14} /> {t.nav_videos}
        </button>
        <h2 title={open.path}>{open.name}</h2>
        <p className="muted small">
          {[
            open.duration_label,
            open.width && open.height ? `${open.width} × ${open.height}` : null,
            open.taken_at ? open.taken_at.slice(0, 10) : null,
            formatBytes(open.size),
            t.video_frames_n(open.frame_count),
          ]
            .filter(Boolean)
            .join(" · ")}
        </p>
        {playing ? (
          <>
            <video
              ref={(el) => {
                playerRef.current = el;
                if (el && pendingSeek.current !== null) {
                  const ts = pendingSeek.current;
                  pendingSeek.current = null;
                  el.addEventListener("loadedmetadata", () => (el.currentTime = ts), { once: true });
                }
              }}
              className="video-player"
              src={api.videoStreamUrl(open.id)}
              controls
              preload="metadata"
              onError={() => setPlayerFailed(true)}
            />
            {playerFailed && <p className="error-text small">{t.video_player_failed}</p>}
            <button className="btn" onClick={() => setPlaying(false)}>
              {t.video_hide_player}
            </button>
          </>
        ) : (
          <button className="btn" onClick={() => setPlaying(true)}>
            <Play size={14} /> {t.video_play_from(open.frames[0]?.timestamp ?? "00:00")}
          </button>
        )}
        <div className="side-label" style={{ marginTop: 14 }}>
          {t.video_key_frames}
        </div>
        {open.frames.length === 0 ? (
          <p className="muted">{open.error ?? t.video_no_frames}</p>
        ) : (
          <FrameStrip
            frames={open.frames}
            onPick={(f) => {
              if (playing) seekTo(f.ts);
              setLightIndex(open.frames.findIndex((x) => x.id === f.id));
            }}
          />
        )}
        {lightIndex !== null && (
          <Lightbox
            photos={photos}
            index={lightIndex}
            onClose={() => setLightIndex(null)}
            onIndexChange={(i) => {
              setLightIndex(i);
              if (playing) seekTo(open.frames[i].ts);
            }}
            t={t}
            platformIsWindows={platformIsWindows}
          />
        )}
      </div>
    );
  }

  if (loaded && videos.length === 0) {
    return (
      <div className="empty-state">
        <VideoIcon size={40} />
        <h3>{error ? t.error_generic : t.videos_empty_title}</h3>
        <p>{error ?? note ?? t.videos_empty_body}</p>
      </div>
    );
  }

  return (
    <div>
      {note && <p className="muted small">{note}</p>}
      {error && <p className="error-text">{error}</p>}
      <div className="grid">
        {videos.map((v) => (
          <button key={v.id} className="video-card" onClick={() => openVideo(v)} title={v.path}>
            <div className="video-cover">
              {v.thumbnail_url && <img src={v.thumbnail_url} alt="" loading="lazy" decoding="async" />}
              {v.duration_label && <span className="video-badge">{v.duration_label}</span>}
            </div>
            <div className="video-info">
              <div className="name">{v.name}</div>
              <div className="muted small">
                {[v.taken_at ? v.taken_at.slice(0, 10) : null, t.video_frames_n(v.frame_count)].filter(Boolean).join(" · ")}
              </div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
