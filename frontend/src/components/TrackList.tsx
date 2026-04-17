import { useState, useEffect } from 'react'
import { apiService, Track } from '../services/api'
import HeartButton from './HeartButton'
import './TrackList.css'

interface TrackListProps {
  playlistId: string
  onTrackSelect: (trackUri: string) => void
}

function TrackList({ playlistId, onTrackSelect }: TrackListProps) {
  const [tracks, setTracks] = useState<Track[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lovedMap, setLovedMap] = useState<Record<string, { spotify: boolean | null; lastfm: boolean | null }>>({})

  useEffect(() => {
    loadTracks()
  }, [playlistId])

  const loadTracks = async () => {
    try {
      setLoading(true)
      const data = await apiService.getPlaylistTracks(playlistId)
      setTracks(data)
      setError(null)
      // Bulk-fetch loved state in one round trip
      try {
        const favs = await apiService.checkFavorites(
          data.map((t) => ({
            track_id: t.id,
            name: t.name,
            artist: t.artists[0] ?? '',
          }))
        )
        const map: Record<string, { spotify: boolean | null; lastfm: boolean | null }> = {}
        favs.forEach((f, i) => {
          const id = data[i]?.id
          if (id) {
            map[id] = {
              spotify: (f.sources.spotify ?? null) as boolean | null,
              lastfm: (f.sources.lastfm ?? null) as boolean | null,
            }
          }
        })
        setLovedMap(map)
      } catch {
        /* non-fatal */
      }
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
            <div className="track-heart" onClick={(e) => e.stopPropagation()}>
              <HeartButton
                track={{
                  spotify_id: track.id,
                  spotify_uri: track.uri,
                  name: track.name,
                  artist: track.artists[0] ?? '',
                  album: track.album,
                  image_url: track.image_url,
                }}
                size="sm"
                initialSpotifyLoved={lovedMap[track.id]?.spotify}
                initialLastfmLoved={lovedMap[track.id]?.lastfm}
                onChange={(loved) =>
                  setLovedMap((m) => ({
                    ...m,
                    [track.id]: {
                      spotify: loved,
                      lastfm: m[track.id]?.lastfm ?? null,
                    },
                  }))
                }
              />
            </div>
            <div className="track-duration">{formatDuration(track.duration_ms)}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default TrackList

