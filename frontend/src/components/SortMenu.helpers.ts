// Framework-free pure helper lifted out of SortMenu.tsx for direct unit
// testing (see SortMenu.helpers.test.ts).
import type { SortField } from "../services/api";

/** Resolve a sort-key's display label, falling back to the raw key. */
export function fieldLabel(fields: SortField[], key: string): string {
  return fields.find((f) => f.key === key)?.label ?? key;
}
