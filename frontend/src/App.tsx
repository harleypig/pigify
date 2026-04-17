import { useEffect, useState } from 'react'
import Login from './components/Login'
import PlaylistSelector from './components/PlaylistSelector'
import RecipesSidebar from './components/RecipesSidebar'
import TrackList from './components/TrackList'
import NowPlayingBar from './components/NowPlayingBar'
import SettingsPanel from './components/SettingsPanel'
import TrackInfoPanel from './components/TrackInfoPanel'
import UserMenu from './components/UserMenu'
import { apiService, Profile } from './services/api'
import './App.css'

const PANEL_COLLAPSED_KEY = 'pigify.trackInfoPanel.collapsed'
const SCROBBLE_DISMISS_KEY = 'pigify.scrobbleAlert.dismissed'
const SCROBBLE_QUEUE_THRESHOLD = 5
const SCROBBLE_STALE_MS = 60 * 60 * 1000 // 1 hour
const SCROBBLE_POLL_MS = 60 * 1000 // 60s

interface ScrobbleAlertState {
  queued: number
  oldestQueuedAt: string | null
}

function readDismissed(): ScrobbleAlertState | null {
  try {
    const raw = localStorage.getItem(SCROBBLE_DISMISS_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (
      parsed &&
      typeof parsed.queued === 'number' &&
      (parsed.oldestQueuedAt === null || typeof parsed.oldestQueuedAt === 'string')
    ) {
      return parsed
    }
  } catch {
    /* ignore */
  }
  return null
}

function pickAvatarUrl(
  images?: Array<{ url: string; height?: number; width?: number }> | null,
): string | null {
  if (!images || images.length === 0) return null
  const sized = images.filter((img) => typeof img.height === 'number')
  if (sized.length > 0) {
    const smallest = sized.reduce((a, b) =>
      (a.height ?? Infinity) <= (b.height ?? Infinity) ? a : b,
    )
    return smallest.url
  }
  return images[images.length - 1].url
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState<any>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [selectedPlaylist, setSelectedPlaylist] = useState<string | null>(null)
  const [currentTrack, setCurrentTrack] = useState<string | null>(null)
  const [settingsPanelOpen, setSettingsPanelOpen] = useState(false)
  const [settingsInitialTab, setSettingsInitialTab] = useState<
    'favorites' | 'connections' | 'about'
  >('favorites')
  const [scrobbleAlert, setScrobbleAlert] = useState<ScrobbleAlertState>({
    queued: 0,
    oldestQueuedAt: null,
  })
  const [bannerDismissed, setBannerDismissed] = useState<ScrobbleAlertState | null>(
    () => readDismissed(),
  )

  // Track Info Panel state
  const [nowPlayingTrackId, setNowPlayingTrackId] = useState<string | null>(null)
  const [panelOverrideTrackId, setPanelOverrideTrackId] = useState<string | null>(null)
  const [panelCollapsed, setPanelCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(PANEL_COLLAPSED_KEY) === '1'
    } catch {
      return false
    }
  })

  useEffect(() => {
    try {
      localStorage.setItem(PANEL_COLLAPSED_KEY, panelCollapsed ? '1' : '0')
    } catch {
      /* ignore */
    }
  }, [panelCollapsed])

  useEffect(() => {
    checkAuth()
  }, [])

  useEffect(() => {
    if (!isAuthenticated) {
      setScrobbleAlert({ queued: 0, oldestQueuedAt: null })
      return
    }
    let cancelled = false
    const poll = async () => {
      try {
        const status = await apiService.getLastfmStatus()
        const queued = status.status?.queued ?? 0
        let oldestQueuedAt: string | null = null
        if (queued > 0) {
          try {
            const q = await apiService.getLastfmQueue()
            for (const e of q.entries) {
              if (e.queued_at && (!oldestQueuedAt || e.queued_at < oldestQueuedAt)) {
                oldestQueuedAt = e.queued_at
              }
            }
          } catch {
            /* ignore queue read failure */
          }
        }
        if (!cancelled) setScrobbleAlert({ queued, oldestQueuedAt })
      } catch {
        /* not connected or transient failure */
      }
    }
    poll()
    const timer = window.setInterval(poll, SCROBBLE_POLL_MS)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [isAuthenticated])

  const checkAuth = async () => {
    try {
      const userData = await apiService.getCurrentUser()
      setUser(userData)
      setIsAuthenticated(true)
      try {
        const prof = await apiService.getProfile()
        setProfile(prof)
      } catch {
        setProfile(null)
      }
    } catch (error) {
      setIsAuthenticated(false)
    }
  }

  const handleLogin = () => {
    window.location.href = '/api/auth/spotify/login'
  }

  const handleLogout = async () => {
    try {
      await apiService.logout()
      setIsAuthenticated(false)
      setUser(null)
      setProfile(null)
      setSelectedPlaylist(null)
      setCurrentTrack(null)
      setPanelOverrideTrackId(null)
      setNowPlayingTrackId(null)
      setSettingsPanelOpen(false)
      setScrobbleAlert({ queued: 0, oldestQueuedAt: null })
    } catch (error) {
      console.error('Logout error:', error)
    }
  }

  // Effective track id displayed in the panel: explicit selection wins,
  // otherwise mirror the now-playing track.
  const panelTrackId = panelOverrideTrackId ?? nowPlayingTrackId

  const focusPanelOnNowPlaying = () => {
    setPanelOverrideTrackId(null)
    setPanelCollapsed(false)
  }

  const focusPanelOnTrack = (trackId: string) => {
    setPanelOverrideTrackId(trackId)
    setPanelCollapsed(false)
  }

  if (!isAuthenticated) {
    return <Login onLogin={handleLogin} />
  }

  const oldestStaleMs = scrobbleAlert.oldestQueuedAt
    ? Date.now() - new Date(scrobbleAlert.oldestQueuedAt).getTime()
    : 0
  const isStale = scrobbleAlert.queued > 0 && oldestStaleMs > SCROBBLE_STALE_MS
  const isOverThreshold = scrobbleAlert.queued > SCROBBLE_QUEUE_THRESHOLD
  const severe = isStale || isOverThreshold
  const alertSignatureChanged =
    !bannerDismissed ||
    scrobbleAlert.queued > bannerDismissed.queued ||
    scrobbleAlert.oldestQueuedAt !== bannerDismissed.oldestQueuedAt
  const showBanner = severe && alertSignatureChanged

  const openScrobbleQueue = () => {
    setSettingsInitialTab('connections')
    setSettingsPanelOpen(true)
  }
  const dismissBanner = () => {
    const snapshot = { ...scrobbleAlert }
    setBannerDismissed(snapshot)
    try {
      localStorage.setItem(SCROBBLE_DISMISS_KEY, JSON.stringify(snapshot))
    } catch {
      /* ignore */
    }
  }

  const badgeTitle =
    scrobbleAlert.queued > 0
      ? isStale
        ? `${scrobbleAlert.queued} pending scrobble${scrobbleAlert.queued === 1 ? '' : 's'} · oldest stuck for over 1h — click Settings to review`
        : `${scrobbleAlert.queued} pending scrobble${scrobbleAlert.queued === 1 ? '' : 's'} — click Settings to review`
      : undefined

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
                  scrobbleAlert.queued > 0 ? 'connections' : 'favorites',
                )
                setSettingsPanelOpen(true)
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
          className={`scrobble-banner ${isStale ? 'stale' : ''}`}
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
  )
}

export default App
