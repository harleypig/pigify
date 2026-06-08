import { describe, expect, it } from "vitest";
import type { SortField, SortKeySpec, Track } from "./api";
import { presetToKeys, type SortableHydration, sortTracks } from "./sortEngine";

const NO_HYDRATION: SortableHydration = { audio_features: {}, lastfm: {} };

function track(id: string, popularity: number | null): Track {
  return {
    id,
    name: id,
    artists: ["x"],
    album: "a",
    duration_ms: 0,
    uri: `spotify:track:${id}`,
    image_url: "",
    explicit: false,
    popularity,
  };
}

const POPULARITY: SortField = {
  key: "popularity",
  label: "Popularity",
  type: "number",
  source: "spotify_track",
  requires_hydration: false,
  group: "",
  default: false,
};

const asc: SortKeySpec = { field: "popularity", direction: "asc" };
const desc: SortKeySpec = { field: "popularity", direction: "desc" };

describe("sortTracks", () => {
  it("orders by a numeric field ascending", () => {
    const out = sortTracks(
      [track("b", 50), track("a", 10), track("c", 90)],
      [POPULARITY],
      [asc],
      NO_HYDRATION,
    );
    expect(out.map((t) => t.id)).toEqual(["a", "b", "c"]);
  });

  it("sorts missing values last regardless of direction", () => {
    const ids = (dir: SortKeySpec) =>
      sortTracks(
        [track("hi", 90), track("none", null), track("lo", 10)],
        [POPULARITY],
        [dir],
        NO_HYDRATION,
      ).map((t) => t.id);

    expect(ids(asc)).toEqual(["lo", "hi", "none"]);
    expect(ids(desc)).toEqual(["hi", "lo", "none"]);
  });

  it("returns the input unchanged when no keys resolve to a field", () => {
    const input = [track("a", 1), track("b", 2)];
    const out = sortTracks(input, [POPULARITY], [], NO_HYDRATION);
    expect(out).toBe(input);
  });
});

describe("presetToKeys", () => {
  it("prefers an explicit keys list", () => {
    expect(presetToKeys({ keys: [asc, desc] })).toEqual([asc, desc]);
  });

  it("falls back to legacy primary/secondary", () => {
    expect(presetToKeys({ primary: asc, secondary: desc })).toEqual([
      asc,
      desc,
    ]);
  });

  it("yields an empty list when nothing is set", () => {
    expect(presetToKeys({})).toEqual([]);
  });
});
