import {
  type CSSProperties,
  type ReactNode,
  type PointerEvent as ReactPointerEvent,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { apiService, type TrackDetail } from "../services/api";
import {
  formatDuration,
  highlightJson,
  providerSearchUrl,
  type SearchProvider,
} from "./TrackInfoPanel.helpers";
import "./TrackInfoPanel.css";

const PANEL_SIZE_KEY = "pigify.trackInfoPanel.size";
const PANEL_POS_KEY = "pigify.trackInfoPanel.pos";
const PANEL_FONT_KEY = "pigify.trackInfoPanel.fontScale";
const MIN_W = 280;
const MIN_H = 200;
const EDGE = 8; // keep this gap from the viewport edges
const FONT_MIN = 0.8;
const FONT_MAX = 1.6;
const FONT_STEP = 0.1;

interface Size {
  w: number;
  h: number;
}
interface Pos {
  x: number;
  y: number;
}

function readStored<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    if (raw) return JSON.parse(raw) as T;
  } catch {
    /* ignore malformed storage */
  }
  return null;
}

// Keep the panel reachable: fully on-screen when it fits, else pinned to the
// top-left edge (so the header / drag handle never drifts out of reach).
function clampPos(p: Pos, w: number, h: number): Pos {
  return {
    x: Math.max(
      EDGE,
      Math.min(p.x, Math.max(EDGE, window.innerWidth - w - EDGE)),
    ),
    y: Math.max(
      EDGE,
      Math.min(p.y, Math.max(EDGE, window.innerHeight - h - EDGE)),
    ),
  };
}

// Resize directions: each handle names the edge(s) it drags. A letter present
// means that edge moves — "n"/"s" vertical, "e"/"w" horizontal, corners both.
type ResizeDir = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";
const RESIZE_HANDLES: ResizeDir[] = [
  "n",
  "s",
  "e",
  "w",
  "ne",
  "nw",
  "se",
  "sw",
];

// Each provider section loads independently so a slow one never blocks the
// rest. "base" is the Spotify header + provider tiers; the others are the
// individual providers.
type SectionKey = "base" | "lastfm" | "musicbrainz" | "wikipedia";
type SectionStatus = "idle" | "loading" | "done" | "error";
const IDLE_STATUS: Record<SectionKey, SectionStatus> = {
  base: "idle",
  lastfm: "idle",
  musicbrainz: "idle",
  wikipedia: "idle",
};

function errMsg(e: unknown): string {
  const x = e as {
    response?: { data?: { detail?: string } };
    message?: string;
  };
  return x?.response?.data?.detail || x?.message || "Failed to load";
}

function Spinner() {
  return <span className="tip-spinner" aria-hidden="true" />;
}

const PROVIDER_LABEL: Record<SearchProvider, string> = {
  musicbrainz: "MusicBrainz",
  wikipedia: "Wikipedia",
  lastfm: "Last.fm",
};

// "Nothing found" line with a link to the provider's search page so the user
// can look it up by hand.
function NoResult({
  message,
  provider,
  artist,
  title,
}: {
  message: string;
  provider: SearchProvider;
  artist: string;
  title: string;
}) {
  return (
    <p className="tip-meta">
      {message}{" "}
      <a
        className="tip-extlink"
        href={providerSearchUrl(provider, artist, title)}
        target="_blank"
        rel="noreferrer"
      >
        Search {PROVIDER_LABEL[provider]}
      </a>
    </p>
  );
}

// A provider section: a mono "equipment label" header carrying its own ↻
// refresh, then a per-section spinner / error / content body.
function SectionFrame({
  title,
  tier,
  status,
  error,
  onRefresh,
  children,
}: {
  title: ReactNode;
  tier?: ReactNode;
  status: SectionStatus;
  error?: string;
  onRefresh: () => void;
  children: ReactNode;
}) {
  return (
    <section className="tip-section">
      <h4 className="tip-sec-head">
        <span className="tip-sec-title">
          {title}
          {tier}
        </span>
        <button
          type="button"
          className="tip-sec-refresh"
          onClick={onRefresh}
          disabled={status === "loading"}
          title="Refresh this section"
          aria-label="Refresh this section"
        >
          {status === "loading" ? "…" : "↻"}
        </button>
      </h4>
      {status === "loading" ? (
        <p className="tip-loading">
          <Spinner /> Loading…
        </p>
      ) : status === "error" ? (
        <p className="tip-error">{error}</p>
      ) : (
        children
      )}
    </section>
  );
}

interface Props {
  trackId: string | null;
  // Close (un-mount) the panel. There is no minimized state — reopen from the
  // now-playing ⓘ button or by clicking/right-clicking a track in the list.
  onClose: () => void;
  // Jump the panel back to the currently-playing track (clears the override
  // set by clicking/right-clicking a track in the list).
  onShowNowPlaying?: () => void;
  // True when there is a now-playing track and the panel isn't showing it.
  canShowNowPlaying?: boolean;
}

function TrackInfoPanel({
  trackId,
  onClose,
  onShowNowPlaying,
  canShowNowPlaying,
}: Props) {
  // Detail accumulates sections as they arrive; status/errors track each one.
  const [detail, setDetail] = useState<Partial<TrackDetail>>({});
  const [status, setStatus] =
    useState<Record<SectionKey, SectionStatus>>(IDLE_STATUS);
  const [errors, setErrors] = useState<Partial<Record<SectionKey, string>>>({});
  const [showRaw, setShowRaw] = useState(false);
  const [copied, setCopied] = useState(false);
  const [shared, setShared] = useState(false);
  // Wikipedia starts collapsed; opened on demand via the "+" toggle.
  const [wikiOpen, setWikiOpen] = useState(false);
  // Body text scale (A− / A+), persisted. Applied as `zoom` on the body so
  // text + spacing scale together; the header chrome stays fixed.
  const [fontScale, setFontScale] = useState<number>(
    () => readStored<number>(PANEL_FONT_KEY) ?? 1,
  );
  const reqRef = useRef(0);

  useEffect(() => {
    try {
      localStorage.setItem(PANEL_FONT_KEY, JSON.stringify(fontScale));
    } catch {
      /* ignore */
    }
  }, [fontScale]);

  const adjustFont = (delta: number) =>
    setFontScale(
      (s) =>
        Math.round(Math.min(FONT_MAX, Math.max(FONT_MIN, s + delta)) * 10) / 10,
    );

  // Floating-window geometry, both persisted: a top-left position and a size.
  // Drag the header to move; drag the bottom-right grip to resize. `null`
  // means "not set yet" — the panel first paints at its CSS default.
  const [size, setSize] = useState<Size | null>(() =>
    readStored<Size>(PANEL_SIZE_KEY),
  );
  const [pos, setPos] = useState<Pos | null>(() =>
    readStored<Pos>(PANEL_POS_KEY),
  );
  const [dragging, setDragging] = useState(false);
  const panelRef = useRef<HTMLElement>(null);
  // Origin of the active pointer gesture, shared by move and resize.
  const gestureRef = useRef<{
    mode: "move" | "resize";
    dir: ResizeDir | null;
    px: number;
    py: number;
    x: number;
    y: number;
    w: number;
    h: number;
  } | null>(null);

  useEffect(() => {
    if (size) {
      try {
        localStorage.setItem(PANEL_SIZE_KEY, JSON.stringify(size));
      } catch {
        /* ignore */
      }
    }
  }, [size]);
  useEffect(() => {
    if (pos) {
      try {
        localStorage.setItem(PANEL_POS_KEY, JSON.stringify(pos));
      } catch {
        /* ignore */
      }
    }
  }, [pos]);

  // Anchor top-left on first mount: the panel first paints at the CSS default
  // (bottom-right); measure that rect and convert it to an explicit position
  // so dragging and bottom-right resizing share one anchor. Pre-paint, so no
  // visible jump.
  useLayoutEffect(() => {
    if (pos) return;
    const el = panelRef.current;
    if (el) {
      const r = el.getBoundingClientRect();
      setPos({ x: r.left, y: r.top });
    }
  }, [pos]);

  // Keep it on-screen if the window shrinks under it.
  useEffect(() => {
    const onResize = () => {
      const el = panelRef.current;
      if (el)
        setPos((p) => (p ? clampPos(p, el.offsetWidth, el.offsetHeight) : p));
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const onHeaderPointerDown = (e: ReactPointerEvent) => {
    // Header controls (refresh, close, …) must still click, not start a drag.
    if ((e.target as HTMLElement).closest("button, label, input, a")) return;
    const el = panelRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    e.currentTarget.setPointerCapture(e.pointerId);
    gestureRef.current = {
      mode: "move",
      dir: null,
      px: e.clientX,
      py: e.clientY,
      x: r.left,
      y: r.top,
      w: r.width,
      h: r.height,
    };
    setDragging(true);
  };

  const onResizePointerDown = (e: ReactPointerEvent, dir: ResizeDir) => {
    const el = panelRef.current;
    if (!el) return;
    e.preventDefault();
    const r = el.getBoundingClientRect();
    e.currentTarget.setPointerCapture(e.pointerId);
    gestureRef.current = {
      mode: "resize",
      dir,
      px: e.clientX,
      py: e.clientY,
      x: r.left,
      y: r.top,
      w: r.width,
      h: r.height,
    };
  };

  const onGesturePointerMove = (e: ReactPointerEvent) => {
    const g = gestureRef.current;
    if (!g) return;
    const dx = e.clientX - g.px;
    const dy = e.clientY - g.py;
    if (g.mode === "move") {
      setPos(clampPos({ x: g.x + dx, y: g.y + dy }, g.w, g.h));
      return;
    }
    // Resize: each named edge moves toward the pointer; the opposite edge
    // stays put, so dragging a top/left edge also shifts the anchor.
    const dir = g.dir ?? "se";
    const right = g.x + g.w;
    const bottom = g.y + g.h;
    let { x, y, w, h } = g;
    if (dir.includes("e")) {
      w = Math.max(MIN_W, Math.min(window.innerWidth - g.x - EDGE, g.w + dx));
    }
    if (dir.includes("w")) {
      x = Math.max(EDGE, Math.min(right - MIN_W, g.x + dx));
      w = right - x;
    }
    if (dir.includes("s")) {
      h = Math.max(MIN_H, Math.min(window.innerHeight - g.y - EDGE, g.h + dy));
    }
    if (dir.includes("n")) {
      y = Math.max(EDGE, Math.min(bottom - MIN_H, g.y + dy));
      h = bottom - y;
    }
    setSize({ w, h });
    if (dir.includes("w") || dir.includes("n")) {
      setPos({ x, y });
    }
  };

  const onGesturePointerUp = (e: ReactPointerEvent) => {
    if (!gestureRef.current) return;
    gestureRef.current = null;
    setDragging(false);
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      /* ignore */
    }
  };

  // Fetch one section in isolation and merge it in. `reqId` guards against a
  // stale track — results from a superseded load are dropped.
  const fetchSection = useCallback(
    (id: string, key: SectionKey, refresh: boolean, reqId: number) =>
      apiService
        .getTrackDetail(id, { sections: key, refresh })
        .then((d) => {
          if (reqRef.current !== reqId) return d;
          setDetail((prev) => ({ ...prev, ...d }));
          setStatus((s) => ({ ...s, [key]: "done" }));
          return d;
        })
        .catch((e) => {
          if (reqRef.current === reqId) {
            setErrors((er) => ({ ...er, [key]: errMsg(e) }));
            setStatus((s) => ({ ...s, [key]: "error" }));
          }
          return {} as Partial<TrackDetail>;
        }),
    [],
  );

  // Load every section for a track. Base + the always-public providers fire
  // immediately in parallel; Last.fm fires once base reveals it's available.
  const loadAll = useCallback(
    (id: string, refresh: boolean) => {
      const reqId = ++reqRef.current;
      setDetail({});
      setErrors({});
      setStatus({
        base: "loading",
        lastfm: "idle",
        musicbrainz: "loading",
        wikipedia: "loading",
      });
      fetchSection(id, "musicbrainz", refresh, reqId);
      fetchSection(id, "wikipedia", refresh, reqId);
      fetchSection(id, "base", refresh, reqId).then((d) => {
        if (reqRef.current !== reqId) return;
        const tier = d.connections?.lastfm?.tier;
        if (tier && tier !== "none") {
          setStatus((s) => ({ ...s, lastfm: "loading" }));
          fetchSection(id, "lastfm", refresh, reqId);
        }
      });
    },
    [fetchSection],
  );

  useEffect(() => {
    // New track: re-collapse Wikipedia so it never auto-expands.
    setWikiOpen(false);
    if (!trackId) {
      setDetail({});
      setErrors({});
      setStatus(IDLE_STATUS);
      return;
    }
    loadAll(trackId, false);
  }, [trackId, loadAll]);

  const anyLoading = Object.values(status).some((s) => s === "loading");

  // Re-fetch a single section (its own ↻ button).
  const refreshSection = (key: SectionKey) => {
    if (!trackId || status[key] === "loading") return;
    setStatus((s) => ({ ...s, [key]: "loading" }));
    setErrors((er) => ({ ...er, [key]: undefined }));
    fetchSection(trackId, key, true, reqRef.current);
  };

  // Main ↻: re-fetch every section.
  const handleRefresh = () => {
    if (trackId && !anyLoading) loadAll(trackId, true);
  };

  // Share the track. For now the shared payload is just the Spotify link:
  // prefer the native share sheet (Web Share API), falling back to copying
  // the link to the clipboard. Per-service social sharing is a later TODO.
  const handleShare = async () => {
    if (!detail.spotify?.external_url) return;
    const { external_url, name, artists } = detail.spotify;
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
    try {
      await navigator.clipboard.writeText(JSON.stringify(detail, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (e) {
      console.error("Copy failed", e);
    }
  };

  const style: CSSProperties & Record<"--tip-scale", number> = {
    "--tip-scale": fontScale,
  };
  if (pos) {
    style.left = pos.x;
    style.top = pos.y;
    style.right = "auto";
    style.bottom = "auto";
  }
  if (size) {
    style.width = size.w;
    style.height = size.h;
    style.maxHeight = "none";
  }

  // Artist + title for the per-provider "Search …" fallback links.
  const sArtist = detail.spotify?.artists?.[0] ?? "";
  const sTitle = detail.spotify?.name ?? "";

  // Per-section objects for the "Show raw" view (each shows its own spinner).
  const rawBlocks: { key: SectionKey; label: string; value: unknown }[] = [
    {
      key: "base",
      label: "spotify + connections",
      value: { spotify: detail.spotify, connections: detail.connections },
    },
    { key: "lastfm", label: "lastfm", value: detail.lastfm },
    { key: "musicbrainz", label: "musicbrainz", value: detail.musicbrainz },
    { key: "wikipedia", label: "wikipedia", value: detail.wikipedia },
  ];

  return (
    <aside
      className={`track-info-panel${dragging ? " dragging" : ""}`}
      aria-label="Track info"
      ref={panelRef}
      style={style}
    >
      {/* Resize handles on every edge + corner. Pointer-only, invisible. */}
      {RESIZE_HANDLES.map((dir) => (
        <div
          key={dir}
          className={`tip-rz tip-rz-${dir}`}
          onPointerDown={(e) => onResizePointerDown(e, dir)}
          onPointerMove={onGesturePointerMove}
          onPointerUp={onGesturePointerUp}
          aria-hidden="true"
        />
      ))}
      <header
        className="tip-header"
        onPointerDown={onHeaderPointerDown}
        onPointerMove={onGesturePointerMove}
        onPointerUp={onGesturePointerUp}
      >
        <span className="tip-title-tag">Track info</span>
        <div className="tip-header-actions">
          <button
            type="button"
            className="tip-toggle tip-font"
            onClick={() => adjustFont(-FONT_STEP)}
            disabled={fontScale <= FONT_MIN}
            aria-label="Decrease text size"
            title="Decrease text size"
          >
            A−
          </button>
          <button
            type="button"
            className="tip-toggle tip-font"
            onClick={() => adjustFont(FONT_STEP)}
            disabled={fontScale >= FONT_MAX}
            aria-label="Increase text size"
            title="Increase text size"
          >
            A+
          </button>
          {canShowNowPlaying && onShowNowPlaying && (
            <button
              type="button"
              className="tip-toggle tip-nowplaying"
              onClick={onShowNowPlaying}
              aria-label="Show the currently playing track"
              title="Show the currently playing track"
            >
              ♪
            </button>
          )}
          <button
            type="button"
            className="tip-toggle tip-refresh"
            onClick={handleRefresh}
            disabled={!trackId || anyLoading}
            aria-label="Refresh all track info"
            title="Force a fresh lookup of every section, bypassing the cache"
          >
            {anyLoading ? "…" : "↻"}
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
            onClick={onClose}
            aria-label="Close track info panel"
            title="Close"
          >
            ×
          </button>
        </div>
      </header>

      <div className="tip-body">
        {!trackId && <p className="tip-empty">No track selected.</p>}

        {trackId && showRaw && (
          <div className="tip-raw">
            <button type="button" className="tip-copy" onClick={handleCopy}>
              {copied ? "Copied!" : "Copy JSON"}
            </button>
            {rawBlocks.map(({ key, label, value }) => (
              <div key={key} className="tip-raw-block">
                <h5 className="tip-h5">{label}</h5>
                {status[key] === "loading" ? (
                  <p className="tip-loading">
                    <Spinner /> Loading…
                  </p>
                ) : status[key] === "idle" ? (
                  <p className="tip-meta">—</p>
                ) : status[key] === "error" ? (
                  <p className="tip-error">{errors[key]}</p>
                ) : (
                  <pre
                    className="tip-json"
                    // biome-ignore lint/security/noDangerouslySetInnerHtml: highlightJson HTML-escapes input before highlighting; renders app-owned track JSON
                    dangerouslySetInnerHTML={{ __html: highlightJson(value) }}
                  />
                )}
              </div>
            ))}
          </div>
        )}

        {trackId && !showRaw && (
          <>
            <section className="tip-section tip-head-section">
              <button
                type="button"
                className="tip-sec-refresh tip-head-refresh"
                onClick={() => refreshSection("base")}
                disabled={status.base === "loading"}
                title="Refresh track info"
                aria-label="Refresh track info"
              >
                {status.base === "loading" ? "…" : "↻"}
              </button>
              {status.base === "loading" && (
                <p className="tip-loading">
                  <Spinner /> Loading…
                </p>
              )}
              {status.base === "error" && (
                <p className="tip-error">{errors.base}</p>
              )}
              {detail.spotify && (
                <>
                  <h3 className="tip-track-name">{detail.spotify.name}</h3>
                  <p className="tip-sub">
                    {detail.spotify.artists.join(", ")}
                    {detail.spotify.album ? ` · ${detail.spotify.album}` : ""}
                  </p>
                  <p className="tip-meta">
                    {formatDuration(detail.spotify.duration_ms)}
                    {detail.spotify.release_date
                      ? ` · ${detail.spotify.release_date}`
                      : ""}
                    {detail.spotify.isrc
                      ? ` · ISRC ${detail.spotify.isrc}`
                      : ""}
                    {detail.spotify.explicit ? " · explicit" : ""}
                  </p>
                  {detail.spotify.external_url && (
                    <div className="tip-head-actions">
                      <a
                        className="tip-extlink"
                        href={detail.spotify.external_url}
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
                </>
              )}
            </section>

            {status.lastfm !== "idle" && (
              <SectionFrame
                title="Last.fm"
                tier={
                  detail.lastfm && (
                    <span className={`tip-tier tip-tier-${detail.lastfm.tier}`}>
                      {detail.lastfm.tier === "authenticated"
                        ? "connected"
                        : "public"}
                    </span>
                  )
                }
                status={status.lastfm}
                error={errors.lastfm}
                onRefresh={() => refreshSection("lastfm")}
              >
                {detail.lastfm ? (
                  detail.lastfm.error ? (
                    <p className="tip-meta">
                      Lookup failed: {detail.lastfm.error}
                    </p>
                  ) : (
                    <>
                      <p className="tip-stats">
                        {detail.lastfm.user_playcount != null && (
                          <span>
                            Your plays:{" "}
                            <strong>{detail.lastfm.user_playcount}</strong>
                            {detail.lastfm.user_loved ? " ♥" : ""}
                          </span>
                        )}
                        {detail.lastfm.playcount != null && (
                          <span>
                            Global plays:{" "}
                            <strong>
                              {detail.lastfm.playcount.toLocaleString()}
                            </strong>
                          </span>
                        )}
                        {detail.lastfm.listeners != null && (
                          <span>
                            Listeners:{" "}
                            <strong>
                              {detail.lastfm.listeners.toLocaleString()}
                            </strong>
                          </span>
                        )}
                      </p>
                      {detail.lastfm.tags && detail.lastfm.tags.length > 0 && (
                        <div className="tip-tags">
                          {detail.lastfm.tags.map((t) => (
                            <span key={t} className="tip-tag">
                              {t}
                            </span>
                          ))}
                        </div>
                      )}
                      {detail.lastfm.summary && (
                        <p className="tip-summary">{detail.lastfm.summary}</p>
                      )}
                      {detail.lastfm.similar &&
                        detail.lastfm.similar.length > 0 && (
                          <>
                            <h5 className="tip-h5">Similar tracks</h5>
                            <ul className="tip-similar">
                              {detail.lastfm.similar.map((s) => (
                                <li key={`${s.name}-${s.artist}`}>
                                  <a
                                    href={s.url}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
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
                  )
                ) : (
                  <NoResult
                    message="No Last.fm data for this track."
                    provider="lastfm"
                    artist={sArtist}
                    title={sTitle}
                  />
                )}
              </SectionFrame>
            )}

            {status.musicbrainz !== "idle" && (
              <SectionFrame
                title="MusicBrainz"
                tier={<span className="tip-tier tip-tier-public">public</span>}
                status={status.musicbrainz}
                error={errors.musicbrainz}
                onRefresh={() => refreshSection("musicbrainz")}
              >
                {detail.musicbrainz ? (
                  <>
                    <p className="tip-stats">
                      <span>
                        MBID: <code>{detail.musicbrainz.mbid}</code>
                      </span>
                      {detail.musicbrainz.isrcs.length > 0 && (
                        <span>
                          ISRCs: {detail.musicbrainz.isrcs.join(", ")}
                        </span>
                      )}
                    </p>
                    {detail.musicbrainz.releases.length > 0 && (
                      <>
                        <h5 className="tip-h5">Releases</h5>
                        <ul className="tip-releases">
                          {detail.musicbrainz.releases.slice(0, 8).map((r) => (
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
                    {detail.musicbrainz.tags.length > 0 && (
                      <div className="tip-tags">
                        {detail.musicbrainz.tags.map((t) => (
                          <span key={t} className="tip-tag">
                            {t}
                          </span>
                        ))}
                      </div>
                    )}
                  </>
                ) : (
                  <NoResult
                    message="No MusicBrainz match."
                    provider="musicbrainz"
                    artist={sArtist}
                    title={sTitle}
                  />
                )}
              </SectionFrame>
            )}

            {status.wikipedia !== "idle" && (
              <SectionFrame
                title={
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
                }
                tier={<span className="tip-tier tip-tier-public">public</span>}
                status={status.wikipedia}
                error={errors.wikipedia}
                onRefresh={() => refreshSection("wikipedia")}
              >
                {detail.wikipedia ? (
                  wikiOpen && (
                    <>
                      {detail.wikipedia.description && (
                        <p className="tip-meta">
                          {detail.wikipedia.description}
                        </p>
                      )}
                      <p className="tip-summary">{detail.wikipedia.extract}</p>
                      <a
                        className="tip-extlink"
                        href={detail.wikipedia.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Read on Wikipedia
                      </a>
                    </>
                  )
                ) : (
                  <NoResult
                    message="No Wikipedia article found."
                    provider="wikipedia"
                    artist={sArtist}
                    title={sTitle}
                  />
                )}
              </SectionFrame>
            )}
          </>
        )}
      </div>
    </aside>
  );
}

export default TrackInfoPanel;
