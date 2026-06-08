// Framework-free pure helper lifted out of UserMenu.tsx for direct unit
// testing (see UserMenu.helpers.test.ts).

/**
 * Derive up-to-two-letter initials from a display label: first+last initial
 * for multi-word labels, the first two letters for a single word, "?" when
 * empty.
 */
export function getInitials(label: string): string {
  const trimmed = label.trim();
  if (!trimmed) return "?";
  const parts = trimmed.split(/\s+/).filter(Boolean);
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase();
  }
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
