import { describe, expect, it } from "vitest";
import type { SortField } from "../services/api";
import { fieldLabel } from "./SortMenu.helpers";

function field(key: string, label: string): SortField {
  return {
    key,
    label,
    type: "string",
    source: "spotify_track",
    requires_hydration: false,
    group: "track",
    default: false,
  };
}

describe("fieldLabel", () => {
  const fields = [field("added_at", "Date added"), field("name", "Title")];

  it("returns the matching field's label", () => {
    expect(fieldLabel(fields, "added_at")).toBe("Date added");
  });

  it("falls back to the raw key when no field matches", () => {
    expect(fieldLabel(fields, "unknown_key")).toBe("unknown_key");
  });

  it("falls back to the key against an empty field list", () => {
    expect(fieldLabel([], "name")).toBe("name");
  });
});
