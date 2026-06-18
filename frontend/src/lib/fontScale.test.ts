import { describe, expect, it } from "vitest";
import { adjustFontScale, FONT_MAX, FONT_MIN, FONT_STEP } from "./fontScale";

describe("adjustFontScale", () => {
  it("applies a step and rounds to one decimal", () => {
    expect(adjustFontScale(1, FONT_STEP)).toBe(1.1);
    expect(adjustFontScale(1, -FONT_STEP)).toBe(0.9);
  });

  it("clamps to the shared bounds", () => {
    expect(adjustFontScale(FONT_MAX, FONT_STEP)).toBe(FONT_MAX);
    expect(adjustFontScale(FONT_MIN, -FONT_STEP)).toBe(FONT_MIN);
  });

  it("clamps an out-of-range starting value (delta 0)", () => {
    expect(adjustFontScale(99, 0)).toBe(FONT_MAX);
    expect(adjustFontScale(0, 0)).toBe(FONT_MIN);
  });
});
