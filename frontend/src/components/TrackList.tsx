import { useEffect, useMemo, useState, useCallback } from 'react'
import {
  apiService,
  Track,
  SortField,
  SortPreset,
} from '../services/api'
import {
  sortTracks,
  requiredSources,
  SortableHydration,
} from '../services/sortEngine'
import SortMenu, { SortSpec } from './SortMenu'
import HeartButton from './HeartButton'
import './TrackList.css'

interface TrackListProps {
  playlistId: string
  onTrackSelect: (trackUri: string) => void
  onTrackFocus?: (trackId: string) => void
}

const DEFAULT_SORT: SortSpec = {
  keys: [{ field: 'added_at', direction: 'desc' }],
}

function TrackList({ playlistId, onTrackSelect, onTrackFocus }: TrackListProps) {
  const [tracks, setTracks] = useState<Track[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lovedMap, setLovedMap] = useState<
    Record<string, { spotify: boolean | null; lastfm: boolean | null }>
  >({})

  // Sort state
  const [fields, setFields] = useState<SortField[]>([])
  const [presets, setPresets] = useState<SortPreset[]>([])
  const [sortSpec, setSortSpec] = useState<SortSpec>(DEFAULT_SORT)
  const [hydration, setHydration] = useState<SortableHydration>({
    audio_features: {},
    lastfm: {},
  })
  const [warnings, setWarnings] = useState<string[]>([])
  const [hydrating, setHydrating] = useState(false)
  const [applying, setApplying] = useState(false)
  const [undoAvailable, setUndoAvailable] = useState(false)

  // Load fields/presets once.
  useEffect(() => {
    apiService.getSortFields().then((r) => setFields(r.fields)).catch(() => {})
    apiService.listSortPresets().then(setPresets).catch(() => {})
  }, [])

  // Load tracks + undo status when playlist changes.
  useEffect(() => {
    loadTracks()
    refreshUndoStatus()
    setHydration({ audio_features: {}, lastfm: {} })
    setWarnings([])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playlistId])

  const loadTracks = async () => {
    try {
      setLoading(true)
      const data = await apiService.getAllPlaylistTracks(playlistId)
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

  const refreshUndoStatus = async () => {
    try {
      const r = await apiService.getUndoStatus(playlistId)
      setUndoAvailable(r.available)
    } catch {
      setUndoAvailable(false)
    }
  }

  // Hydrate when sort spec needs data we don't have.
  const ensureHydration = useCallback(
    async (spec: SortSpec) => {
      if (fields.length === 0 || tracks.length === 0) return
      const sources = requiredSources(fields, spec.keys)
      if (sources.length === 0) return

      const missing: typeof sources = []
      for (const src of sources) {
        const map = hydration[src]
        const need = tracks.some((t) => !(t.id in map))
        if (need) missing.push(src)
      }
      if (missing.length === 0) return

      try {
        setHydrating(true)
        const meta = tracks.map((t) => ({
          id: t.id,
          name: t.name,
          artist: t.artists[0] ?? '',
        }))
        const ids = tracks.map((t) => t.id).filter(Boolean)
        const r = await apiService.hydrateTracks(playlistId, ids, missing, meta)
        setHydration((prev) => ({
          audio_features: { ...prev.audio_features, ...r.audio_features },
          lastfm: { ...prev.lastfm, ...r.lastfm },
        }))
        setWarnings(r.warnings || [])
      } catch (e) {
        console.error('Hydration failed:', e)
        setWarnings(['Failed to fetch extra data for sort'])
      } finally {
        setHydrating(false)
      }
    },
    [fields, tracks, hydration, playlistId]
  )

  useEffect(() => {
    ensureHydration(sortSpec)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sortSpec, fields, tracks])

  const sortedTracks = useMemo(() => {
    if (fields.length === 0) return tracks
    return sortTracks(tracks, fields, sortSpec.keys, hydration)
  }, [tracks, fields, sortSpec, hydration])

  const handleSavePreset = async (preset: SortPreset) => {
    try {
      const updated = await apiService.saveSortPreset(preset)
      setPresets(updated)
    } catch (e) {
      console.error('Save preset failed:', e)
    }
  }

  const handleDeletePreset = async (name: string) => {
    try {
      const updated = await apiService.deleteSortPreset(name)
      setPresets(updated)
    } catch (e) {
      console.error('Delete preset failed:', e)
    }
  }

  const handleApplyView = () => {
    /* sorted view is already shown */
  }

  const handleApplyToPlaylist = async () => {
    if (!sortedTracks.length) return
    if (
      !window.confirm(
        `This will rewrite the playlist on Spotify in the new order (${sortedTracks.length} tracks). You can undo it once. Continue?`
      )
    )
      return
    try {
      setApplying(true)
      const targetUris = sortedTracks.map((t) => t.uri)
      const result = await apiService.reorderPlaylist(playlistId, targetUris)
      setUndoAvailable(result.undo_available)
      await loadTracks()
    } catch (e) {
      console.error('Apply to playlist failed:', e)
      alert('Failed to reorder playlist on Spotify.')
    } finally {
      setApplying(false)
    }
  }

  const handleUndo = async () => {
    try {
      setApplying(true)
      await apiService.undoReorder(playlistId)
      setUndoAvailable(false)
      await loadTracks()
    } catch (e) {
      console.error('Undo failed:', e)
      alert('Undo failed.')
    } finally {
      setApplying(false)
    }
  }

  const formatDuration = (ms: number): string => {
    const seconds = Math.floor(ms / 1000)
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
  }

  if (loading) {
    return <div className="track-list-loading">Loading tracks…</div>
  }

  if (error) {
    return <div className="track-list-error">{error}</div>
  }

  return (
    <div className="track-list">
      <div className="track-list-header">
        <div>
          <h2>Tracks</h2>
          <span className="track-count">
            {sortedTracks.length} tracks
            {hydrating && <span className="hydrating-tag"> · loading sort data…</span>}
          </span>
        </div>
        <SortMenu
          fields={fields}
          presets={presets}
          current={sortSpec}
          onChange={setSortSpec}
          onSavePreset={handleSavePreset}
          onDeletePreset={handleDeletePreset}
          onApplyView={handleApplyView}
          onApplyToPlaylist={handleApplyToPlaylist}
          onUndo={handleUndo}
          applying={applying}
          undoAvailable={undoAvailable}
          warnings={warnings}
        />
      </div>
      <div className="track-list-items">
        {sortedTracks.map((track, index) => (
          /* The row is rendered as a div with role="button" rather than a real
             <button> because it contains another interactive child (HeartButton),
             and nesting buttons is invalid HTML. We provide keyboard equivalents
             (Enter / Space) and an aria-label so this is still operable.
             Long playlists are not virtualized — the typical Pigify use case is
             a few hundred rows, well within what the DOM handles smoothly. */
          <div
            key={`${track.id}-${index}`}
            className="track-item"
            role="button"
            tabIndex={0}
            aria-label={`Play ${track.name} by ${track.artists.join(', ')}`}
            onClick={() => {
              onTrackSelect(track.uri)
              onTrackFocus?.(track.id)
            }}
            onKeyDown={(e) => {
              // Only act when the row itself is focused — ignore Enter/Space
              // forwarded from the nested HeartButton or any other inner
              // control, otherwise toggling the heart would also trigger
              // playback of the track.
              if (e.target !== e.currentTarget) return
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onTrackSelect(track.uri)
                onTrackFocus?.(track.id)
              }
            }}
          >
            <div className="track-number">{index + 1}</div>
            <div className="track-image">
              {track.image_url ? (
                /* Explicit dimensions match the .track-image CSS box and
                   prevent CLS as rows scroll into view. */
                <img
                  src={track.image_url}
                  alt=""
                  width={40}
                  height={40}
                  loading="lazy"
                  decoding="async"
                />
              ) : (
                <div className="track-placeholder" aria-hidden="true">♪</div>
              )}
            </div>
            <div className="track-info">
              <div className="track-name">{track.name}</div>
              <div className="track-artists">
                {track.artists.join(', ')}
              </div>
            </div>
            <div className="track-album">{track.album}</div>
            {/* stopPropagation prevents heart clicks from triggering the
                row-level "play this track" handler. */}
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
