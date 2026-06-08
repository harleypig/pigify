import { describe, expect, it } from "vitest";
import type { SortField, SortKeySpec, SortSource, Track } from "./api";
import {
  getSortValue,
  requiredSources,
  type SortableHydration,
} from "./sortEngine";

// Covers getSortValue and requiredSources — the sortEngine functions the
// existing sortEngine.test.ts does not exercise (it covers sortTracks and
// presetToKeys).

function track(overrides: Partial<Track> = {}): Track {
  return {
    id: "t1",
    name: "Song",
    artists: ["First", "Second"],
    album: "Album",
    duration_ms: 1000,
    uri: "spotify:track:t1",
    image_url: "",
    explicit: true,
    popularity: 42,
    added_at: "2024-01-01",
    release_date: "2020-05-05",
    track_number: 7,
    ...overrides,
  };
}

function field(key: string, source: SortSource): SortField {
  return {
    key,
    label: key,
    type: "string",
    source,
    requires_hydration: source !== "spotify_track",
    group: "",
    default: false,
  };
}

const NO_HYDRATION: SortableHydration = { audio_features: {}, lastfm: {} };

describe("getSortValue — spotify_track source", () => {
  it("returns the first artist for the artist key", () => {
    expect(
      getSortValue(field("artist", "spotify_track"), track(), NO_HYDRATION),
    ).toBe("First");
  });

  it("returns empty string when there are no artists", () => {
    const t = track({ artists: [] });
    expect(
      getSortValue(field("artist", "spotify_track"), t, NO_HYDRATION),
    ).toBe("");
  });

  it.each([
    ["name", "Song"],
    ["album", "Album"],
    ["duration_ms", 1000],
    ["added_at", "2024-01-01"],
    ["release_date", "2020-05-05"],
    ["popularity", 42],
    ["explicit", true],
    ["track_number", 7],
  ] as const)("maps the %s key to the track field", (key, expected) => {
    expect(
      getSortValue(field(key, "spotify_track"), track(), NO_HYDRATION),
    ).toBe(expected);
  });

  it("returns undefined for an unknown spotify_track key", () => {
    expect(
      getSortValue(field("nope", "spotify_track"), track(), NO_HYDRATION),
    ).toBeUndefined();
  });
});

describe("getSortValue — audio_features source", () => {
  it("reads the keyed value from the per-track hydration entry", () => {
    const hydration: SortableHydration = {
      audio_features: { t1: { tempo: 128, energy: 0.8 } },
      lastfm: {},
    };

    expect(
      getSortValue(field("tempo", "audio_features"), track(), hydration),
    ).toBe(128);
  });

  it("returns undefined when the track has no audio_features entry", () => {
    expect(
      getSortValue(field("tempo", "audio_features"), track(), NO_HYDRATION),
    ).toBeUndefined();
  });

  it("returns undefined when the entry is explicitly null", () => {
    const hydration: SortableHydration = {
      audio_features: { t1: null },
      lastfm: {},
    };

    expect(
      getSortValue(field("tempo", "audio_features"), track(), hydration),
    ).toBeUndefined();
  });
});

describe("getSortValue — lastfm source", () => {
  it.each([
    ["lastfm_playcount", "playcount", 500],
    ["lastfm_listeners", "listeners", 300],
    ["lastfm_user_playcount", "user_playcount", 12],
  ] as const)("maps the %s field key to the lastfm hydration value", (fieldKey, _hydrationKey, value) => {
    const hydration: SortableHydration = {
      audio_features: {},
      lastfm: {
        t1: { playcount: 500, listeners: 300, user_playcount: 12 },
      },
    };

    expect(getSortValue(field(fieldKey, "lastfm"), track(), hydration)).toBe(
      value,
    );
  });

  it("returns undefined for an unknown lastfm key", () => {
    const hydration: SortableHydration = {
      audio_features: {},
      lastfm: { t1: { playcount: 1 } },
    };

    expect(
      getSortValue(field("lastfm_unknown", "lastfm"), track(), hydration),
    ).toBeUndefined();
  });

  it("returns undefined when the track has no lastfm entry", () => {
    expect(
      getSortValue(field("lastfm_playcount", "lastfm"), track(), NO_HYDRATION),
    ).toBeUndefined();
  });
});

describe("requiredSources", () => {
  const audioField: SortField = {
    ...field("tempo", "audio_features"),
    requires_hydration: true,
  };
  const lastfmField: SortField = {
    ...field("lastfm_playcount", "lastfm"),
    requires_hydration: true,
  };
  const trackField: SortField = field("name", "spotify_track");

  const key = (f: string): SortKeySpec => ({ field: f, direction: "asc" });

  it("returns an empty list when no keys require hydration", () => {
    expect(requiredSources([trackField], [key("name")])).toEqual([]);
  });

  it("collects audio_features and lastfm when both are needed", () => {
    const out = requiredSources(
      [audioField, lastfmField],
      [key("tempo"), key("lastfm_playcount")],
    );

    expect(out.sort()).toEqual(["audio_features", "lastfm"]);
  });

  it("de-duplicates a source used by multiple keys", () => {
    const second: SortField = {
      ...field("energy", "audio_features"),
      requires_hydration: true,
    };

    const out = requiredSources(
      [audioField, second],
      [key("tempo"), key("energy")],
    );

    expect(out).toEqual(["audio_features"]);
  });

  it("ignores a field whose requires_hydration flag is false", () => {
    const notHydrated: SortField = {
      ...field("tempo", "audio_features"),
      requires_hydration: false,
    };

    expect(requiredSources([notHydrated], [key("tempo")])).toEqual([]);
  });

  it("ignores keys that do not resolve to a known field", () => {
    expect(requiredSources([audioField], [key("ghost")])).toEqual([]);
  });
});
