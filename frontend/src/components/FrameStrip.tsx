import type { VideoFrame } from "../types";

interface Props {
  frames: VideoFrame[];
  activeId?: string;
  onPick: (frame: VideoFrame) => void;
}

/** The key frames of one video, in time order; each chip shows its timestamp. */
export default function FrameStrip({ frames, activeId, onPick }: Props) {
  return (
    <div className="frame-strip">
      {frames.map((f) => (
        <button
          key={f.id}
          className={`frame-chip${f.id === activeId ? " active" : ""}`}
          onClick={() => onPick(f)}
          title={f.timestamp}
          aria-label={f.timestamp}
        >
          <img src={f.thumbnail_url} alt="" loading="lazy" draggable={false} />
          <span className="frame-time">{f.timestamp}</span>
        </button>
      ))}
    </div>
  );
}
