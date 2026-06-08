// Framework-free pure helpers lifted out of App.tsx so they can be unit
// tested directly (see App.helpers.test.ts). Keep this module free of React
// imports.

export const SCROBBLE_DISMISS_KEY = "pigify.scrobbleAlert.dismissed";
export const SCROBBLE_QUEUE_THRESHOLD = 5;
export const SCROBBLE_STALE_MS = 60 * 60 * 1000; // 1 hour

export interface ScrobbleAlertState {
  queued: number;
  oldestQueuedAt: string | null;
}

/** Read and validate the persisted "banner dismissed" snapshot. */
export function readDismissed(): ScrobbleAlertState | null {
  try {
    const raw = localStorage.getItem(SCROBBLE_DISMISS_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (
      parsed &&
      typeof parsed.queued === "number" &&
      (parsed.oldestQueuedAt === null ||
        typeof parsed.oldestQueuedAt === "string")
    ) {
      return parsed;
    }
  } catch {
    /* ignore */
  }
  return null;
}

/** Pick the smallest avatar image by height, falling back to the last one. */
export function pickAvatarUrl(
  images?: Array<{ url: string; height?: number; width?: number }> | null,
): string | null {
  if (!images || images.length === 0) return null;
  const sized = images.filter((img) => typeof img.height === "number");
  if (sized.length > 0) {
    const smallest = sized.reduce((a, b) =>
      (a.height ?? Infinity) <= (b.height ?? Infinity) ? a : b,
    );
    return smallest.url;
  }
  return images[images.length - 1].url;
}

export interface ScrobbleSeverity {
  isStale: boolean;
  isOverThreshold: boolean;
  severe: boolean;
  showBanner: boolean;
}

/**
 * Derive the scrobble-alert severity and whether the banner should show,
 * given the current alert, the last-dismissed snapshot, and the clock. The
 * banner shows only when severe AND the alert has changed since dismissal.
 */
export function evaluateScrobbleAlert(
  alert: ScrobbleAlertState,
  dismissed: ScrobbleAlertState | null,
  nowMs: number,
): ScrobbleSeverity {
  const oldestStaleMs = alert.oldestQueuedAt
    ? nowMs - new Date(alert.oldestQueuedAt).getTime()
    : 0;
  const isStale = alert.queued > 0 && oldestStaleMs > SCROBBLE_STALE_MS;
  const isOverThreshold = alert.queued > SCROBBLE_QUEUE_THRESHOLD;
  const severe = isStale || isOverThreshold;
  const alertSignatureChanged =
    !dismissed ||
    alert.queued > dismissed.queued ||
    alert.oldestQueuedAt !== dismissed.oldestQueuedAt;
  const showBanner = severe && alertSignatureChanged;
  return { isStale, isOverThreshold, severe, showBanner };
}

/** Tooltip for the queued-scrobbles badge, or undefined when nothing queued. */
export function scrobbleBadgeTitle(
  alert: ScrobbleAlertState,
  isStale: boolean,
): string | undefined {
  if (alert.queued <= 0) return undefined;
  const plural = alert.queued === 1 ? "" : "s";
  const base = `${alert.queued} pending scrobble${plural}`;
  return isStale
    ? `${base} · oldest stuck for over 1h — click Settings to review`
    : `${base} — click Settings to review`;
}
