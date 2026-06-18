// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ResizableWidth } from "../lib/useResizableWidth";
import { ResizeHandle } from "./ResizeHandle";

function fakeResize(over: Partial<ResizableWidth> = {}): ResizableWidth {
  return {
    width: 300,
    edge: "right",
    min: 200,
    max: 600,
    onPointerDown: vi.fn(),
    onPointerMove: vi.fn(),
    onPointerUp: vi.fn(),
    onKeyDown: vi.fn(),
    ...over,
  };
}

describe("ResizeHandle", () => {
  it("exposes the focusable separator semantics", () => {
    render(<ResizeHandle resize={fakeResize()} label="Resize sidebar" />);
    const sep = screen.getByRole("separator", { name: "Resize sidebar" });
    expect(sep).toHaveAttribute("aria-orientation", "vertical");
    expect(sep).toHaveAttribute("aria-valuenow", "300");
    expect(sep).toHaveAttribute("aria-valuemin", "200");
    expect(sep).toHaveAttribute("aria-valuemax", "600");
    expect(sep).toHaveAttribute("tabindex", "0");
  });

  it("places the grip on the configured edge and wires the handlers", () => {
    const resize = fakeResize({ edge: "left" });
    const { container } = render(
      <ResizeHandle resize={resize} label="Resize queue" />,
    );
    expect(container.firstChild).toHaveClass("resize-handle--left");

    const sep = screen.getByRole("separator");
    fireEvent.keyDown(sep, { key: "ArrowRight" });
    expect(resize.onKeyDown).toHaveBeenCalledTimes(1);
    fireEvent.pointerDown(sep);
    expect(resize.onPointerDown).toHaveBeenCalledTimes(1);
  });
});
