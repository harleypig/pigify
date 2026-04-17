import { useEffect, useState } from 'react'
import { apiService, FavoriteWriteBody } from '../services/api'
import './HeartButton.css'

interface HeartButtonProps {
  track: FavoriteWriteBody
  size?: 'sm' | 'md'
  /** Optional initial loved state for either service. */
  initialSpotifyLoved?: boolean | null
  initialLastfmLoved?: boolean | null
  /** Notify parent when state changes (so lists can update without refetching). */
  onChange?: (loved: boolean) => void
}

/**
 * Heart toggle that performs write-through love/unlove across all connected
 * services and reflects the aggregate loved state. The track is shown as
 * "loved" if it is loved on Spotify (the always-connected service).
 */
function HeartButton({
  track,
  size = 'md',
  initialSpotifyLoved,
  initialLastfmLoved,
  onChange,
}: HeartButtonProps) {
  const [spotifyLoved, setSpotifyLoved] = useState<boolean | null>(
    initialSpotifyLoved ?? null
  )
  const [lastfmLoved, setLastfmLoved] = useState<boolean | null>(
    initialLastfmLoved ?? null
  )
  const [busy, setBusy] = useState(false)
  const [statusMsg, setStatusMsg] = useState<string | null>(null)

  // If no initial state provided, query it once.
  useEffect(() => {
    if (initialSpotifyLoved !== undefined && initialLastfmLoved !== undefined) return
    if (!track.name || !track.artist) return
    let cancelled = false
    apiService
      .checkFavorites([
        { track_id: track.spotify_id ?? undefined, name: track.name, artist: track.artist },
      ])
      .then((res) => {
        if (cancelled) return
        const f = res[0]
        if (f) {
          setSpotifyLoved(f.sources.spotify ?? null)
          setLastfmLoved(f.sources.lastfm ?? null)
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [track.spotify_id, track.name, track.artist])

  const loved = spotifyLoved === true

  const toggle = async () => {
    if (busy) return
    setBusy(true)
    setStatusMsg(null)
    const next = !loved
    try {
      const res = next
        ? await apiService.loveTrack(track)
        : await apiService.unloveTrack(track)
      const sp = res.results.find((r) => r.service === 'spotify')
      const lf = res.results.find((r) => r.service === 'lastfm')
      if (sp?.ok) setSpotifyLoved(next)
      if (lf?.ok) setLastfmLoved(next)
      const failed = res.results.filter((r) => !r.skipped && !r.ok)
      if (failed.length > 0) {
        setStatusMsg(`Failed on ${failed.map((r) => r.service).join(', ')}`)
      }
      onChange?.(next)
    } catch (e) {
      setStatusMsg('Network error')
    } finally {
      setBusy(false)
    }
  }

  const title = (() => {
    const parts: string[] = []
    parts.push(`Spotify: ${spotifyLoved === null ? '?' : spotifyLoved ? 'loved' : 'not loved'}`)
    parts.push(`Last.fm: ${lastfmLoved === null ? 'n/a' : lastfmLoved ? 'loved' : 'not loved'}`)
    if (statusMsg) parts.push(statusMsg)
    return parts.join(' · ')
  })()

  return (
    <button
      type="button"
      className={`heart-btn heart-${size} ${loved ? 'is-loved' : ''} ${busy ? 'is-busy' : ''}`}
      onClick={(e) => {
        e.stopPropagation()
        toggle()
      }}
      title={title}
      aria-pressed={loved}
      aria-label={loved ? 'Unlove track' : 'Love track'}
      disabled={busy || !track.name || !track.artist}
    >
      {loved ? '♥' : '♡'}
    </button>
  )
}

export default HeartButton
