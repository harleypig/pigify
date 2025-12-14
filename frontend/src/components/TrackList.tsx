import { useState, useEffect } from 'react'
import { apiService, Track } from '../services/api'
import './TrackList.css'

interface TrackListProps {
  playlistId: string
  onTrackSelect: (trackUri: string) => void
}

function TrackList({ playlistId, onTrackSelect }: TrackListProps) {
  const [tracks, setTracks] = useState<Track[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadTracks()
  }, [playlistId])

  const loadTracks = async () => {
    try {
      setLoading(true)
      const data = await apiService.getPlaylistTracks(playlistId)
      setTracks(data)
      setError(null)
    } catch (err) {
      setError('Failed to load tracks')
      console.error('Error loading tracks:', err)
    } finally {
      setLoading(false)
    }
  }

  const formatDuration = (ms: number): string => {
    const seconds = Math.floor(ms / 1000)
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
  }

  if (loading) {
    return <div className="track-list-loading">Loading tracks...</div>
  }

  if (error) {
    return <div className="track-list-error">{error}</div>
  }

  return (
    <div className="track-list">
      <div className="track-list-header">
        <h2>Tracks</h2>
        <span className="track-count">{tracks.length} tracks</span>
      </div>
      <div className="track-list-items">
        {tracks.map((track, index) => (
          <div
            key={track.id}
            className="track-item"
            onClick={() => onTrackSelect(track.uri)}
          >
            <div className="track-number">{index + 1}</div>
            <div className="track-image">
              {track.image_url ? (
                <img src={track.image_url} alt={track.name} />
              ) : (
                <div className="track-placeholder">♪</div>
              )}
            </div>
            <div className="track-info">
              <div className="track-name">{track.name}</div>
              <div className="track-artists">
                {track.artists.join(', ')}
              </div>
            </div>
            <div className="track-album">{track.album}</div>
            <div className="track-duration">{formatDuration(track.duration_ms)}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default TrackList

