import type { ResizableWidth } from "../lib/useResizableWidth";
import "./ResizeHandle.css";

interface ResizeHandleProps {
  /** The handle bundle from `useResizableWidth` (props + the edge). */
  resize: ResizableWidth;
  /** Accessible name, e.g. "Resize playlist sidebar". */
  label: string;
}

/**
 * The draggable edge strip that resizes a panel, wired to `useResizableWidth`.
 * Sits on the panel's `edge`; drag (or focus + ←/→) to resize. The panel needs
 * `position: relative` so this can straddle its border.
 */
export function ResizeHandle({ resize, label }: ResizeHandleProps) {
  return (
    // biome-ignore lint/a11y/useSemanticElements: this is the WAI-ARIA window-splitter pattern — a focusable, interactive separator (tabIndex + key/pointer resize), not a thematic break; <hr> can't be an interactive resizer
    <div
      className={`resize-handle resize-handle--${resize.edge}`}
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuenow={resize.width}
      aria-valuemin={resize.min}
      aria-valuemax={resize.max}
      tabIndex={0}
      title={label}
      onPointerDown={resize.onPointerDown}
      onPointerMove={resize.onPointerMove}
      onPointerUp={resize.onPointerUp}
      onKeyDown={resize.onKeyDown}
    />
  );
}
