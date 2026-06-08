import { describe, expect, it } from "vitest";
import { getInitials } from "./UserMenu.helpers";

describe("getInitials", () => {
  it("returns ? for empty or whitespace-only labels", () => {
    expect(getInitials("")).toBe("?");
    expect(getInitials("   ")).toBe("?");
  });

  it("uses the first two letters of a single word", () => {
    expect(getInitials("pig")).toBe("PI");
    expect(getInitials("x")).toBe("X");
  });

  it("uses first + last initial for multi-word labels", () => {
    expect(getInitials("Alan Young")).toBe("AY");
    expect(getInitials("a b c")).toBe("AC");
  });

  it("collapses extra whitespace between words", () => {
    expect(getInitials("  Alan   Young  ")).toBe("AY");
  });
});
