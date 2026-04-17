import { useState, useEffect } from 'react'
import Login from './components/Login'
import PlaylistSelector from './components/PlaylistSelector'
import TrackList from './components/TrackList'
import NowPlayingBar from './components/NowPlayingBar'
import SettingsModal from './components/SettingsModal'
import TrackDetailModal from './components/TrackDetailModal'
import Settings from './components/Settings'
import { apiService } from './services/api'
import './App.css'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState<any>(null)
  const [selectedPlaylist, setSelectedPlaylist] = useState<string | null>(null)
  const [currentTrack, setCurrentTrack] = useState<string | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [detailTrackId, setDetailTrackId] = useState<string | null>(null)
  const [showFavoritesSettings, setShowFavoritesSettings] = useState(false)

  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    try {
      const userData = await apiService.getCurrentUser()
      setUser(userData)
      setIsAuthenticated(true)
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
      setSelectedPlaylist(null)
      setCurrentTrack(null)
    } catch (error) {
      console.error('Logout error:', error)
    }
  }

  if (!isAuthenticated) {
    return <Login onLogin={handleLogin} />
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1 className="app-title">Pigify</h1>
        <div className="app-header-center">
          <NowPlayingBar trackUri={currentTrack} onShowDetails={setDetailTrackId} />
        </div>
        {user && (
          <div className="user-info">
            <button
              className="user-name-btn"
              onClick={() => setSettingsOpen(true)}
              title="Open settings"
            >
              {user.display_name}
            </button>
            <button onClick={() => setShowFavoritesSettings(true)}>Favorites</button>
            <button onClick={handleLogout}>Logout</button>
          </div>
        )}
      </header>
      <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <TrackDetailModal trackId={detailTrackId} onClose={() => setDetailTrackId(null)} />
      <main className="app-main">
        <div className="sidebar">
          <PlaylistSelector
            onSelectPlaylist={setSelectedPlaylist}
            selectedPlaylist={selectedPlaylist}
          />
        </div>
        <div className="content">
          {selectedPlaylist && (
            <TrackList
              playlistId={selectedPlaylist}
              onTrackSelect={setCurrentTrack}
            />
          )}
        </div>
      </main>
      {showFavoritesSettings && <Settings onClose={() => setShowFavoritesSettings(false)} />}
    </div>
  )
}

export default App
