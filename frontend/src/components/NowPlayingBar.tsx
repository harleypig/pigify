import { useState, useEffect } from 'react'
import { spotifyService } from '../services/spotify'
import './NowPlayingBar.css'

interface NowPlayingBarProps {
  trackUri: string | null
}

function NowPlayingBar({ trackUri }: NowPlayingBarProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentState, setCurrentState] = useState<any>(null)

  useEffect(() => {
    if (trackUri) {
      playTrack(trackUri)
    }
  }, [trackUri])

  useEffect(() => {
    const interval = setInterval(updateState, 1000)
    return () => clearInterval(interval)
  }, [])

  const playTrack = async (uri: string) => {
    try {
      await spotifyService.play(uri)
      setIsPlaying(true)
    } catch (error) {
      console.error('Error playing track:', error)
    }
  }

  const updateState = async () => {
    try {
      const state = await spotifyService.getCurrentState()
      setCurrentState(state)
      if (state) {
        setIsPlaying(!state.paused)
      }
    } catch {
      // silently ignore
    }
  }

  const handlePlayPause = async () => {
    try {
      if (isPlaying) {
        await spotifyService.pause()
        setIsPlaying(false)
      } else {
        await spotifyService.resume()
        setIsPlaying(true)
      }
    } catch (error) {
      console.error('Error toggling play/pause:', error)
    }
  }

  const track = currentState?.track_window?.current_track

  if (!track) {
    return (
      <div className="now-playing-bar">
        <span className="now-playing-idle">No track selected</span>
      </div>
    )
  }

  return (
    <div className="now-playing-bar">
      {track.album?.images?.[0]?.url && (
        <img
          src={track.album.images[0].url}
          alt={track.album?.name}
          className="now-playing-art"
        />
      )}
      <div className="now-playing-info">
        <span className="now-playing-title">{track.name}</span>
        <span className="now-playing-artist">
          {track.artists.map((a: any) => a.name).join(', ')}
        </span>
      </div>
      <button
        className="now-playing-btn"
        onClick={handlePlayPause}
        aria-label={isPlaying ? 'Pause' : 'Play'}
      >
        {isPlaying ? '⏸' : '▶'}
      </button>
    </div>
  )
}

export default NowPlayingBar
