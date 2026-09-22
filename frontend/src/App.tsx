import { useCallback, useEffect, useState } from "react";
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
import type { LibraryStatus } from "./types";

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

function initialTheme(): Theme {
  const stored = readStored("argus-theme");
  if (stored === "light" || stored === "dark") return stored;
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  } catch {
    return "light";
  }
}

function initialLang(): Lang {
  const stored = readStored("argus-lang");
  return stored === "en" || stored === "es" ? stored : detectLang();
}

export default function App() {
  const [page, setPage] = useState<Page>("library");
  const [lang, setLang] = useState<Lang>(initialLang);
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [status, setStatus] = useState<LibraryStatus | null>(null);
  const [platformIsWindows] = useState(() => navigator.userAgent.toLowerCase().includes("windows"));

  const t = dict[lang];

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = t.appName;
  }, [lang, t.appName]);

  const refreshStatus = useCallback(() => {
    api
      .libraryStatus()
      .then(setStatus)
      .catch(() => {});
  }, []);

  useEffect(refreshStatus, [refreshStatus]);

  // While a scan or model download runs, keep the counts and progress fresh.
  useEffect(() => {
    if (!status?.indexing) return;
    const id = setInterval(refreshStatus, 1500);
    return () => clearInterval(id);
  }, [status?.indexing, refreshStatus]);

  function toggleTheme() {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    writeStored("argus-theme", next);
  }

  function toggleLang() {
    const next = lang === "en" ? "es" : "en";
    setLang(next);
    writeStored("argus-lang", next);
  }

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

  const runningJob = status?.recent_jobs.find((j) => j.status === "running");

  return (
    <div className="app-shell">
      <Sidebar page={page} onNavigate={setPage} t={t} status={status} />
      <div className="main">
        <header className="topbar">
          <div className="topbar-title">
            <h1>{titleByPage[page]}</h1>
            {status && (
              <span className="topbar-sub">
                {t.library_count(status.photo_count)}
                {runningJob && (
                  <>
                    {" · "}
                    <span className="topbar-busy">{t.indexing_now}</span> {Math.round(runningJob.progress * 100)}%
                  </>
                )}
              </span>
            )}
          </div>
          <div className="topbar-actions">
            <button className="icon-btn" onClick={toggleLang} title={t.lang_switch} aria-label="Language">
              <Languages size={16} />
              <span className="icon-btn-label">{t.lang_switch}</span>
            </button>
            <button
              className="icon-btn"
              onClick={toggleTheme}
              title={theme === "light" ? t.theme_dark : t.theme_light}
              aria-label="Theme"
            >
              {theme === "light" ? <Moon size={16} /> : <Sun size={16} />}
            </button>
          </div>
        </header>
        <main className="content">
          {page === "library" && (
            <LibraryPage
              t={t}
              platformIsWindows={platformIsWindows}
              status={status}
              onOpenSettings={() => setPage("settings")}
            />
          )}
          {page === "search" && (
            <SearchPage t={t} platformIsWindows={platformIsWindows} onOpenSettings={() => setPage("settings")} />
          )}
          {page === "duplicates" && <DuplicatesPage t={t} platformIsWindows={platformIsWindows} />}
          {page === "timeline" && <TimelinePage t={t} platformIsWindows={platformIsWindows} />}
          {page === "places" && <PlacesPage t={t} platformIsWindows={platformIsWindows} />}
          {page === "albums" && <AlbumsPage t={t} platformIsWindows={platformIsWindows} />}
          {page === "settings" && <SettingsPage t={t} status={status} onChanged={refreshStatus} />}
          {page === "activity" && <ActivityPage t={t} />}
        </main>
      </div>
    </div>
  );
}
