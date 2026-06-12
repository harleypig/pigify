import {
  type CSSProperties,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  apiService,
  type Playlist,
  type SortField,
  type SortPreset,
  type Track,
} from "../services/api";
import {
  requiredSources,
  type SortableHydration,
  sortTracks,
} from "../services/sortEngine";
import EditPlaylistInfo from "./EditPlaylistInfo";
import HeartButton from "./HeartButton";
import SortMenu, { type SortSpec } from "./SortMenu";
import "./TrackList.css";

interface TrackListProps {
  playlistId: string;
  onTrackSelect: (trackUri: string) => void;
  onTrackFocus?: (trackId: string) => void;
}

const DEFAULT_SORT: SortSpec = {
  keys: [{ field: "added_at", direction: "desc" }],
};

// Track-row columns, in grid order. `width` feeds the shared grid template;
// `label` is the (possibly empty) column-header text; `name` is the readable
// label in the column chooser. Non-hideable columns (title, heart) are always
// shown. The header row and every track row use the same template plus a fixed
// trailing gutter for the chooser, so the two separate grids stay aligned.
interface ColumnDef {
  key: string;
  label: string;
  name: string;
  width: string;
  align?: "center" | "right";
  hideable: boolean;
}

const COLUMNS: ColumnDef[] = [
  {
    key: "index",
    label: "#",
    name: "Index",
    width: "40px",
    align: "center",
    hideable: true,
  },
  { key: "art", label: "", name: "Artwork", width: "60px", hideable: true },
  {
    key: "title",
    label: "Title",
    name: "Title",
    width: "1fr",
    hideable: false,
  },
  {
    key: "album",
    label: "Album",
    name: "Album",
    width: "200px",
    hideable: true,
  },
  { key: "heart", label: "", name: "Heart", width: "36px", hideable: false },
  {
    key: "duration",
    label: "Time",
    name: "Duration",
    width: "60px",
    align: "right",
    hideable: true,
  },
];

const HIDEABLE_COLUMNS = COLUMNS.filter((c) => c.hideable);
const COLUMNS_KEY = "pigify.trackColumns";

function TrackList({
  playlistId,
  onTrackSelect,
  onTrackFocus,
}: TrackListProps) {
  const [tracks, setTracks] = useState<Track[]>([]);
  const [playlist, setPlaylist] = useState<Playlist | null>(null);
  const [editing, setEditing] = useState(false);
  // Row selection (mouse): a plain click single-selects, Ctrl toggles one
  // row, Shift selects a range. Queuing the selection will be drag-and-drop
  // to the queue display later (TODO) — this only tracks selection for now.
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [anchorIndex, setAnchorIndex] = useState<number | null>(null);
  // Which hideable columns are shown (non-hideable ones are always shown).
  // Persisted so the chosen column set survives reloads. Defaults to all.
  const [visibleCols, setVisibleCols] = useState<Set<string>>(() => {
    try {
      const raw = localStorage.getItem(COLUMNS_KEY);
      if (raw) return new Set(JSON.parse(raw) as string[]);
    } catch {
      /* ignore */
    }
    return new Set(HIDEABLE_COLUMNS.map((c) => c.key));
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lovedMap, setLovedMap] = useState<
    Record<string, { spotify: boolean | null; lastfm: boolean | null }>
  >({});

  // Sort state
  const [fields, setFields] = useState<SortField[]>([]);
  const [presets, setPresets] = useState<SortPreset[]>([]);
  const [sortSpec, setSortSpec] = useState<SortSpec>(DEFAULT_SORT);
  const [hydration, setHydration] = useState<SortableHydration>({
    audio_features: {},
    lastfm: {},
  });
  const [warnings, setWarnings] = useState<string[]>([]);
  const [hydrating, setHydrating] = useState(false);
  const [applying, setApplying] = useState(false);
  const [undoAvailable, setUndoAvailable] = useState(false);

  // Load fields/presets once.
  useEffect(() => {
    apiService
      .getSortFields()
      .then((r) => setFields(r.fields))
      .catch(() => {});
    apiService
      .listSortPresets()
      .then(setPresets)
      .catch(() => {});
  }, []);

  const loadTracks = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiService.getAllPlaylistTracks(playlistId);
      setTracks(data);
      setError(null);
      // Bulk-fetch loved state in one round trip
      try {
        const favs = await apiService.checkFavorites(
          data.map((t) => ({
            track_id: t.id,
            name: t.name,
            artist: t.artists[0] ?? "",
          })),
        );
        const map: Record<
          string,
          { spotify: boolean | null; lastfm: boolean | null }
        > = {};
        favs.forEach((f, i) => {
          const id = data[i]?.id;
          if (id) {
            map[id] = {
              spotify: (f.sources.spotify ?? null) as boolean | null,
              lastfm: (f.sources.lastfm ?? null) as boolean | null,
            };
          }
        });
        setLovedMap(map);
      } catch {
        /* non-fatal */
      }
    } catch (err) {
      setError("Failed to load tracks");
      console.error("Error loading tracks:", err);
    } finally {
      setLoading(false);
    }
  }, [playlistId]);

  const refreshUndoStatus = useCallback(async () => {
    try {
      const r = await apiService.getUndoStatus(playlistId);
      setUndoAvailable(r.available);
    } catch {
      setUndoAvailable(false);
    }
  }, [playlistId]);

  // Load tracks + undo status when playlist changes.
  useEffect(() => {
    loadTracks();
    refreshUndoStatus();
    setHydration({ audio_features: {}, lastfm: {} });
    setWarnings([]);
  }, [refreshUndoStatus, loadTracks]);

  // Load the playlist's own details (name/description) for the header, and
  // drop any row selection carried over from the previous playlist.
  useEffect(() => {
    setSelectedKeys(new Set());
    setAnchorIndex(null);
    apiService
      .getPlaylist(playlistId)
      .then(setPlaylist)
      .catch(() => setPlaylist(null));
  }, [playlistId]);

  // Hydrate when sort spec needs data we don't have.
  const ensureHydration = useCallback(
    async (spec: SortSpec) => {
      if (fields.length === 0 || tracks.length === 0) return;
      const sources = requiredSources(fields, spec.keys);
      if (sources.length === 0) return;

      const missing: typeof sources = [];
      for (const src of sources) {
        const map = hydration[src];
        const need = tracks.some((t) => !(t.id in map));
        if (need) missing.push(src);
      }
      if (missing.length === 0) return;

      try {
        setHydrating(true);
        const meta = tracks.map((t) => ({
          id: t.id,
          name: t.name,
          artist: t.artists[0] ?? "",
        }));
        const ids = tracks.map((t) => t.id).filter(Boolean);
        const r = await apiService.hydrateTracks(
          playlistId,
          ids,
          missing,
          meta,
        );
        setHydration((prev) => ({
          audio_features: { ...prev.audio_features, ...r.audio_features },
          lastfm: { ...prev.lastfm, ...r.lastfm },
        }));
        setWarnings(r.warnings || []);
      } catch (e) {
        console.error("Hydration failed:", e);
        setWarnings(["Failed to fetch extra data for sort"]);
      } finally {
        setHydrating(false);
      }
    },
    [fields, tracks, hydration, playlistId],
  );

  useEffect(() => {
    ensureHydration(sortSpec);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sortSpec, ensureHydration]);

  const sortedTracks = useMemo(() => {
    if (fields.length === 0) return tracks;
    return sortTracks(tracks, fields, sortSpec.keys, hydration);
  }, [tracks, fields, sortSpec, hydration]);

  // A playlist can legitimately contain the same track more than once, so
  // track.id is not unique on its own. Pair each row with a stable key built
  // from its id plus a per-id occurrence count (not the array index), so
  // duplicates get distinct keys without relying on render position.
  const rowKeys = useMemo(() => {
    const seen = new Map<string, number>();
    return sortedTracks.map((t) => {
      const n = seen.get(t.id) ?? 0;
      seen.set(t.id, n + 1);
      return `${t.id}-${n}`;
    });
  }, [sortedTracks]);

  const handleSavePreset = async (preset: SortPreset) => {
    try {
      const updated = await apiService.saveSortPreset(preset);
      setPresets(updated);
    } catch (e) {
      console.error("Save preset failed:", e);
    }
  };

  const handleDeletePreset = async (name: string) => {
    try {
      const updated = await apiService.deleteSortPreset(name);
      setPresets(updated);
    } catch (e) {
      console.error("Delete preset failed:", e);
    }
  };

  const handleApplyView = () => {
    /* sorted view is already shown */
  };

  const handleApplyToPlaylist = async () => {
    if (!sortedTracks.length) return;
    if (
      !window.confirm(
        `This will rewrite the playlist on Spotify in the new order (${sortedTracks.length} tracks). You can undo it once. Continue?`,
      )
    )
      return;
    try {
      setApplying(true);
      const targetUris = sortedTracks.map((t) => t.uri);
      const result = await apiService.reorderPlaylist(playlistId, targetUris);
      setUndoAvailable(result.undo_available);
      await loadTracks();
    } catch (e) {
      console.error("Apply to playlist failed:", e);
      alert("Failed to reorder playlist on Spotify.");
    } finally {
      setApplying(false);
    }
  };

  const handleUndo = async () => {
    try {
      setApplying(true);
      await apiService.undoReorder(playlistId);
      setUndoAvailable(false);
      await loadTracks();
    } catch (e) {
      console.error("Undo failed:", e);
      alert("Undo failed.");
    } finally {
      setApplying(false);
    }
  };

  // Mouse selection model: a plain click single-selects, Ctrl toggles the
  // one row, Shift selects the range from the anchor (the last single/Ctrl
  // click) to this row in either direction. Selection is keyed by rowKeys so
  // it survives sorts and tolerates duplicate tracks.
  const selectRow = (index: number, ctrl: boolean, shift: boolean) => {
    const key = rowKeys[index];

    if (shift && anchorIndex !== null) {
      const lo = Math.min(anchorIndex, index);
      const hi = Math.max(anchorIndex, index);
      const range = new Set<string>();
      for (let i = lo; i <= hi; i++) range.add(rowKeys[i]);
      setSelectedKeys(range);
    } else if (ctrl) {
      setSelectedKeys((prev) => {
        const next = new Set(prev);
        if (next.has(key)) next.delete(key);
        else next.add(key);
        return next;
      });
      setAnchorIndex(index);
    } else {
      // Plain click: single-select — but clicking an already-highlighted row
      // unhighlights it (removing just that row, keeping any others).
      setSelectedKeys((prev) => {
        if (prev.has(key)) {
          const next = new Set(prev);
          next.delete(key);
          return next;
        }
        return new Set([key]);
      });
      setAnchorIndex(index);
    }
  };

  // Persist the chosen column set.
  useEffect(() => {
    try {
      localStorage.setItem(COLUMNS_KEY, JSON.stringify([...visibleCols]));
    } catch {
      /* ignore */
    }
  }, [visibleCols]);

  // Close the column chooser when clicking outside its popover.
  const columnsRef = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      const el = columnsRef.current;
      if (el?.open && !el.contains(e.target as Node)) el.open = false;
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, []);

  const toggleColumn = (key: string) => {
    setVisibleCols((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  // Columns actually shown (non-hideable always; hideable when selected), the
  // grid template they imply, and a quick lookup of which keys are shown.
  const shownColumns = COLUMNS.filter(
    (c) => !c.hideable || visibleCols.has(c.key),
  );
  const shownKeys = new Set(shownColumns.map((c) => c.key));
  // A fixed trailing 28px gutter reserves space for the header's column
  // chooser so the header and the rows (separate grids) line up exactly.
  const gridStyle = {
    "--tl-cols": `${shownColumns.map((c) => c.width).join(" ")} 28px`,
  } as CSSProperties;

  const formatDuration = (ms: number): string => {
    const seconds = Math.floor(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`;
  };

  if (loading) {
    return <div className="track-list-loading">Loading tracks…</div>;
  }

  if (error) {
    return <div className="track-list-error">{error}</div>;
  }

  return (
    <div className="track-list" style={gridStyle}>
      <div className="track-list-header">
        <div className="track-list-heading">
          <h2>{playlist?.name ?? "Playlist"}</h2>
          <span className="track-count">
            {sortedTracks.length} tracks
            {hydrating && (
              <span className="hydrating-tag"> · loading sort data…</span>
            )}
          </span>
          {playlist && (
            <button
              type="button"
              className="track-list-edit"
              onClick={() => setEditing(true)}
            >
              Edit
            </button>
          )}
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
      {/* Column header row + chooser. Labels align to the rows below via the
          shared --tl-cols template; the chooser sits in the trailing gutter. */}
      <div className="track-list-columns">
        {shownColumns.map((c) => (
          <span
            key={c.key}
            className={`tlc-label${c.align ? ` tlc-align-${c.align}` : ""}`}
          >
            {c.label}
          </span>
        ))}
        <details className="tlc-chooser" ref={columnsRef}>
          <summary
            className="tlc-chooser-btn"
            title="Choose columns"
            aria-label="Choose columns"
          >
            ▦
          </summary>
          <div className="tlc-chooser-menu">
            <p className="tlc-chooser-title">Columns</p>
            {HIDEABLE_COLUMNS.map((c) => (
              <label key={c.key} className="tlc-chooser-item">
                <input
                  type="checkbox"
                  checked={visibleCols.has(c.key)}
                  onChange={() => toggleColumn(c.key)}
                />
                <span>{c.name}</span>
              </label>
            ))}
          </div>
        </details>
      </div>
      <div
        className="track-list-items"
        role="listbox"
        aria-multiselectable="true"
        aria-label="Tracks"
      >
        {sortedTracks.map((track, index) => (
          /* Each row is an option in the listbox below — the row body is the
             mouse selection affordance (single / Ctrl / Shift click); it is
             NOT the play trigger. Only the song name plays (see the name
             button), so a stray click never starts playback; Enter on a
             focused row plays as a keyboard fallback. Long playlists are not
             virtualized — the typical Pigify use case is a few hundred rows,
             well within what the DOM handles smoothly. */
          <div
            key={rowKeys[index]}
            className={`track-item${
              selectedKeys.has(rowKeys[index]) ? " selected" : ""
            }`}
            role="option"
            aria-selected={selectedKeys.has(rowKeys[index])}
            tabIndex={0}
            aria-label={`${track.name} by ${track.artists.join(", ")}`}
            onClick={(e) =>
              selectRow(index, e.ctrlKey || e.metaKey, e.shiftKey)
            }
            onKeyDown={(e) => {
              // Only act when the row itself is focused — ignore Enter
              // forwarded from inner controls (the name button, the heart).
              if (e.target !== e.currentTarget) return;
              if (e.key === "Enter") {
                e.preventDefault();
                onTrackSelect(track.uri);
                onTrackFocus?.(track.id);
              }
            }}
          >
            {shownKeys.has("index") && (
              <div className="track-number">{index + 1}</div>
            )}
            {shownKeys.has("art") && (
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
                  <div className="track-placeholder" aria-hidden="true">
                    ♪
                  </div>
                )}
              </div>
            )}
            <div className="track-info">
              {/* The song name is the only way to start playback. Right-click
                  it to open the Track Info panel instead of playing. */}
              <button
                type="button"
                className="track-name"
                title="Play — right-click for track info"
                onClick={(e) => {
                  e.stopPropagation();
                  onTrackSelect(track.uri);
                  onTrackFocus?.(track.id);
                }}
                onContextMenu={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onTrackFocus?.(track.id);
                }}
              >
                {track.name}
              </button>
              <div className="track-artists">{track.artists.join(", ")}</div>
            </div>
            {shownKeys.has("album") && (
              <div className="track-album">{track.album}</div>
            )}
            {/* stopPropagation prevents heart clicks from triggering the
                row-level "play this track" handler. The wrapper is a passive
                event boundary, not an interactive control of its own — the
                interactive HeartButton lives inside it. */}
            {/* biome-ignore lint/a11y/noStaticElementInteractions: passive boundary that only stops click propagation; the actual control is the nested HeartButton */}
            <div
              className="track-heart"
              onClick={(e) => e.stopPropagation()}
              onKeyDown={(e) => e.stopPropagation()}
            >
              <HeartButton
                track={{
                  spotify_id: track.id,
                  spotify_uri: track.uri,
                  name: track.name,
                  artist: track.artists[0] ?? "",
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
            {shownKeys.has("duration") && (
              <div className="track-duration">
                {formatDuration(track.duration_ms)}
              </div>
            )}
          </div>
        ))}
      </div>
      {editing && playlist && (
        <EditPlaylistInfo
          playlist={playlist}
          onClose={() => setEditing(false)}
          onSaved={setPlaylist}
        />
      )}
    </div>
  );
}

export default TrackList;
