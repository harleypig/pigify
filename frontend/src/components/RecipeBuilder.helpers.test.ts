import { describe, expect, it } from "vitest";
import type { SortField, SortType } from "../services/api";
import {
  buildSource,
  inputValue,
  opsForField,
  parseSource,
  pickCover,
} from "./RecipeBuilder.helpers";

function field(type: SortType): SortField {
  return {
    key: "f",
    label: "F",
    type,
    source: "spotify_track",
    requires_hydration: false,
    group: "track",
    default: false,
  };
}

describe("inputValue", () => {
  it("collapses null, undefined, booleans and arrays to an empty string", () => {
    expect(inputValue(null)).toBe("");
    expect(inputValue(undefined)).toBe("");
    expect(inputValue(true)).toBe("");
    expect(inputValue(["a", "b"])).toBe("");
  });

  it("stringifies numbers and passes strings through", () => {
    expect(inputValue(42)).toBe("42");
    expect(inputValue("hello")).toBe("hello");
  });
});

describe("opsForField", () => {
  const firstOp = (f?: SortField) => opsForField(f)[0][0];

  it("defaults to string ops with no field", () => {
    expect(firstOp(undefined)).toBe("contains");
  });

  it("selects ops by field type", () => {
    expect(firstOp(field("number"))).toBe("gte");
    expect(firstOp(field("date"))).toBe("gte");
    expect(firstOp(field("enum"))).toBe("eq");
    expect(firstOp(field("string"))).toBe("contains");
  });

  it("gives enum fields exactly is/is-not", () => {
    expect(opsForField(field("enum")).map(([op]) => op)).toEqual(["eq", "ne"]);
  });
});

describe("parseSource", () => {
  it("parses the liked and all-playlists sentinels", () => {
    expect(parseSource("liked")).toEqual({ kind: "liked", ids: [] });
    expect(parseSource("all_playlists")).toEqual({
      kind: "all_playlists",
      ids: [],
    });
  });

  it("parses a single playlist", () => {
    expect(parseSource("playlist:abc")).toEqual({
      kind: "playlist",
      ids: ["abc"],
    });
  });

  it("parses a multi-playlist list, trimming and dropping blanks", () => {
    expect(parseSource("playlists:a, b ,,c")).toEqual({
      kind: "playlists",
      ids: ["a", "b", "c"],
    });
  });

  it("treats an empty playlist id as no ids", () => {
    expect(parseSource("playlist:")).toEqual({ kind: "playlist", ids: [] });
  });

  it("falls back to liked for an unrecognized source", () => {
    expect(parseSource("garbage")).toEqual({ kind: "liked", ids: [] });
  });
});

describe("buildSource", () => {
  it("emits the sentinels", () => {
    expect(buildSource("liked", [])).toBe("liked");
    expect(buildSource("all_playlists", ["ignored"])).toBe("all_playlists");
  });

  it("emits a bare prefix when no ids remain", () => {
    expect(buildSource("playlists", [])).toBe("playlists:");
    expect(buildSource("playlists", ["", ""])).toBe("playlists:");
  });

  it("collapses a single id to the playlist form", () => {
    expect(buildSource("playlists", ["only"])).toBe("playlist:only");
  });

  it("joins multiple ids", () => {
    expect(buildSource("playlists", ["a", "b"])).toBe("playlists:a,b");
  });
});

describe("parse/build round-trip", () => {
  for (const source of ["liked", "all_playlists", "playlist:abc"]) {
    it(`round-trips ${source}`, () => {
      const { kind, ids } = parseSource(source);
      expect(buildSource(kind, ids)).toBe(source);
    });
  }

  it("round-trips a multi-playlist list", () => {
    const { kind, ids } = parseSource("playlists:a,b,c");
    expect(buildSource(kind, ids)).toBe("playlists:a,b,c");
  });
});

describe("pickCover", () => {
  it("returns null for missing, empty, or url-less images", () => {
    expect(pickCover()).toBeNull();
    expect(pickCover([])).toBeNull();
    expect(pickCover([{ url: "" }])).toBeNull();
  });

  it("prefers the smallest image at least 32px tall", () => {
    const url = pickCover([
      { url: "tiny", height: 16 },
      { url: "small", height: 64 },
      { url: "big", height: 640 },
    ]);
    expect(url).toBe("small");
  });

  it("falls back to the smallest when all are under 32px", () => {
    const url = pickCover([
      { url: "a", height: 20 },
      { url: "b", height: 8 },
    ]);
    expect(url).toBe("b");
  });

  it("falls back to the first url when no heights are present", () => {
    expect(pickCover([{ url: "first" }, { url: "second" }])).toBe("first");
  });
});
