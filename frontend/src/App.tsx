import { useState, useEffect } from 'react'
import Login from './components/Login'
import PlaylistSelector from './components/PlaylistSelector'
import TrackList from './components/TrackList'
import Player from './components/Player'
import { apiService } from './services/api'
import { spotifyService } from './services/spotify'
import './App.css'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState<any>(null)
  const [selectedPlaylist, setSelectedPlaylist] = useState<string | null>(null)
  const [currentTrack, setCurrentTrack] = useState<string | null>(null)

  useEffect(() => {
    checkAuth()
  }, [])

  const checkAuth = async () => {
    try {
      const userData = await apiService.getCurrentUser()
      setUser(userData)
      setIsAuthenticated(true)
      // Initialize Spotify Web SDK with access token
      await spotifyService.initialize()
      const token = await apiService.getAccessToken()
      await spotifyService.setAccessToken(token)
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
        <h1>Spotify Web App</h1>
        {user && (
          <div className="user-info">
            <span>{user.display_name}</span>
            <button onClick={handleLogout}>Logout</button>
          </div>
        )}
      </header>
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
      {currentTrack && (
        <Player trackUri={currentTrack} />
      )}
    </div>
  )
}

export default App

