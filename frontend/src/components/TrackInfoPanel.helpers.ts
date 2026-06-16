// Framework-free pure helpers lifted out of TrackInfoPanel.tsx for direct
// unit testing (see TrackInfoPanel.helpers.test.ts).

/** Format a track duration as `m:ss`; 0/undefined renders as "" (unknown). */
export function formatDuration(ms?: number): string {
  if (!ms) return "";
  const sec = Math.round(ms / 1000);
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
}

export type SearchProvider = "musicbrainz" | "wikipedia" | "lastfm";

/** Lowercase, hyphenate runs of non-alphanumerics, drop apostrophes. */
function slug(s: string): string {
  return s
    .toLowerCase()
    .replace(/['’]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** A Wikipedia full-text search link for an arbitrary query. */
export function wikipediaSearchUrl(query: string): string {
  return `https://en.wikipedia.org/w/index.php?search=${encodeURIComponent(
    query.trim(),
  )}`;
}

/**
 * Build a link to a provider's search page, pre-filled with the track. Shown
 * when a provider returns no result, so the user can look it up manually.
 */
export function providerSearchUrl(
  provider: SearchProvider,
  artist: string,
  title: string,
): string {
  const both = `${artist} ${title}`.trim();
  switch (provider) {
    case "musicbrainz":
      return `https://musicbrainz.org/search?query=${encodeURIComponent(
        both,
      )}&type=recording`;
    case "wikipedia":
      return wikipediaSearchUrl(`${title} ${artist} song`);
    case "lastfm":
      return `https://www.last.fm/search?q=${encodeURIComponent(both)}`;
  }
}

/**
 * Songfacts has no public API and its native search is **path-based, by
 * kind** — `/search/songs/<slug>` and `/search/artists/<slug>` (a `?q=` query
 * param does NOT work). We surface both a song-title and an artist search.
 */
export function songfactsSearchUrl(
  kind: "songs" | "artists",
  name: string,
): string {
  return `https://www.songfacts.com/search/${kind}/${slug(name)}`;
}

/** Escape the three HTML-significant characters for safe text interpolation. */
export function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/** Render a value as syntax-highlighted, HTML-escaped pretty JSON. */
export function highlightJson(value: unknown): string {
  const json = JSON.stringify(value, null, 2) ?? "";
  const escaped = escapeHtml(json);
  // Match strings (with optional trailing colon for keys), numbers, booleans, null
  const re =
    /("(?:\\.|[^"\\])*")(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g;
  return escaped.replace(re, (match, str, colon, kw) => {
    if (str !== undefined) {
      const cls = colon ? "tip-json-key" : "tip-json-string";
      return `<span class="${cls}">${str}</span>${colon || ""}`;
    }
    if (kw !== undefined) {
      const cls = kw === "null" ? "tip-json-null" : "tip-json-bool";
      return `<span class="${cls}">${kw}</span>`;
    }
    return `<span class="tip-json-number">${match}</span>`;
  });
}
