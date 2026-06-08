// Framework-free pure helpers lifted out of SettingsPanel.tsx for direct unit
// testing (see SettingsPanel.helpers.test.ts).

/** Human label for a connection access tier. */
export function tierLabel(tier: string): string {
  if (tier === "authenticated") return "Connected";
  if (tier === "public") return "Public access only";
  return "Unavailable";
}

/** CSS class for a connection access tier. */
export function tierClass(tier: string): string {
  if (tier === "authenticated") return "tier-ok";
  if (tier === "public") return "tier-public";
  return "tier-none";
}

/**
 * Format an ISO timestamp as a coarse "x ago" string, falling back to a full
 * locale string past a day and "—" for missing/invalid input. `nowMs` is
 * injectable so the relative output is deterministic in tests.
 */
export function formatRelative(
  iso?: string | null,
  nowMs: number = Date.now(),
): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const diff = nowMs - d.getTime();
  const sec = Math.round(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.round(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.round(sec / 3600)}h ago`;
  return d.toLocaleString();
}
