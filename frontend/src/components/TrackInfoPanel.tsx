import { useEffect, useRef, useState } from 'react'
import { apiService, TrackDetail } from '../services/api'
import './TrackInfoPanel.css'

interface Props {
  trackId: string | null
  collapsed: boolean
  onToggleCollapsed: () => void
}

function formatDuration(ms?: number): string {
  if (!ms) return ''
  const sec = Math.round(ms / 1000)
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`
}

function TrackInfoPanel({ trackId, collapsed, onToggleCollapsed }: Props) {
  const [data, setData] = useState<TrackDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showRaw, setShowRaw] = useState(false)
  const [copied, setCopied] = useState(false)
  const reqRef = useRef(0)

  useEffect(() => {
    if (!trackId) {
      setData(null)
      setError(null)
      return
    }
    const reqId = ++reqRef.current
    setLoading(true)
    setError(null)
    apiService
      .getTrackDetail(trackId)
      .then((d) => {
        if (reqRef.current === reqId) setData(d)
      })
      .catch((e) => {
        if (reqRef.current === reqId) {
          setError(e?.response?.data?.detail || e.message || 'Failed to load')
          setData(null)
        }
      })
      .finally(() => {
        if (reqRef.current === reqId) setLoading(false)
      })
  }, [trackId])

  const handleCopy = async () => {
    if (!data) return
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2))
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch (e) {
      console.error('Copy failed', e)
    }
  }

  if (collapsed) {
    return (
      <div className="track-info-panel collapsed">
        <button
          className="tip-toggle"
          onClick={onToggleCollapsed}
          aria-label="Expand track info panel"
          title="Show track info"
        >
          ⓘ
        </button>
      </div>
    )
  }

  return (
    <aside className="track-info-panel" aria-label="Track info">
      <header className="tip-header">
        <span className="tip-title-tag">Track info</span>
        <div className="tip-header-actions">
          <label className="tip-raw-toggle" title="Toggle raw JSON view">
            <input
              type="checkbox"
              checked={showRaw}
              onChange={(e) => setShowRaw(e.target.checked)}
            />
            <span>Show raw</span>
          </label>
          <button
            className="tip-toggle"
            onClick={onToggleCollapsed}
            aria-label="Collapse track info panel"
            title="Collapse"
          >
            ×
          </button>
        </div>
      </header>

      <div className="tip-body">
        {!trackId && <p className="tip-empty">No track selected.</p>}
        {trackId && loading && <p className="tip-empty">Loading…</p>}
        {trackId && error && <p className="tip-error">{error}</p>}

        {data && showRaw && (
          <div className="tip-raw">
            <button className="tip-copy" onClick={handleCopy}>
              {copied ? 'Copied!' : 'Copy JSON'}
            </button>
            <pre>{JSON.stringify(data, null, 2)}</pre>
          </div>
        )}

        {data && !showRaw && (
          <>
            <section className="tip-section tip-head-section">
              <h3 className="tip-track-name">{data.spotify.name}</h3>
              <p className="tip-sub">
                {data.spotify.artists.join(', ')}
                {data.spotify.album ? ` · ${data.spotify.album}` : ''}
              </p>
              <p className="tip-meta">
                {formatDuration(data.spotify.duration_ms)}
                {data.spotify.release_date ? ` · ${data.spotify.release_date}` : ''}
                {data.spotify.isrc ? ` · ISRC ${data.spotify.isrc}` : ''}
                {data.spotify.explicit ? ' · explicit' : ''}
              </p>
              {data.spotify.external_url && (
                <a
                  className="tip-extlink"
                  href={data.spotify.external_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open in Spotify
                </a>
              )}
            </section>

            {data.lastfm && (
              <section className="tip-section">
                <h4>
                  Last.fm
                  <span className={`tip-tier tip-tier-${data.lastfm.tier}`}>
                    {data.lastfm.tier === 'authenticated' ? 'connected' : 'public'}
                  </span>
                </h4>
                {data.lastfm.error ? (
                  <p className="tip-meta">Lookup failed: {data.lastfm.error}</p>
                ) : (
                  <>
                    <p className="tip-stats">
                      {data.lastfm.user_playcount != null && (
                        <span>
                          Your plays: <strong>{data.lastfm.user_playcount}</strong>
                          {data.lastfm.user_loved ? ' ♥' : ''}
                        </span>
                      )}
                      {data.lastfm.playcount != null && (
                        <span>
                          Global plays:{' '}
                          <strong>{data.lastfm.playcount.toLocaleString()}</strong>
                        </span>
                      )}
                      {data.lastfm.listeners != null && (
                        <span>
                          Listeners:{' '}
                          <strong>{data.lastfm.listeners.toLocaleString()}</strong>
                        </span>
                      )}
                    </p>
                    {data.lastfm.tags && data.lastfm.tags.length > 0 && (
                      <div className="tip-tags">
                        {data.lastfm.tags.map((t) => (
                          <span key={t} className="tip-tag">
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                    {data.lastfm.summary && (
                      <p className="tip-summary">{data.lastfm.summary}</p>
                    )}
                    {data.lastfm.similar && data.lastfm.similar.length > 0 && (
                      <>
                        <h5 className="tip-h5">Similar tracks</h5>
                        <ul className="tip-similar">
                          {data.lastfm.similar.map((s, i) => (
                            <li key={i}>
                              <a href={s.url} target="_blank" rel="noreferrer">
                                {s.name}
                              </a>{' '}
                              <span className="tip-similar-artist">— {s.artist}</span>
                            </li>
                          ))}
                        </ul>
                      </>
                    )}
                  </>
                )}
              </section>
            )}

            {data.musicbrainz && (
              <section className="tip-section">
                <h4>
                  MusicBrainz
                  <span className="tip-tier tip-tier-public">public</span>
                </h4>
                <p className="tip-stats">
                  <span>
                    MBID: <code>{data.musicbrainz.mbid}</code>
                  </span>
                  {data.musicbrainz.isrcs.length > 0 && (
                    <span>ISRCs: {data.musicbrainz.isrcs.join(', ')}</span>
                  )}
                </p>
                {data.musicbrainz.releases.length > 0 && (
                  <>
                    <h5 className="tip-h5">Releases</h5>
                    <ul className="tip-releases">
                      {data.musicbrainz.releases.slice(0, 8).map((r) => (
                        <li key={r.mbid}>
                          {r.title}
                          {r.date ? ` (${r.date})` : ''}
                          {r.country ? ` · ${r.country}` : ''}
                          {r.release_group_type ? ` · ${r.release_group_type}` : ''}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
                {data.musicbrainz.tags.length > 0 && (
                  <div className="tip-tags">
                    {data.musicbrainz.tags.map((t) => (
                      <span key={t} className="tip-tag">
                        {t}
                      </span>
                    ))}
                  </div>
                )}
              </section>
            )}

            {data.wikipedia && (
              <section className="tip-section">
                <h4>
                  Wikipedia
                  <span className="tip-tier tip-tier-public">public</span>
                </h4>
                {data.wikipedia.description && (
                  <p className="tip-meta">{data.wikipedia.description}</p>
                )}
                <p className="tip-summary">{data.wikipedia.extract}</p>
                <a
                  className="tip-extlink"
                  href={data.wikipedia.url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Read on Wikipedia
                </a>
              </section>
            )}

            {!data.lastfm && !data.musicbrainz && !data.wikipedia && (
              <p className="tip-meta">
                No external metadata providers available for this track.
              </p>
            )}
          </>
        )}
      </div>
    </aside>
  )
}

export default TrackInfoPanel
