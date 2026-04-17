import { useEffect, useState } from 'react'
import { apiService, ConnectionStatus, LastfmStatus, Profile } from '../services/api'
import './SettingsModal.css'

interface Props {
  open: boolean
  onClose: () => void
  onProfileChange?: (profile: Profile) => void
}

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

function SettingsModal({ open, onClose, onProfileChange }: Props) {
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
    } catch (e: any) {
      setNameStatus('Failed to save')
    } finally {
      setSavingName(false)
    }
  }

  useEffect(() => {
    if (open) refresh()
  }, [open])

  if (!open) return null

  const lastfm = connections.lastfm
  const mb = connections.musicbrainz

  return (
    <div className="settings-overlay" onClick={onClose}>
      <div className="settings-modal" onClick={(e) => e.stopPropagation()}>
        <div className="settings-header">
          <h2>Connections</h2>
          <button className="settings-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        {loading && <p className="settings-loading">Loading…</p>}

        {/* Profile */}
        {profile && (
          <section className="settings-card">
            <header>
              <h3>Profile</h3>
            </header>
            <p className="settings-meta">
              Pick how Pigify labels you in the header. Leave empty to use your
              Spotify user id.
            </p>
            <div className="settings-row">
              <input
                type="text"
                className="settings-input"
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
                className="settings-btn-primary"
                onClick={saveName}
                disabled={
                  savingName ||
                  nameInput.trim() === (profile.custom_display_name ?? '')
                }
              >
                {savingName ? 'Saving…' : 'Save'}
              </button>
            </div>
            {nameStatus && <p className="settings-meta">{nameStatus}</p>}
          </section>
        )}

        {/* Last.fm */}
        {lastfm && lastfm.tier !== 'none' && (
          <section className="settings-card">
            <header>
              <h3>Last.fm</h3>
              <span className={`tier-pill ${tierClass(lastfm.tier)}`}>
                {tierLabel(lastfm.tier)}
              </span>
            </header>
            {lastfm.tier === 'authenticated' ? (
              <>
                <p className="settings-meta">
                  Signed in as <strong>{lastfm.connected_account}</strong>. Plays will be
                  scrobbled automatically.
                </p>
                <p className="settings-meta">
                  Last scrobble:{' '}
                  {lastfmStatus.last_scrobble_at
                    ? new Date(lastfmStatus.last_scrobble_at * 1000).toLocaleTimeString()
                    : 'none yet'}
                  {lastfmStatus.queued ? ` · ${lastfmStatus.queued} queued` : ''}
                </p>
                <button
                  className="settings-btn-danger"
                  onClick={async () => {
                    await apiService.disconnectLastfm()
                    refresh()
                  }}
                >
                  Disconnect
                </button>
              </>
            ) : (
              <>
                <p className="settings-meta">
                  Tags, similar tracks and global play counts work without signing in.
                  Connect your Last.fm account to scrobble plays and see your personal
                  play counts.
                </p>
                <a className="settings-btn-primary" href="/api/integrations/lastfm/login">
                  Connect Last.fm
                </a>
              </>
            )}
          </section>
        )}

        {/* MusicBrainz */}
        {mb && mb.tier !== 'none' && (
          <section className="settings-card">
            <header>
              <h3>MusicBrainz</h3>
              <span className={`tier-pill ${tierClass(mb.tier)}`}>
                {tierLabel(mb.tier)}
              </span>
            </header>
            <p className="settings-meta">
              MusicBrainz is fully public. Track identifiers, releases and credits are
              fetched automatically — no account needed.
            </p>
          </section>
        )}

        {/* Anything that returned tier=none is intentionally hidden. */}
      </div>
    </div>
  )
}

export default SettingsModal
