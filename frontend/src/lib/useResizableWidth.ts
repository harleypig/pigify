/**
 * Shared horizontal-resize capability for layout panels.
 *
 * The standard way to make a fixed-width panel user-resizable: this hook owns
 * the width (clamped + persisted) and returns the props a `<ResizeHandle>`
 * spreads onto its draggable edge. It supports either edge so a LEFT sidebar
 * (handle on its right edge) and a RIGHT sidebar (handle on its left edge)
 * both drag intuitively — dragging the divider outward always *grows* the
 * panel. Pointer drag and keyboard (←/→) both work; the value persists per
 * `storageKey` (mirroring the useFontScale pattern).
 */

import {
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  useEffect,
  useState,
} from "react";

export interface ResizableWidthOptions {
  /** localStorage key, e.g. "pigify.sidebar.width". */
  storageKey: string;
  min: number;
  max: number;
  /** Width used when nothing valid is stored. */
  defaultWidth: number;
  /** Which edge the handle sits on (the panel grows when that edge is dragged
   *  away from the panel). "right" for a left-docked panel; "left" for a
   *  right-docked one. Defaults to "right". */
  edge?: "left" | "right";
  /** Keyboard resize step in px. */
  step?: number;
}

export interface ResizableWidth {
  width: number;
  edge: "left" | "right";
  min: number;
  max: number;
  // Behavior the grip element wires up (the ARIA lives in `<ResizeHandle>`).
  onPointerDown: (e: ReactPointerEvent) => void;
  onPointerMove: (e: ReactPointerEvent) => void;
  onPointerUp: (e: ReactPointerEvent) => void;
  onKeyDown: (e: ReactKeyboardEvent) => void;
}

function clampWidth(width: number, min: number, max: number): number {
  return Math.round(Math.min(max, Math.max(min, width)));
}

function readWidth(opts: ResizableWidthOptions): number {
  const { storageKey, min, max, defaultWidth } = opts;
  try {
    const raw = localStorage.getItem(storageKey);
    if (raw !== null) {
      const value = JSON.parse(raw);
      if (typeof value === "number" && Number.isFinite(value)) {
        return clampWidth(value, min, max);
      }
    }
  } catch {
    /* ignore malformed storage */
  }
  return clampWidth(defaultWidth, min, max);
}

export function useResizableWidth(opts: ResizableWidthOptions): ResizableWidth {
  const { storageKey, min, max, edge = "right", step = 16 } = opts;
  const [width, setWidth] = useState(() => readWidth(opts));
  // Drag origin; null when not dragging. Kept in state-free closure via a ref
  // would also work, but a small module-local is clearer here.
  const [drag, setDrag] = useState<{ x: number; w: number } | null>(null);

  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(width));
    } catch {
      /* ignore */
    }
  }, [storageKey, width]);

  // A divider moved by `dx` px (pointer) grows the panel when dragged away
  // from it: the right-edge handle grows with +dx, the left-edge handle with
  // −dx.
  const applyDividerDelta = (startW: number, dx: number) =>
    setWidth(clampWidth(startW + (edge === "right" ? dx : -dx), min, max));

  const onPointerDown = (e: ReactPointerEvent) => {
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    setDrag({ x: e.clientX, w: width });
  };

  const onPointerMove = (e: ReactPointerEvent) => {
    if (!drag) return;
    applyDividerDelta(drag.w, e.clientX - drag.x);
  };

  const onPointerUp = (e: ReactPointerEvent) => {
    setDrag(null);
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      /* capture may already be gone */
    }
  };

  const onKeyDown = (e: ReactKeyboardEvent) => {
    // ←/→ move the divider, so they grow/shrink per the same edge rule.
    if (e.key === "ArrowRight") {
      applyDividerDelta(width, step);
      e.preventDefault();
    } else if (e.key === "ArrowLeft") {
      applyDividerDelta(width, -step);
      e.preventDefault();
    }
  };

  return {
    width,
    edge,
    min,
    max,
    onPointerDown,
    onPointerMove,
    onPointerUp,
    onKeyDown,
  };
}
