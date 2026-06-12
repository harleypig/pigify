import { useCallback, useEffect, useRef, useState } from "react";
import { apiService, type TrackDetail } from "../services/api";
import { formatDuration, highlightJson } from "./TrackInfoPanel.helpers";
import "./TrackInfoPanel.css";

interface Props {
  trackId: string | null;
  collapsed: boolean;
  onToggleCollapsed: () => void;
}

function TrackInfoPanel({ trackId, collapsed, onToggleCollapsed }: Props) {
  const [data, setData] = useState<TrackDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(false);
  const [copied, setCopied] = useState(false);
  const [shared, setShared] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  // Wikipedia starts collapsed; opened on demand via the "+" toggle.
  const [wikiOpen, setWikiOpen] = useState(false);
  const reqRef = useRef(0);

  const fetchDetail = useCallback((id: string, refresh: boolean) => {
    const reqId = ++reqRef.current;
    if (refresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    apiService
      .getTrackDetail(id, { refresh })
      .then((d) => {
        if (reqRef.current === reqId) setData(d);
      })
      .catch((e) => {
        if (reqRef.current === reqId) {
          setError(e?.response?.data?.detail || e.message || "Failed to load");
          if (!refresh) setData(null);
        }
      })
      .finally(() => {
        if (reqRef.current === reqId) {
          setLoading(false);
          setRefreshing(false);
        }
      });
  }, []);

  useEffect(() => {
    // New track: re-collapse Wikipedia so it never auto-expands.
    setWikiOpen(false);
    if (!trackId) {
      setData(null);
      setError(null);
      return;
    }
    fetchDetail(trackId, false);
  }, [trackId, fetchDetail]);

  const handleRefresh = () => {
    if (trackId && !refreshing && !loading) fetchDetail(trackId, true);
  };

  // Share the track. For now the shared payload is just the Spotify link:
  // prefer the native share sheet (Web Share API), falling back to copying
  // the link to the clipboard. Per-service social sharing is a later TODO.
  const handleShare = async () => {
    if (!data?.spotify.external_url) return;
    const { external_url, name, artists } = data.spotify;
    const payload = {
      title: name,
      text: `${name} — ${artists.join(", ")}`,
      url: external_url,
    };
    if (typeof navigator.share === "function") {
      try {
        await navigator.share(payload);
        return;
      } catch {
        // User dismissed the sheet or it failed — fall back to copy.
      }
    }
    try {
      await navigator.clipboard.writeText(external_url);
      setShared(true);
      setTimeout(() => setShared(false), 1500);
    } catch (e) {
      console.error("Share failed", e);
    }
  };

  const handleCopy = async () => {
    if (!data) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(data, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (e) {
      console.error("Copy failed", e);
    }
  };

  if (collapsed) {
    return (
      <div className="track-info-panel collapsed">
        <button
          type="button"
          className="tip-toggle"
          onClick={onToggleCollapsed}
          aria-label="Expand track info panel"
          title="Show track info"
        >
          ⓘ
        </button>
      </div>
    );
  }

  return (
    <aside className="track-info-panel" aria-label="Track info">
      <header className="tip-header">
        <span className="tip-title-tag">Track info</span>
        <div className="tip-header-actions">
          <button
            type="button"
            className="tip-toggle tip-refresh"
            onClick={handleRefresh}
            disabled={!trackId || loading || refreshing}
            aria-label="Refresh cached track info"
            title="Force a fresh lookup, bypassing the cache"
          >
            {refreshing ? "…" : "↻"}
          </button>
          <label className="tip-raw-toggle" title="Toggle raw JSON view">
            <input
              type="checkbox"
              checked={showRaw}
              onChange={(e) => setShowRaw(e.target.checked)}
            />
            <span>Show raw</span>
          </label>
          <button
            type="button"
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
            <button type="button" className="tip-copy" onClick={handleCopy}>
              {copied ? "Copied!" : "Copy JSON"}
            </button>
            <pre
              className="tip-json"
              // biome-ignore lint/security/noDangerouslySetInnerHtml: highlightJson HTML-escapes input before highlighting; renders app-owned track JSON
              dangerouslySetInnerHTML={{ __html: highlightJson(data) }}
            />
          </div>
        )}

        {data && !showRaw && (
          <>
            <section className="tip-section tip-head-section">
              <h3 className="tip-track-name">{data.spotify.name}</h3>
              <p className="tip-sub">
                {data.spotify.artists.join(", ")}
                {data.spotify.album ? ` · ${data.spotify.album}` : ""}
              </p>
              <p className="tip-meta">
                {formatDuration(data.spotify.duration_ms)}
                {data.spotify.release_date
                  ? ` · ${data.spotify.release_date}`
                  : ""}
                {data.spotify.isrc ? ` · ISRC ${data.spotify.isrc}` : ""}
                {data.spotify.explicit ? " · explicit" : ""}
              </p>
              {data.spotify.external_url && (
                <div className="tip-head-actions">
                  <a
                    className="tip-extlink"
                    href={data.spotify.external_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open in Spotify
                  </a>
                  <button
                    type="button"
                    className="tip-share"
                    onClick={handleShare}
                    title="Share this track (copies the Spotify link)"
                    aria-label="Share this track"
                  >
                    <svg
                      width="13"
                      height="13"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <circle cx="18" cy="5" r="3" />
                      <circle cx="6" cy="12" r="3" />
                      <circle cx="18" cy="19" r="3" />
                      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
                      <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
                    </svg>
                    <span>{shared ? "Link copied!" : "Share"}</span>
                  </button>
                </div>
              )}
            </section>

            {data.lastfm && (
              <section className="tip-section">
                <h4>
                  Last.fm
                  <span className={`tip-tier tip-tier-${data.lastfm.tier}`}>
                    {data.lastfm.tier === "authenticated"
                      ? "connected"
                      : "public"}
                  </span>
                </h4>
                {data.lastfm.error ? (
                  <p className="tip-meta">Lookup failed: {data.lastfm.error}</p>
                ) : (
                  <>
                    <p className="tip-stats">
                      {data.lastfm.user_playcount != null && (
                        <span>
                          Your plays:{" "}
                          <strong>{data.lastfm.user_playcount}</strong>
                          {data.lastfm.user_loved ? " ♥" : ""}
                        </span>
                      )}
                      {data.lastfm.playcount != null && (
                        <span>
                          Global plays:{" "}
                          <strong>
                            {data.lastfm.playcount.toLocaleString()}
                          </strong>
                        </span>
                      )}
                      {data.lastfm.listeners != null && (
                        <span>
                          Listeners:{" "}
                          <strong>
                            {data.lastfm.listeners.toLocaleString()}
                          </strong>
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
                          {data.lastfm.similar.map((s) => (
                            <li key={`${s.name}-${s.artist}`}>
                              <a href={s.url} target="_blank" rel="noreferrer">
                                {s.name}
                              </a>{" "}
                              <span className="tip-similar-artist">
                                — {s.artist}
                              </span>
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
                    <span>ISRCs: {data.musicbrainz.isrcs.join(", ")}</span>
                  )}
                </p>
                {data.musicbrainz.releases.length > 0 && (
                  <>
                    <h5 className="tip-h5">Releases</h5>
                    <ul className="tip-releases">
                      {data.musicbrainz.releases.slice(0, 8).map((r) => (
                        <li key={r.mbid}>
                          {r.title}
                          {r.date ? ` (${r.date})` : ""}
                          {r.country ? ` · ${r.country}` : ""}
                          {r.release_group_type
                            ? ` · ${r.release_group_type}`
                            : ""}
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
                <h4 className="tip-wiki-head">
                  <button
                    type="button"
                    className="tip-wiki-toggle"
                    onClick={() => setWikiOpen((o) => !o)}
                    aria-expanded={wikiOpen}
                  >
                    <span className="tip-wiki-sign" aria-hidden="true">
                      {wikiOpen ? "−" : "+"}
                    </span>
                    Wikipedia
                  </button>
                  <span className="tip-tier tip-tier-public">public</span>
                </h4>
                {wikiOpen && (
                  <>
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
                  </>
                )}
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
  );
}

export default TrackInfoPanel;
