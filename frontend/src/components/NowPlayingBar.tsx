import { useState, useEffect, useRef } from 'react'
import { apiService } from '../services/api'
import './NowPlayingBar.css'

interface NowPlayingBarProps {
  trackUri: string | null
}

function NowPlayingBar({ trackUri }: NowPlayingBarProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [track, setTrack] = useState<any>(null)
  const lastUriRef = useRef<string | null>(null)

  // When a track is selected from the playlist, play it
  useEffect(() => {
    if (trackUri && trackUri !== lastUriRef.current) {
      lastUriRef.current = trackUri
      apiService.playTrack(trackUri).catch(console.error)
    }
  }, [trackUri])

  // Poll Spotify REST API for cross-device playback state
  useEffect(() => {
    const poll = async () => {
      try {
        const state = await apiService.getPlaybackState()
        setTrack(state?.item ?? null)
        setIsPlaying(state?.is_playing ?? false)
      } catch {
        // no active session or error — leave as-is
      }
    }

    poll()
    const interval = setInterval(poll, 2000)
    return () => clearInterval(interval)
  }, [])

  const handlePlayPause = async () => {
    try {
      if (isPlaying) {
        await apiService.pausePlayback()
        setIsPlaying(false)
      } else {
        await apiService.playTrack()
        setIsPlaying(true)
      }
    } catch (e) {
      console.error('Play/pause error:', e)
    }
  }

  const handlePrevious = async () => {
    try {
      await apiService.previousTrack()
    } catch (e) {
      console.error('Previous error:', e)
    }
  }

  const handleNext = async () => {
    try {
      await apiService.nextTrack()
    } catch (e) {
      console.error('Next error:', e)
    }
  }

  const albumArt = track?.album?.images?.[0]?.url
  const trackName = track?.name
  const artistNames = track?.artists?.map((a: any) => a.name).join(', ')

  return (
    <div className="now-playing-bar">
      {albumArt ? (
        <img src={albumArt} alt={track?.album?.name} className="now-playing-art" />
      ) : (
        <div className="now-playing-art-placeholder" />
      )}

      <div className="now-playing-info">
        {trackName ? (
          <>
            <span className="now-playing-title">{trackName}</span>
            <span className="now-playing-artist">{artistNames}</span>
          </>
        ) : (
          <span className="now-playing-idle">Nothing playing</span>
        )}
      </div>

      <div className="now-playing-controls">
        <button
          className="now-playing-ctrl-btn"
          onClick={handlePrevious}
          aria-label="Previous"
          disabled={!track}
        >
          ⏮
        </button>
        <button
          className="now-playing-btn"
          onClick={handlePlayPause}
          aria-label={isPlaying ? 'Pause' : 'Play'}
          disabled={!track}
        >
          {isPlaying ? '⏸' : '▶'}
        </button>
        <button
          className="now-playing-ctrl-btn"
          onClick={handleNext}
          aria-label="Next"
          disabled={!track}
        >
          ⏭
        </button>
      </div>
    </div>
  )
}

export default NowPlayingBar
