/**
 * Shared text-size scale for the floating panels (Track-info, Settings).
 *
 * Each panel persists its own scale under its own storage key, but they share
 * the bounds, step, default, and the clamp/persist mechanism so the control
 * behaves identically everywhere. The scale is applied per-panel as
 * `zoom: var(--…-scale)` on the panel body (text + spacing together; the
 * header chrome stays fixed).
 */

import { useEffect, useState } from "react";

export const FONT_MIN = 0.8;
export const FONT_MAX = 1.6;
export const FONT_STEP = 0.1;
export const FONT_DEFAULT = 1;

/** Apply a delta to a scale, clamped to [FONT_MIN, FONT_MAX] and rounded. */
export function adjustFontScale(scale: number, delta: number): number {
  const next = Math.min(FONT_MAX, Math.max(FONT_MIN, scale + delta));
  return Math.round(next * 10) / 10;
}

function readFontScale(key: string): number {
  try {
    const raw = localStorage.getItem(key);
    if (raw !== null) {
      const value = JSON.parse(raw);
      if (typeof value === "number" && Number.isFinite(value)) {
        return adjustFontScale(value, 0); // clamp a stale/out-of-range value
      }
    }
  } catch {
    /* ignore malformed storage */
  }
  return FONT_DEFAULT;
}

/**
 * A persisted text-size scale plus an adjuster. `key` is the panel's own
 * localStorage key; the default and bounds are shared.
 */
export function useFontScale(key: string): [number, (delta: number) => void] {
  const [scale, setScale] = useState<number>(() => readFontScale(key));

  useEffect(() => {
    try {
      localStorage.setItem(key, JSON.stringify(scale));
    } catch {
      /* ignore */
    }
  }, [key, scale]);

  const adjust = (delta: number) =>
    setScale((current) => adjustFontScale(current, delta));

  return [scale, adjust];
}
