import { describe, expect, it } from "vitest";
import {
  escapeHtml,
  formatDuration,
  highlightJson,
  providerSearchUrl,
  songfactsSearchUrl,
  wikipediaSearchUrl,
} from "./TrackInfoPanel.helpers";

describe("formatDuration", () => {
  it("renders 0/undefined as an empty (unknown) string", () => {
    expect(formatDuration()).toBe("");
    expect(formatDuration(0)).toBe("");
  });

  it("rounds to the nearest second and zero-pads", () => {
    expect(formatDuration(5_400)).toBe("0:05");
    expect(formatDuration(5_600)).toBe("0:06");
    expect(formatDuration(65_000)).toBe("1:05");
  });

  it("formats multi-minute durations", () => {
    expect(formatDuration(185_000)).toBe("3:05");
  });
});

describe("escapeHtml", () => {
  it("escapes the three HTML-significant characters", () => {
    expect(escapeHtml('<a href="x">&')).toBe('&lt;a href="x"&gt;&amp;');
  });

  it("escapes ampersands before angle brackets (no double-escape)", () => {
    expect(escapeHtml("a & b < c")).toBe("a &amp; b &lt; c");
  });
});

describe("highlightJson", () => {
  it("wraps keys, strings, numbers, booleans and null in classed spans", () => {
    const html = highlightJson({ a: "hi", b: 3, c: true, d: null });
    expect(html).toContain('<span class="tip-json-key">"a"</span>:');
    expect(html).toContain('<span class="tip-json-string">"hi"</span>');
    expect(html).toContain('<span class="tip-json-number">3</span>');
    expect(html).toContain('<span class="tip-json-bool">true</span>');
    expect(html).toContain('<span class="tip-json-null">null</span>');
  });

  it("escapes HTML inside string values", () => {
    const html = highlightJson({ x: "<script>" });
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>");
  });
});

describe("providerSearchUrl", () => {
  it("builds a recording search for MusicBrainz", () => {
    expect(providerSearchUrl("musicbrainz", "Daft Punk", "Aerodynamic")).toBe(
      "https://musicbrainz.org/search?query=Daft%20Punk%20Aerodynamic&type=recording",
    );
  });

  it("appends 'song' for Wikipedia and queries title first", () => {
    expect(providerSearchUrl("wikipedia", "Daft Punk", "Aerodynamic")).toBe(
      "https://en.wikipedia.org/w/index.php?search=Aerodynamic%20Daft%20Punk%20song",
    );
  });

  it("builds a Last.fm search", () => {
    expect(providerSearchUrl("lastfm", "Daft Punk", "Aerodynamic")).toBe(
      "https://www.last.fm/search?q=Daft%20Punk%20Aerodynamic",
    );
  });

  it("trims gracefully when artist or title is missing", () => {
    expect(providerSearchUrl("lastfm", "", "Aerodynamic")).toBe(
      "https://www.last.fm/search?q=Aerodynamic",
    );
  });
});

describe("songfactsSearchUrl", () => {
  it("searches songs and artists by the path-based, hyphenated slug", () => {
    expect(songfactsSearchUrl("songs", "Aerodynamic")).toBe(
      "https://www.songfacts.com/search/songs/aerodynamic",
    );
    expect(songfactsSearchUrl("songs", "Bohemian Rhapsody")).toBe(
      "https://www.songfacts.com/search/songs/bohemian-rhapsody",
    );
    expect(songfactsSearchUrl("artists", "Daft Punk")).toBe(
      "https://www.songfacts.com/search/artists/daft-punk",
    );
  });

  it("drops apostrophes and hyphenates other punctuation", () => {
    expect(songfactsSearchUrl("songs", "Don't Stop Me Now")).toBe(
      "https://www.songfacts.com/search/songs/dont-stop-me-now",
    );
  });
});

describe("wikipediaSearchUrl", () => {
  it("builds a Wikipedia full-text search link", () => {
    expect(wikipediaSearchUrl("Discovery album")).toBe(
      "https://en.wikipedia.org/w/index.php?search=Discovery%20album",
    );
  });
});
