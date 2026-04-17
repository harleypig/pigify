import { useEffect, useState } from 'react'
import { apiService, TrackDetail } from '../services/api'
import './TrackDetailModal.css'

interface Props {
  trackId: string | null
  onClose: () => void
}

function formatDuration(ms?: number): string {
  if (!ms) return ''
  const sec = Math.round(ms / 1000)
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`
}

function TrackDetailModal({ trackId, onClose }: Props) {
  const [data, setData] = useState<TrackDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!trackId) {
      setData(null)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    setData(null)
    apiService
      .getTrackDetail(trackId)
      .then((d) => {
        if (!cancelled) setData(d)
      })
      .catch((e) => {
        if (!cancelled) setError(e?.response?.data?.detail || e.message || 'Failed to load')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [trackId])

  if (!trackId) return null

  return (
    <div className="track-detail-overlay" onClick={onClose}>
      <div className="track-detail-modal" onClick={(e) => e.stopPropagation()}>
        <button className="track-detail-close" onClick={onClose} aria-label="Close">
          ×
        </button>

        {loading && <p className="td-loading">Loading track details…</p>}
        {error && <p className="td-error">{error}</p>}

        {data && (
          <>
            <header className="td-header">
              <h2>{data.spotify.name}</h2>
              <p className="td-sub">
                {data.spotify.artists.join(', ')}
                {data.spotify.album ? ` · ${data.spotify.album}` : ''}
              </p>
              <p className="td-meta">
                {formatDuration(data.spotify.duration_ms)}
                {data.spotify.release_date ? ` · ${data.spotify.release_date}` : ''}
                {data.spotify.isrc ? ` · ISRC ${data.spotify.isrc}` : ''}
                {data.spotify.explicit ? ' · explicit' : ''}
              </p>
              {data.spotify.external_url && (
                <a
                  className="td-extlink"
                  href={data.spotify.external_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open in Spotify
                </a>
              )}
            </header>

            {data.lastfm && (
              <section className="td-section">
                <h3>
                  Last.fm
                  <span className={`td-tier td-tier-${data.lastfm.tier}`}>
                    {data.lastfm.tier === 'authenticated' ? 'connected' : 'public'}
                  </span>
                </h3>
                {data.lastfm.error ? (
                  <p className="td-meta">Last.fm lookup failed: {data.lastfm.error}</p>
                ) : (
                  <>
                    <p className="td-stats">
                      {data.lastfm.user_playcount != null && (
                        <span>
                          Your plays: <strong>{data.lastfm.user_playcount}</strong>
                          {data.lastfm.user_loved ? ' ♥' : ''}
                        </span>
                      )}
                      {data.lastfm.playcount != null && (
                        <span>
                          Global plays: <strong>{data.lastfm.playcount.toLocaleString()}</strong>
                        </span>
                      )}
                      {data.lastfm.listeners != null && (
                        <span>
                          Listeners: <strong>{data.lastfm.listeners.toLocaleString()}</strong>
                        </span>
                      )}
                    </p>
                    {data.lastfm.tags && data.lastfm.tags.length > 0 && (
                      <div className="td-tags">
                        {data.lastfm.tags.map((t) => (
                          <span key={t} className="td-tag">
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                    {data.lastfm.summary && (
                      <p className="td-summary">{data.lastfm.summary}</p>
                    )}
                    {data.lastfm.similar && data.lastfm.similar.length > 0 && (
                      <>
                        <h4 className="td-h4">Similar tracks</h4>
                        <ul className="td-similar">
                          {data.lastfm.similar.map((s, i) => (
                            <li key={i}>
                              <a href={s.url} target="_blank" rel="noreferrer">
                                {s.name}
                              </a>{' '}
                              <span className="td-similar-artist">— {s.artist}</span>
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
              <section className="td-section">
                <h3>
                  MusicBrainz
                  <span className="td-tier td-tier-public">public</span>
                </h3>
                <p className="td-stats">
                  <span>
                    MBID: <code>{data.musicbrainz.mbid}</code>
                  </span>
                  {data.musicbrainz.isrcs.length > 0 && (
                    <span>ISRCs: {data.musicbrainz.isrcs.join(', ')}</span>
                  )}
                </p>
                {data.musicbrainz.releases.length > 0 && (
                  <>
                    <h4 className="td-h4">Releases</h4>
                    <ul className="td-releases">
                      {data.musicbrainz.releases.map((r) => (
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
                  <div className="td-tags">
                    {data.musicbrainz.tags.map((t) => (
                      <span key={t} className="td-tag">
                        {t}
                      </span>
                    ))}
                  </div>
                )}
              </section>
            )}

            {/* If neither lastfm nor musicbrainz are available, show a quiet note. */}
            {!data.lastfm && !data.musicbrainz && (
              <p className="td-meta">
                No external metadata providers available for this track.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default TrackDetailModal
