import { useEffect, useState } from 'react'
import Login from './components/Login'
import PlaylistSelector from './components/PlaylistSelector'
import RecipesSidebar from './components/RecipesSidebar'
import TrackList from './components/TrackList'
import NowPlayingBar from './components/NowPlayingBar'
import SettingsModal from './components/SettingsModal'
import TrackInfoPanel from './components/TrackInfoPanel'
import Settings from './components/Settings'
import { apiService, Profile } from './services/api'
import './App.css'

const PANEL_COLLAPSED_KEY = 'pigify.trackInfoPanel.collapsed'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState<any>(null)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [selectedPlaylist, setSelectedPlaylist] = useState<string | null>(null)
  const [currentTrack, setCurrentTrack] = useState<string | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [showFavoritesSettings, setShowFavoritesSettings] = useState(false)

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
            <button
              className="user-name-btn"
              onClick={() => setSettingsOpen(true)}
              title="Open settings"
            >
              {profile?.display_name ?? user.display_name}
            </button>
            <button onClick={() => setShowFavoritesSettings(true)}>Favorites</button>
            <button onClick={handleLogout}>Logout</button>
          </div>
        )}
      </header>
      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onProfileChange={setProfile}
      />
      <main className="app-main">
        <div className="sidebar">
          <PlaylistSelector
            onSelectPlaylist={setSelectedPlaylist}
            selectedPlaylist={selectedPlaylist}
          />
          <RecipesSidebar />
        </div>
        <div className="content">
          {selectedPlaylist && (
            <TrackList
              playlistId={selectedPlaylist}
              onTrackSelect={setCurrentTrack}
              onTrackFocus={focusPanelOnTrack}
            />
          )}
        </div>
      </main>
      <TrackInfoPanel
        trackId={panelTrackId}
        collapsed={panelCollapsed}
        onToggleCollapsed={() => setPanelCollapsed((c) => !c)}
      />
      {showFavoritesSettings && <Settings onClose={() => setShowFavoritesSettings(false)} />}
    </div>
  )
}

export default App
