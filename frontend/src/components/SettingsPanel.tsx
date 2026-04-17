import { useEffect, useRef, useState } from 'react'
import {
  apiService,
  ConnectionStatus,
  FavoritesStatus,
  LastfmQueueEntry,
  LastfmQueueFlushResult,
  LastfmStatus,
  Profile,
} from '../services/api'
import './SettingsPanel.css'

type TabId = 'favorites' | 'connections'

interface Props {
  onClose: () => void
  onProfileChange?: (profile: Profile) => void
  initialTab?: TabId
}

interface TabDef {
  id: TabId
  label: string
}

const TABS: TabDef[] = [
  { id: 'favorites', label: 'Favorites' },
  { id: 'connections', label: 'Connections' },
]

function tierLabel(tier: string): string {
  if (tier === 'authenticated') return 'Connected'
  if (tier === 'public') return 'Public access only'
  return 'Unavailable'
}

function tierClass(tier: string): string {
  if (tier === 'authenticated') return 'tier-ok'
  if (tier === 'public') return 'tier-public'
  return 'tier-none'
}

function SettingsPanel({ onClose, onProfileChange, initialTab = 'favorites' }: Props) {
  const [activeTab, setActiveTab] = useState<TabId>(initialTab)

  useEffect(() => {
    setActiveTab(initialTab)
  }, [initialTab])

  return (
    <aside className="settings-panel" aria-label="Settings">
      <header className="sp-header">
        <span className="sp-title-tag">Settings</span>
        <button
          className="sp-close"
          onClick={onClose}
          aria-label="Close settings"
          title="Close settings"
        >
          ×
        </button>
      </header>
      <div className="sp-tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={activeTab === t.id}
            className={`sp-tab ${activeTab === t.id ? 'active' : ''}`}
            onClick={() => setActiveTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="sp-body">
        <div hidden={activeTab !== 'favorites'} role="tabpanel">
          <FavoritesTab />
        </div>
        <div hidden={activeTab !== 'connections'} role="tabpanel">
          <ConnectionsTab onProfileChange={onProfileChange} />
        </div>
      </div>
    </aside>
  )
}

function FavoritesTab() {
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
    } catch {
      setError('Failed to load settings')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    if (bgTimerRef.current) {
      window.clearInterval(bgTimerRef.current)
      bgTimerRef.current = null
    }
    const minutes = status?.background_interval_minutes ?? 0
    if (minutes > 0) {
      bgTimerRef.current = window.setInterval(() => {
        apiService
          .syncFavorites()
          .then((s) => {
            setStatus((prev) =>
              prev ? { ...prev, last_sync: s, pending_conflicts: s.conflicts } : prev
            )
          })
          .catch(() => {})
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

  const resolve = async (
    index: number,
    choice: 'love_both' | 'unlove_both' | 'keep'
  ) => {
    try {
      await apiService.resolveFavoriteConflict(index, choice)
      await load()
    } catch {
      setError('Failed to resolve conflict')
    }
  }

  return (
    <div className="sp-tabpanel">
      {loading && <p className="sp-meta">Loading…</p>}
      {error && <p className="sp-error">{error}</p>}

      {status && (
        <>
          <section className="sp-section">
            <h3>Sync sources</h3>
            <ul className="sp-list">
              {status.connections.map((c) => (
                <li key={c.service} className={`sp-conn ${c.connected ? 'on' : 'off'}`}>
                  <span className="sp-conn-name">{c.service}</span>
                  <span className="sp-conn-state">
                    {c.connected
                      ? `Connected${c.username ? ` as ${c.username}` : ''}`
                      : 'Not connected'}
                  </span>
                  {c.detail && <span className="sp-conn-detail">{c.detail}</span>}
                </li>
              ))}
            </ul>
          </section>

          <section className="sp-section">
            <h3>Background sync</h3>
            <div className="sp-row">
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
              <button className="sp-btn" onClick={saveInterval}>
                Save
              </button>
            </div>
            <div className="sp-row">
              <button className="sp-btn" onClick={runSync} disabled={syncing}>
                {syncing ? 'Syncing…' : 'Sync now'}
              </button>
              {status.last_sync && (
                <span className="sp-meta">
                  Last sync: {new Date(status.last_sync.ran_at).toLocaleString()} ·{' '}
                  Spotify {status.last_sync.spotify_count} · Last.fm{' '}
                  {status.last_sync.lastfm_count} · Matched {status.last_sync.matched}
                  {status.last_sync.error ? ` · ${status.last_sync.error}` : ''}
                </span>
              )}
            </div>
          </section>

          <section className="sp-section">
            <h3>Conflicts ({status.pending_conflicts.length})</h3>
            {status.pending_conflicts.length === 0 ? (
              <p className="sp-meta">No pending conflicts.</p>
            ) : (
              <ul className="sp-conflict-list">
                {status.pending_conflicts.map((c, i) => (
                  <li key={`${c.track.name}-${i}`} className="sp-conflict-item">
                    <div className="sp-conflict-info">
                      <strong>{c.track.name}</strong> — {c.track.artist}
                      <div className="sp-conflict-meta">
                        Loved on: {c.loved_on.join(', ') || '—'} · Missing on:{' '}
                        {c.not_loved_on.join(', ') || '—'}
                      </div>
                    </div>
                    <div className="sp-conflict-actions">
                      <button
                        className="sp-btn"
                        onClick={() => resolve(i, 'love_both')}
                        disabled={
                          !c.track.spotify_id && c.not_loved_on.includes('spotify')
                        }
                      >
                        Love on both
                      </button>
                      <button className="sp-btn" onClick={() => resolve(i, 'unlove_both')}>
                        Unlove on both
                      </button>
                      <button className="sp-btn" onClick={() => resolve(i, 'keep')}>
                        Keep as-is
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </div>
  )
}

interface ConnectionsTabProps {
  onProfileChange?: (profile: Profile) => void
}

function ConnectionsTab({ onProfileChange }: ConnectionsTabProps) {
  const [connections, setConnections] = useState<Record<string, ConnectionStatus>>({})
  const [lastfmStatus, setLastfmStatus] = useState<LastfmStatus>({})
  const [loading, setLoading] = useState(false)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [nameInput, setNameInput] = useState('')
  const [savingName, setSavingName] = useState(false)
  const [nameStatus, setNameStatus] = useState<string | null>(null)

  const refresh = async () => {
    setLoading(true)
    try {
      const [conns, prof] = await Promise.all([
        apiService.getConnections(),
        apiService.getProfile(),
      ])
      setConnections(conns)
      setProfile(prof)
      setNameInput(prof.custom_display_name ?? '')
      if (conns.lastfm && conns.lastfm.tier !== 'none') {
        try {
          const s = await apiService.getLastfmStatus()
          setLastfmStatus(s.status || {})
        } catch {
          setLastfmStatus({})
        }
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  const saveName = async () => {
    setSavingName(true)
    setNameStatus(null)
    try {
      const trimmed = nameInput.trim()
      const updated = await apiService.updateProfile(trimmed === '' ? null : trimmed)
      setProfile(updated)
      setNameInput(updated.custom_display_name ?? '')
      setNameStatus('Saved')
      onProfileChange?.(updated)
    } catch {
      setNameStatus('Failed to save')
    } finally {
      setSavingName(false)
    }
  }

  const lastfm = connections.lastfm
  const mb = connections.musicbrainz

  return (
    <div className="sp-tabpanel">
      {loading && <p className="sp-meta">Loading…</p>}

      {profile && (
        <section className="sp-card">
          <header>
            <h3>Profile</h3>
          </header>
          <p className="sp-meta">
            Pick how Pigify labels you in the header. Leave empty to use your Spotify
            user id.
          </p>
          <div className="sp-row">
            <input
              type="text"
              className="sp-input"
              value={nameInput}
              onChange={(e) => {
                setNameInput(e.target.value)
                setNameStatus(null)
              }}
              placeholder={profile.spotify_id}
              maxLength={255}
              aria-label="Display name"
            />
            <button
              className="sp-btn-primary"
              onClick={saveName}
              disabled={
                savingName ||
                nameInput.trim() === (profile.custom_display_name ?? '')
              }
            >
              {savingName ? 'Saving…' : 'Save'}
            </button>
          </div>
          {nameStatus && <p className="sp-meta">{nameStatus}</p>}
        </section>
      )}

      {lastfm && lastfm.tier !== 'none' && (
        <section className="sp-card">
          <header>
            <h3>Last.fm</h3>
            <span className={`sp-tier-pill ${tierClass(lastfm.tier)}`}>
              {tierLabel(lastfm.tier)}
            </span>
          </header>
          {lastfm.tier === 'authenticated' ? (
            <>
              <p className="sp-meta">
                Signed in as <strong>{lastfm.connected_account}</strong>. Plays will be
                scrobbled automatically.
              </p>
              <p className="sp-meta">
                Last scrobble:{' '}
                {lastfmStatus.last_scrobble_at
                  ? new Date(lastfmStatus.last_scrobble_at * 1000).toLocaleTimeString()
                  : 'none yet'}
                {lastfmStatus.queued ? ` · ${lastfmStatus.queued} queued` : ''}
              </p>
              <button
                className="sp-btn-danger"
                onClick={async () => {
                  await apiService.disconnectLastfm()
                  refresh()
                }}
              >
                Disconnect
              </button>
              <LastfmQueuePanel />
            </>
          ) : (
            <>
              <p className="sp-meta">
                Tags, similar tracks and global play counts work without signing in.
                Connect your Last.fm account to scrobble plays and see your personal
                play counts.
              </p>
              <a className="sp-btn-primary" href="/api/integrations/lastfm/login">
                Connect Last.fm
              </a>
            </>
          )}
        </section>
      )}

      {mb && mb.tier !== 'none' && (
        <section className="sp-card">
          <header>
            <h3>MusicBrainz</h3>
            <span className={`sp-tier-pill ${tierClass(mb.tier)}`}>
              {tierLabel(mb.tier)}
            </span>
          </header>
          <p className="sp-meta">
            MusicBrainz is fully public. Track identifiers, releases and credits are
            fetched automatically — no account needed.
          </p>
        </section>
      )}
    </div>
  )
}

function formatRelative(iso?: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return '—'
  const diff = Date.now() - d.getTime()
  const sec = Math.round(diff / 1000)
  if (sec < 60) return `${sec}s ago`
  if (sec < 3600) return `${Math.round(sec / 60)}m ago`
  if (sec < 86400) return `${Math.round(sec / 3600)}h ago`
  return d.toLocaleString()
}

function LastfmQueuePanel() {
  const [entries, setEntries] = useState<LastfmQueueEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [flushResult, setFlushResult] = useState<LastfmQueueFlushResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = async () => {
    setLoading(true)
    try {
      const data = await apiService.getLastfmQueue()
      setEntries(data.entries)
      setError(null)
    } catch {
      setError('Failed to load queue')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const flush = async () => {
    setBusy(true)
    setFlushResult(null)
    try {
      const result = await apiService.flushLastfmQueue()
      setFlushResult(result)
      await load()
    } catch {
      setError('Retry failed')
    } finally {
      setBusy(false)
    }
  }

  const remove = async (id: number) => {
    setBusy(true)
    try {
      await apiService.deleteLastfmQueueEntry(id)
      setEntries((prev) => prev.filter((e) => e.id !== id))
    } catch {
      setError('Failed to delete entry')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="sp-queue">
      <header className="sp-queue-head">
        <h4>Pending scrobbles ({entries.length})</h4>
        <div className="sp-queue-actions">
          <button
            className="sp-btn"
            onClick={load}
            disabled={loading || busy}
            title="Reload queue"
          >
            Refresh
          </button>
          <button
            className="sp-btn-primary"
            onClick={flush}
            disabled={busy || entries.length === 0}
          >
            {busy ? 'Retrying…' : 'Retry now'}
          </button>
        </div>
      </header>

      {loading && <p className="sp-meta">Loading queue…</p>}
      {error && <p className="sp-error">{error}</p>}

      {flushResult && (
        <p className="sp-meta">
          Retried {flushResult.attempted} · sent {flushResult.succeeded} ·{' '}
          {flushResult.remaining} remaining
          {flushResult.error ? ` · ${flushResult.error}` : ''}
        </p>
      )}

      {!loading && entries.length === 0 ? (
        <p className="sp-meta">
          Nothing queued — all your plays have been delivered to Last.fm.
        </p>
      ) : (
        <ul className="sp-queue-list">
          {entries.map((e) => (
            <li key={e.id} className="sp-queue-item">
              <div className="sp-queue-info">
                <strong>{e.track}</strong>
                <span className="sp-queue-artist"> — {e.artist}</span>
                <div className="sp-queue-meta">
                  Queued {formatRelative(e.queued_at)} ·{' '}
                  Played {new Date(e.timestamp * 1000).toLocaleString()} ·{' '}
                  {e.attempts} {e.attempts === 1 ? 'attempt' : 'attempts'}
                  {e.next_attempt_at
                    ? ` · next retry ${formatRelative(e.next_attempt_at)}`
                    : ''}
                </div>
                {e.last_error && (
                  <div className="sp-queue-error" title={e.last_error}>
                    Last error: {e.last_error}
                  </div>
                )}
              </div>
              <button
                className="sp-btn-danger sp-queue-del"
                onClick={() => remove(e.id)}
                disabled={busy}
                aria-label={`Delete ${e.track}`}
                title="Delete this queued scrobble"
              >
                Delete
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default SettingsPanel
