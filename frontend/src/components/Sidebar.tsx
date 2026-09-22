import {
  Activity,
  Copy,
  Eye,
  FolderOpen,
  Images,
  MapPin,
  Search,
  Settings as SettingsIcon,
} from "lucide-react";
import type { Dict } from "../i18n";

export type Page =
  | "library"
  | "search"
  | "duplicates"
  | "timeline"
  | "places"
  | "albums"
  | "settings"
  | "activity";

interface Props {
  page: Page;
  onNavigate: (p: Page) => void;
  t: Dict;
}

const ITEMS: { id: Page; icon: typeof Images; labelKey: keyof Dict }[] = [
  { id: "library", icon: Images, labelKey: "nav_library" },
  { id: "search", icon: Search, labelKey: "nav_search" },
  { id: "duplicates", icon: Copy, labelKey: "nav_duplicates" },
  { id: "timeline", icon: Activity, labelKey: "nav_timeline" },
  { id: "places", icon: MapPin, labelKey: "nav_places" },
  { id: "albums", icon: FolderOpen, labelKey: "nav_albums" },
  { id: "settings", icon: SettingsIcon, labelKey: "nav_settings" },
  { id: "activity", icon: Eye, labelKey: "nav_activity" },
];

export default function Sidebar({ page, onNavigate, t }: Props) {
  return (
    <nav className="sidebar">
      <div className="sidebar-brand">
        <Eye size={22} color="#2fd8dc" />
        <span className="label">{t.appName}</span>
      </div>
      <div className="sidebar-nav">
        {ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              className={`sidebar-item${page === item.id ? " active" : ""}`}
              onClick={() => onNavigate(item.id)}
            >
              <Icon size={17} />
              <span className="label">{t[item.labelKey] as string}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
