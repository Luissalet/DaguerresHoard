import { useEffect, useState } from "react";
import { Languages, Moon, Sun } from "lucide-react";
import { api } from "./api";
import Sidebar, { type Page } from "./components/Sidebar";
import { detectLang, dict, type Lang } from "./i18n";
import ActivityPage from "./pages/ActivityPage";
import AlbumsPage from "./pages/AlbumsPage";
import DuplicatesPage from "./pages/DuplicatesPage";
import LibraryPage from "./pages/LibraryPage";
import PlacesPage from "./pages/PlacesPage";
import SearchPage from "./pages/SearchPage";
import SettingsPage from "./pages/SettingsPage";
import TimelinePage from "./pages/TimelinePage";

type Theme = "light" | "dark";

function readStored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStored(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // best-effort only: a private window or blocked storage should not break the app
  }
}

export default function App() {
  const [page, setPage] = useState<Page>("library");
  const [lang, setLang] = useState<Lang>(() => (readStored("argus-lang") as Lang) || detectLang());
  const [theme, setTheme] = useState<Theme>(() => (readStored("argus-theme") as Theme) || "light");
  const [photoCount, setPhotoCount] = useState(0);
  const [platformIsWindows] = useState(() => navigator.userAgent.toLowerCase().includes("windows"));

  const t = dict[lang];

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    writeStored("argus-theme", theme);
  }, [theme]);

  useEffect(() => {
    writeStored("argus-lang", lang);
  }, [lang]);

  function refreshLibraryStatus() {
    api.libraryStatus().then((s) => setPhotoCount(s.photo_count));
  }

  useEffect(() => {
    refreshLibraryStatus();
  }, []);

  const titleByPage: Record<Page, string> = {
    library: t.nav_library,
    search: t.nav_search,
    duplicates: t.nav_duplicates,
    timeline: t.nav_timeline,
    places: t.nav_places,
    albums: t.nav_albums,
    settings: t.nav_settings,
    activity: t.nav_activity,
  };

  return (
    <div className="app-shell">
      <Sidebar page={page} onNavigate={setPage} t={t} />
      <div className="main">
        <div className="topbar">
          <h1>{titleByPage[page]}</h1>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              className="icon-btn"
              onClick={() => setLang(lang === "en" ? "es" : "en")}
              title={t.lang_switch}
              aria-label="Language"
            >
              <Languages size={16} />
            </button>
            <button
              className="icon-btn"
              onClick={() => setTheme(theme === "light" ? "dark" : "light")}
              title={theme === "light" ? t.theme_dark : t.theme_light}
              aria-label="Theme"
            >
              {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
            </button>
          </div>
        </div>
        <div className="content">
          {page === "library" && (
            <LibraryPage t={t} platformIsWindows={platformIsWindows} totalPhotoCount={photoCount} />
          )}
          {page === "search" && <SearchPage t={t} platformIsWindows={platformIsWindows} />}
          {page === "duplicates" && <DuplicatesPage t={t} />}
          {page === "timeline" && <TimelinePage t={t} />}
          {page === "places" && <PlacesPage t={t} />}
          {page === "albums" && <AlbumsPage t={t} platformIsWindows={platformIsWindows} />}
          {page === "settings" && <SettingsPage t={t} onLibraryChanged={refreshLibraryStatus} />}
          {page === "activity" && <ActivityPage t={t} />}
        </div>
      </div>
    </div>
  );
}
