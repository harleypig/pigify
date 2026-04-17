import { useEffect, useRef, useState } from 'react'
import { apiService, FavoritesStatus } from '../services/api'
import './Settings.css'

interface SettingsProps {
  onClose: () => void
}

function Settings({ onClose }: SettingsProps) {
  const [status, setStatus] = useState<FavoritesStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [intervalDraft, setIntervalDraft] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const bgTimerRef = useRef<number | null>(null)

  const load = async () => {
    try {
      const data = await apiService.getFavoritesStatus()
      setStatus(data)
      setIntervalDraft(data.background_interval_minutes)
      setError(null)
    } catch (e) {
      setError('Failed to load settings')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  // Frontend-driven background sync (polling). Re-armed whenever status changes.
  useEffect(() => {
    if (bgTimerRef.current) {
      window.clearInterval(bgTimerRef.current)
      bgTimerRef.current = null
    }
    const minutes = status?.background_interval_minutes ?? 0
    if (minutes > 0) {
      bgTimerRef.current = window.setInterval(() => {
        apiService.syncFavorites().then((s) => {
          setStatus((prev) => (prev ? { ...prev, last_sync: s, pending_conflicts: s.conflicts } : prev))
        }).catch(() => {})
      }, minutes * 60 * 1000)
    }
    return () => {
      if (bgTimerRef.current) window.clearInterval(bgTimerRef.current)
    }
  }, [status?.background_interval_minutes])

  const runSync = async () => {
    setSyncing(true)
    try {
      const summary = await apiService.syncFavorites()
      setStatus((prev) =>
        prev ? { ...prev, last_sync: summary, pending_conflicts: summary.conflicts } : prev
      )
    } catch {
      setError('Sync failed')
    } finally {
      setSyncing(false)
    }
  }

  const saveInterval = async () => {
    try {
      const next = await apiService.updateFavoritesSettings(intervalDraft)
      setStatus(next)
    } catch {
      setError('Failed to save interval')
    }
  }

  const resolve = async (index: number, choice: 'love_both' | 'unlove_both' | 'keep') => {
    try {
      await apiService.resolveFavoriteConflict(index, choice)
      // Reload to get fresh ordering
      await load()
    } catch {
      setError('Failed to resolve conflict')
    }
  }

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="settings-header">
          <h2>Settings · Favorites Sync</h2>
          <button className="settings-close" onClick={onClose} aria-label="Close">×</button>
        </div>

        {loading && <p>Loading…</p>}
        {error && <p className="settings-error">{error}</p>}

        {status && (
          <>
            <section className="settings-section">
              <h3>Connections</h3>
              <ul className="settings-list">
                {status.connections.map((c) => (
                  <li key={c.service} className={`conn ${c.connected ? 'on' : 'off'}`}>
                    <span className="conn-name">{c.service}</span>
                    <span className="conn-state">
                      {c.connected ? `Connected${c.username ? ` as ${c.username}` : ''}` : 'Not connected'}
                    </span>
                    {c.detail && <span className="conn-detail">{c.detail}</span>}
                  </li>
                ))}
              </ul>
            </section>

            <section className="settings-section">
              <h3>Background sync</h3>
              <div className="settings-row">
                <label>
                  Interval (minutes, 0 to disable):{' '}
                  <input
                    type="number"
                    min={0}
                    max={1440}
                    value={intervalDraft}
                    onChange={(e) => setIntervalDraft(Number(e.target.value))}
                  />
                </label>
                <button onClick={saveInterval}>Save</button>
              </div>
              <div className="settings-row">
                <button onClick={runSync} disabled={syncing}>
                  {syncing ? 'Syncing…' : 'Sync now'}
                </button>
                {status.last_sync && (
                  <span className="settings-meta">
                    Last sync: {new Date(status.last_sync.ran_at).toLocaleString()} ·{' '}
                    Spotify {status.last_sync.spotify_count} · Last.fm {status.last_sync.lastfm_count} ·{' '}
                    Matched {status.last_sync.matched}
                    {status.last_sync.error ? ` · ${status.last_sync.error}` : ''}
                  </span>
                )}
              </div>
            </section>

            <section className="settings-section">
              <h3>Conflicts ({status.pending_conflicts.length})</h3>
              {status.pending_conflicts.length === 0 ? (
                <p className="settings-meta">No pending conflicts.</p>
              ) : (
                <ul className="conflict-list">
                  {status.pending_conflicts.map((c, i) => (
                    <li key={`${c.track.name}-${i}`} className="conflict-item">
                      <div className="conflict-info">
                        <strong>{c.track.name}</strong> — {c.track.artist}
                        <div className="conflict-meta">
                          Loved on: {c.loved_on.join(', ') || '—'} · Missing on: {c.not_loved_on.join(', ') || '—'}
                        </div>
                      </div>
                      <div className="conflict-actions">
                        <button onClick={() => resolve(i, 'love_both')} disabled={!c.track.spotify_id && c.not_loved_on.includes('spotify')}>
                          Love on both
                        </button>
                        <button onClick={() => resolve(i, 'unlove_both')}>Unlove on both</button>
                        <button onClick={() => resolve(i, 'keep')}>Keep as-is</button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  )
}

export default Settings
