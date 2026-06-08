import { useCallback, useEffect, useState } from "react";
import {
  evaluateScrobbleAlert,
  pickAvatarUrl,
  readDismissed,
  SCROBBLE_DISMISS_KEY,
  type ScrobbleAlertState,
  scrobbleBadgeTitle,
} from "./App.helpers";
import Login from "./components/Login";
import NowPlayingBar from "./components/NowPlayingBar";
import PlaylistSelector from "./components/PlaylistSelector";
import RecipesSidebar from "./components/RecipesSidebar";
import SettingsPanel from "./components/SettingsPanel";
import TrackInfoPanel from "./components/TrackInfoPanel";
import TrackList from "./components/TrackList";
import UserMenu from "./components/UserMenu";
import { apiService, type Profile, type User } from "./services/api";
import "./App.css";

const PANEL_COLLAPSED_KEY = "pigify.trackInfoPanel.collapsed";
const SCROBBLE_POLL_MS = 60 * 1000; // 60s

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [selectedPlaylist, setSelectedPlaylist] = useState<string | null>(null);
  const [currentTrack, setCurrentTrack] = useState<string | null>(null);
  const [settingsPanelOpen, setSettingsPanelOpen] = useState(false);
  const [settingsInitialTab, setSettingsInitialTab] = useState<
    "favorites" | "connections" | "about"
  >("favorites");
  const [scrobbleAlert, setScrobbleAlert] = useState<ScrobbleAlertState>({
    queued: 0,
    oldestQueuedAt: null,
  });
  const [bannerDismissed, setBannerDismissed] =
    useState<ScrobbleAlertState | null>(() => readDismissed());

  // Track Info Panel state
  const [nowPlayingTrackId, setNowPlayingTrackId] = useState<string | null>(
    null,
  );
  const [panelOverrideTrackId, setPanelOverrideTrackId] = useState<
    string | null
  >(null);
  const [panelCollapsed, setPanelCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(PANEL_COLLAPSED_KEY) === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(PANEL_COLLAPSED_KEY, panelCollapsed ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [panelCollapsed]);

  const checkAuth = useCallback(async () => {
    try {
      const userData = await apiService.getCurrentUser();
      setUser(userData);
      setIsAuthenticated(true);
      try {
        const prof = await apiService.getProfile();
        setProfile(prof);
      } catch {
        setProfile(null);
      }
    } catch (_error) {
      setIsAuthenticated(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    if (!isAuthenticated) {
      setScrobbleAlert({ queued: 0, oldestQueuedAt: null });
      return;
    }
    let cancelled = false;
    const poll = async () => {
      try {
        const status = await apiService.getLastfmStatus();
        const queued = status.status?.queued ?? 0;
        let oldestQueuedAt: string | null = null;
        if (queued > 0) {
          try {
            const q = await apiService.getLastfmQueue();
            for (const e of q.entries) {
              if (
                e.queued_at &&
                (!oldestQueuedAt || e.queued_at < oldestQueuedAt)
              ) {
                oldestQueuedAt = e.queued_at;
              }
            }
          } catch {
            /* ignore queue read failure */
          }
        }
        if (!cancelled) setScrobbleAlert({ queued, oldestQueuedAt });
      } catch {
        /* not connected or transient failure */
      }
    };
    poll();
    const timer = window.setInterval(poll, SCROBBLE_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [isAuthenticated]);

  const handleLogin = () => {
    window.location.href = "/api/auth/spotify/login";
  };

  const handleLogout = async () => {
    try {
      await apiService.logout();
      setIsAuthenticated(false);
      setUser(null);
      setProfile(null);
      setSelectedPlaylist(null);
      setCurrentTrack(null);
      setPanelOverrideTrackId(null);
      setNowPlayingTrackId(null);
      setSettingsPanelOpen(false);
      setScrobbleAlert({ queued: 0, oldestQueuedAt: null });
    } catch (error) {
      console.error("Logout error:", error);
    }
  };

  // Effective track id displayed in the panel: explicit selection wins,
  // otherwise mirror the now-playing track.
  const panelTrackId = panelOverrideTrackId ?? nowPlayingTrackId;

  const focusPanelOnNowPlaying = () => {
    setPanelOverrideTrackId(null);
    setPanelCollapsed(false);
  };

  const focusPanelOnTrack = (trackId: string) => {
    setPanelOverrideTrackId(trackId);
    setPanelCollapsed(false);
  };

  if (!isAuthenticated) {
    return <Login onLogin={handleLogin} />;
  }

  const { isStale, showBanner } = evaluateScrobbleAlert(
    scrobbleAlert,
    bannerDismissed,
    Date.now(),
  );

  const openScrobbleQueue = () => {
    setSettingsInitialTab("connections");
    setSettingsPanelOpen(true);
  };
  const dismissBanner = () => {
    const snapshot = { ...scrobbleAlert };
    setBannerDismissed(snapshot);
    try {
      localStorage.setItem(SCROBBLE_DISMISS_KEY, JSON.stringify(snapshot));
    } catch {
      /* ignore */
    }
  };

  const badgeTitle = scrobbleBadgeTitle(scrobbleAlert, isStale);

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">Pigify</h1>
        <div className="app-header-center">
          <NowPlayingBar
            trackUri={currentTrack}
            onShowDetails={focusPanelOnNowPlaying}
            onTrackChange={setNowPlayingTrackId}
          />
        </div>
        {user && (
          <div className="user-info">
            <UserMenu
              label={profile?.display_name ?? user.display_name}
              imageUrl={pickAvatarUrl(user.images)}
              onOpenSettings={() => {
                setSettingsInitialTab(
                  scrobbleAlert.queued > 0 ? "connections" : "favorites",
                );
                setSettingsPanelOpen(true);
              }}
              onLogout={handleLogout}
              badgeCount={scrobbleAlert.queued}
              badgeTitle={badgeTitle}
            />
          </div>
        )}
      </header>
      {showBanner && (
        <div
          className={`scrobble-banner ${isStale ? "stale" : ""}`}
          role="status"
          aria-live="polite"
        >
          <span className="scrobble-banner-text">
            {isStale
              ? `Some Last.fm scrobbles have been stuck for over an hour (${scrobbleAlert.queued} pending).`
              : `${scrobbleAlert.queued} Last.fm scrobbles are waiting to be sent.`}
          </span>
          <div className="scrobble-banner-actions">
            <button
              type="button"
              className="scrobble-banner-btn"
              onClick={openScrobbleQueue}
            >
              Review queue
            </button>
            <button
              type="button"
              className="scrobble-banner-dismiss"
              onClick={dismissBanner}
              aria-label="Dismiss"
              title="Dismiss"
            >
              ×
            </button>
          </div>
        </div>
      )}
      <main className="app-main">
        <div className="sidebar">
          <PlaylistSelector
            onSelectPlaylist={setSelectedPlaylist}
            selectedPlaylist={selectedPlaylist}
          />
          <RecipesSidebar />
        </div>
        <div className="content">
          {/* Settings lives in the main content panel rather than a floating
              overlay — opening it temporarily takes over the track list area
              and is dismissed back to the playlist via its × button. */}
          {settingsPanelOpen ? (
            <SettingsPanel
              onClose={() => setSettingsPanelOpen(false)}
              onProfileChange={setProfile}
              initialTab={settingsInitialTab}
            />
          ) : (
            selectedPlaylist && (
              <TrackList
                playlistId={selectedPlaylist}
                onTrackSelect={setCurrentTrack}
                onTrackFocus={focusPanelOnTrack}
              />
            )
          )}
        </div>
      </main>
      <TrackInfoPanel
        trackId={panelTrackId}
        collapsed={panelCollapsed}
        onToggleCollapsed={() => setPanelCollapsed((c) => !c)}
      />
    </div>
  );
}

export default App;
