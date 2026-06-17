// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  flipTheme,
  OWNER_THEME_DEFAULT,
  resolveOwnerDefault,
} from "./ownerTheme";

describe("flipTheme", () => {
  it("swaps dark and light", () => {
    expect(flipTheme("dark")).toBe("light");
    expect(flipTheme("light")).toBe("dark");
  });
});

describe("resolveOwnerDefault", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("follows the OS preference when the owner default is 'system'", () => {
    // The shipped default is "system"; this documents the dependency so a
    // future owner change to a forced theme is a deliberate, visible edit.
    expect(OWNER_THEME_DEFAULT).toBe("system");

    vi.stubGlobal("matchMedia", (q: string) => ({
      matches: q.includes("dark"),
    }));
    expect(resolveOwnerDefault()).toBe("dark");

    vi.stubGlobal("matchMedia", () => ({ matches: false }));
    expect(resolveOwnerDefault()).toBe("light");
  });
});
