import { useState, useEffect } from 'react'
import { apiService, Playlist } from '../services/api'
import './PlaylistSelector.css'

interface PlaylistSelectorProps {
  onSelectPlaylist: (playlistId: string) => void
  selectedPlaylist: string | null
}

function PlaylistSelector({ onSelectPlaylist, selectedPlaylist }: PlaylistSelectorProps) {
  const [playlists, setPlaylists] = useState<Playlist[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadPlaylists()
  }, [])

  const loadPlaylists = async () => {
    try {
      setLoading(true)
      const data = await apiService.getPlaylists()
      setPlaylists(data)
      setError(null)
    } catch (err) {
      setError('Failed to load playlists')
      console.error('Error loading playlists:', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="playlist-selector">
        <div className="playlist-selector-header">
          <h2>Your Playlists</h2>
        </div>
        <div className="loading">Loading playlists...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="playlist-selector">
        <div className="playlist-selector-header">
          <h2>Your Playlists</h2>
        </div>
        <div className="error">{error}</div>
      </div>
    )
  }

  return (
    <div className="playlist-selector">
      <div className="playlist-selector-header">
        <h2>Your Playlists</h2>
      </div>
      <div className="playlist-list">
        {playlists.map((playlist) => (
          <div
            key={playlist.id}
            className={`playlist-item ${
              selectedPlaylist === playlist.id ? 'selected' : ''
            }`}
            onClick={() => onSelectPlaylist(playlist.id)}
          >
            <div className="playlist-image">
              {playlist.images && playlist.images.length > 0 ? (
                <img src={playlist.images[0].url} alt={playlist.name} />
              ) : (
                <div className="playlist-placeholder">♪</div>
              )}
            </div>
            <div className="playlist-info">
              <div className="playlist-name">{playlist.name}</div>
              <div className="playlist-meta">
                {playlist.track_count} tracks
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default PlaylistSelector

