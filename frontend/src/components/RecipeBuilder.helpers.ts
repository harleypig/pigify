// Framework-free pure helpers lifted out of RecipeBuilder.tsx for direct unit
// testing (see RecipeBuilder.helpers.test.ts).
import type { FilterOp, RecipeFilter, SortField } from "../services/api";

const NUMERIC_OPS: Array<[FilterOp, string]> = [
  ["gte", "≥"],
  ["lte", "≤"],
  ["gt", ">"],
  ["lt", "<"],
  ["eq", "="],
  ["ne", "≠"],
  ["between", "between"],
];
const STRING_OPS: Array<[FilterOp, string]> = [
  ["contains", "contains"],
  ["eq", "="],
  ["ne", "≠"],
];
const ENUM_OPS: Array<[FilterOp, string]> = [
  ["eq", "is"],
  ["ne", "is not"],
];
const DATE_OPS: Array<[FilterOp, string]> = [
  ["gte", "on/after"],
  ["lte", "on/before"],
  ["between", "between"],
];

/**
 * Coerce a filter value to a string suitable for a text/number `<input>`.
 * Enum (boolean) filters use a dedicated `<select>`, and list operands are
 * not edited through these inputs, so those collapse to an empty string.
 */
export function inputValue(v: RecipeFilter["value"]): string {
  if (v == null || typeof v === "boolean" || Array.isArray(v)) return "";
  return String(v);
}

/** The operator choices available for a field, keyed off its type. */
export function opsForField(f?: SortField): Array<[FilterOp, string]> {
  if (!f) return STRING_OPS;
  if (f.type === "number") return NUMERIC_OPS;
  if (f.type === "date") return DATE_OPS;
  if (f.type === "enum") return ENUM_OPS;
  return STRING_OPS;
}

export type SourceKind = "liked" | "playlist" | "playlists" | "all_playlists";

/** Parse a bucket source string into its kind and any playlist ids. */
export function parseSource(source: string): {
  kind: SourceKind;
  ids: string[];
} {
  if (source === "liked") return { kind: "liked", ids: [] };
  if (source === "all_playlists") return { kind: "all_playlists", ids: [] };
  if (source.startsWith("playlists:")) {
    const ids = source
      .slice("playlists:".length)
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    return { kind: "playlists", ids };
  }
  if (source.startsWith("playlist:")) {
    const id = source.slice("playlist:".length).trim();
    return { kind: "playlist", ids: id ? [id] : [] };
  }
  return { kind: "liked", ids: [] };
}

/** Serialize a kind + playlist ids back into a bucket source string. */
export function buildSource(kind: SourceKind, ids: string[]): string {
  if (kind === "liked") return "liked";
  if (kind === "all_playlists") return "all_playlists";
  const clean = ids.filter(Boolean);
  if (clean.length === 0) return "playlists:";
  if (clean.length === 1) return `playlist:${clean[0]}`;
  return `playlists:${clean.join(",")}`;
}

/** Pick a playlist cover: smallest image ≥ 32px tall, else smallest/first. */
export function pickCover(
  images?: Array<{ url: string; height?: number; width?: number }>,
): string | null {
  if (!images || images.length === 0) return null;
  // Prefer the smallest image >= 32px tall; otherwise pick the smallest available.
  const withSize = images.filter((i) => i?.url);
  if (withSize.length === 0) return null;
  const sized = withSize
    .filter((i) => typeof i.height === "number" && i.height! > 0)
    .sort((a, b) => (a.height || 0) - (b.height || 0));
  const small = sized.find((i) => (i.height || 0) >= 32);
  if (small) return small.url;
  if (sized.length) return sized[0].url;
  return withSize[0].url;
}
