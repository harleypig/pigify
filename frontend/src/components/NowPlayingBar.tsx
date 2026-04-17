import { useState, useEffect, useRef } from 'react'
import { apiService } from '../services/api'
import './NowPlayingBar.css'

interface NowPlayingBarProps {
  trackUri: string | null
}

/** Format remaining time as -M:SS */
function formatTimeLeft(progressMs: number, durationMs: number): string {
  const remainMs = Math.max(0, durationMs - progressMs)
  const totalSec = Math.floor(remainMs / 1000)
  const mins = Math.floor(totalSec / 60)
  const secs = totalSec % 60
  return `-${mins}:${String(secs).padStart(2, '0')}`
}

interface WaveformBarProps {
  bars: number[]
  progress: number // 0–1
}

/** SVG waveform — played portion in green, unplayed in dim gray */
function WaveformBar({ bars, progress }: WaveformBarProps) {
  if (bars.length === 0) return null
  const n = bars.length
  const barW = 0.7
  const gap = 1
  const totalW = n * gap
  const maxH = 20

  return (
    <svg
      className="progress-waveform"
      viewBox={`0 0 ${totalW} ${maxH}`}
      preserveAspectRatio="none"
      aria-hidden="true"
    >
      {bars.map((v, i) => {
        const h = Math.max(2, v * maxH)
        const x = i * gap
        const y = maxH - h
        const played = i / n <= progress
        return (
          <rect
            key={i}
            x={x}
            y={y}
            width={barW}
            height={h}
            fill={played ? '#1db954' : '#444'}
          />
        )
      })}
    </svg>
  )
}

function NowPlayingBar({ trackUri }: NowPlayingBarProps) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [track, setTrack] = useState<any>(null)
  const [durationMs, setDurationMs] = useState(0)
  const [waveform, setWaveform] = useState<number[]>([])

  // Smooth progress: sync from server, interpolate locally
  const syncedProgressRef = useRef(0)
  const syncedAtRef = useRef(Date.now())
  const isPlayingRef = useRef(false)
  const [displayProgress, setDisplayProgress] = useState(0) // 0–1

  const lastUriRef = useRef<string | null>(null)
  const lastTrackIdRef = useRef<string | null>(null)

  // Trigger playback when a track is selected from the playlist
  useEffect(() => {
    if (trackUri && trackUri !== lastUriRef.current) {
      lastUriRef.current = trackUri
      apiService.playTrack(trackUri).catch(console.error)
    }
  }, [trackUri])

  // Poll Spotify REST API every 2s for cross-device state
  useEffect(() => {
    const poll = async () => {
      try {
        const state = await apiService.getPlaybackState()
        const item = state?.item ?? null
        const playing = state?.is_playing ?? false
        const progressMs = state?.progress_ms ?? 0
        const durMs = item?.duration_ms ?? 0

        setTrack(item)
        setIsPlaying(playing)
        setDurationMs(durMs)

        syncedProgressRef.current = progressMs
        syncedAtRef.current = Date.now()
        isPlayingRef.current = playing

        if (durMs > 0) {
          setDisplayProgress(progressMs / durMs)
        }
      } catch {
        // leave as-is on error
      }
    }

    poll()
    const interval = setInterval(poll, 2000)
    return () => clearInterval(interval)
  }, [])

  // Local 100ms interpolation for smooth progress bar movement
  useEffect(() => {
    const timer = setInterval(() => {
      if (!isPlayingRef.current) return
      const elapsed = Date.now() - syncedAtRef.current
      const estimated = syncedProgressRef.current + elapsed
      const dur = durationMs || 1
      setDisplayProgress(Math.min(estimated / dur, 1))
    }, 100)
    return () => clearInterval(timer)
  }, [durationMs])

  // Fetch audio analysis when track changes
  useEffect(() => {
    if (!track?.id || track.id === lastTrackIdRef.current) return
    lastTrackIdRef.current = track.id
    setWaveform([])
    apiService
      .getAudioAnalysis(track.id)
      .then((data) => setWaveform(data.bars))
      .catch(() => setWaveform([]))
  }, [track?.id])

  const handlePlayPause = async () => {
    try {
      if (isPlaying) {
        await apiService.pausePlayback()
        setIsPlaying(false)
        isPlayingRef.current = false
      } else {
        await apiService.playTrack()
        setIsPlaying(true)
        isPlayingRef.current = true
      }
    } catch (e) {
      console.error('Play/pause error:', e)
    }
  }

  const handlePrevious = async () => {
    try { await apiService.previousTrack() } catch (e) { console.error(e) }
  }

  const handleNext = async () => {
    try { await apiService.nextTrack() } catch (e) { console.error(e) }
  }

  const albumArt = track?.album?.images?.[0]?.url
  const trackName = track?.name
  const artistNames = track?.artists?.map((a: any) => a.name).join(', ')
  const progressMs = durationMs > 0 ? displayProgress * durationMs : 0

  return (
    <div className="now-playing-bar">
      {/* Row 1: art · info · controls */}
      <div className="now-playing-row1">
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
          <button className="now-playing-ctrl-btn" onClick={handlePrevious} aria-label="Previous" disabled={!track}>⏮</button>
          <button className="now-playing-btn" onClick={handlePlayPause} aria-label={isPlaying ? 'Pause' : 'Play'} disabled={!track}>
            {isPlaying ? '⏸' : '▶'}
          </button>
          <button className="now-playing-ctrl-btn" onClick={handleNext} aria-label="Next" disabled={!track}>⏭</button>
        </div>
      </div>

      {/* Row 2: progress */}
      {track && durationMs > 0 && (
        <div className="now-playing-progress-row">
          <span className="progress-time-left">{formatTimeLeft(progressMs, durationMs)}</span>
          <span className="progress-pct">{Math.round(displayProgress * 100)}%</span>
          <div className="progress-bar-wrap">
            {waveform.length > 0 ? (
              <WaveformBar bars={waveform} progress={displayProgress} />
            ) : (
              <div className="progress-plain-track">
                <div className="progress-plain-fill" style={{ width: `${displayProgress * 100}%` }} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default NowPlayingBar
