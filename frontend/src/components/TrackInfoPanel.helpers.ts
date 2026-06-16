// Framework-free pure helpers lifted out of TrackInfoPanel.tsx for direct
// unit testing (see TrackInfoPanel.helpers.test.ts).

/** Format a track duration as `m:ss`; 0/undefined renders as "" (unknown). */
export function formatDuration(ms?: number): string {
  if (!ms) return "";
  const sec = Math.round(ms / 1000);
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
}

export type SearchProvider = "musicbrainz" | "wikipedia" | "lastfm";

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
      return `https://en.wikipedia.org/w/index.php?search=${encodeURIComponent(
        `${title} ${artist} song`.trim(),
      )}`;
    case "lastfm":
      return `https://www.last.fm/search?q=${encodeURIComponent(both)}`;
  }
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
