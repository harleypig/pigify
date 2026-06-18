// @vitest-environment jsdom
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { useResizableWidth } from "./useResizableWidth";

const KEY = "pigify.test.width";

function pointer(x: number) {
  return {
    clientX: x,
    pointerId: 1,
    preventDefault() {},
    currentTarget: {
      setPointerCapture() {},
      releasePointerCapture() {},
    },
  } as unknown as React.PointerEvent;
}

describe("useResizableWidth", () => {
  afterEach(() => localStorage.clear());

  it("starts at the default and persists drag results", () => {
    const { result } = renderHook(() =>
      useResizableWidth({
        storageKey: KEY,
        min: 200,
        max: 600,
        defaultWidth: 300,
      }),
    );
    expect(result.current.width).toBe(300);

    // Drag the right edge +120px → grows to 420, persisted.
    act(() => result.current.onPointerDown(pointer(0)));
    act(() => result.current.onPointerMove(pointer(120)));
    act(() => result.current.onPointerUp(pointer(120)));

    expect(result.current.width).toBe(420);
    expect(localStorage.getItem(KEY)).toBe("420");
  });

  it("clamps to min/max", () => {
    const { result } = renderHook(() =>
      useResizableWidth({
        storageKey: KEY,
        min: 200,
        max: 600,
        defaultWidth: 300,
      }),
    );
    act(() => result.current.onPointerDown(pointer(0)));
    act(() => result.current.onPointerMove(pointer(9999)));
    expect(result.current.width).toBe(600);

    act(() => result.current.onPointerMove(pointer(-9999)));
    expect(result.current.width).toBe(200);
  });

  it("inverts the drag delta for a left-edge handle", () => {
    const { result } = renderHook(() =>
      useResizableWidth({
        storageKey: KEY,
        min: 200,
        max: 600,
        defaultWidth: 300,
        edge: "left",
      }),
    );
    // A right-docked panel grows when its LEFT edge is dragged left (−dx).
    act(() => result.current.onPointerDown(pointer(0)));
    act(() => result.current.onPointerMove(pointer(-80)));
    expect(result.current.width).toBe(380);
  });

  it("restores a clamped stored width", () => {
    localStorage.setItem(KEY, "9999");
    const { result } = renderHook(() =>
      useResizableWidth({
        storageKey: KEY,
        min: 200,
        max: 600,
        defaultWidth: 300,
      }),
    );
    expect(result.current.width).toBe(600);
  });
});
