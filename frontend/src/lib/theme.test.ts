import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  isThemeChoice,
  readStoredChoice,
  resolveTheme,
  THEME_CHOICES,
  themeChoiceLabel,
} from "./theme";

describe("isThemeChoice", () => {
  it("accepts the known choices and rejects anything else", () => {
    expect(isThemeChoice("system")).toBe(true);
    expect(isThemeChoice("dark")).toBe(true);
    expect(isThemeChoice("light")).toBe(true);
    expect(isThemeChoice("sepia")).toBe(false);
    expect(isThemeChoice(null)).toBe(false);
    expect(isThemeChoice(undefined)).toBe(false);
  });
});

describe("readStoredChoice", () => {
  it("returns the stored choice when valid", () => {
    expect(readStoredChoice(() => "light")).toBe("light");
  });

  it("falls back to 'system' when absent or invalid", () => {
    expect(readStoredChoice(() => null)).toBe("system");
    expect(readStoredChoice(() => "bogus")).toBe("system");
  });
});

describe("resolveTheme", () => {
  it("maps 'system' to dark/light by the OS preference", () => {
    expect(resolveTheme("system", true)).toBe("dark");
    expect(resolveTheme("system", false)).toBe("light");
  });

  it("returns an explicit choice unchanged regardless of OS", () => {
    expect(resolveTheme("dark", false)).toBe("dark");
    expect(resolveTheme("light", true)).toBe("light");
  });
});

describe("themeChoiceLabel", () => {
  it("gives a human label for every choice", () => {
    expect(THEME_CHOICES.map(themeChoiceLabel)).toEqual([
      "System",
      "Dark",
      "Light",
    ]);
  });
});

// Contract parity: every built-in theme must define exactly the same
// `--brand-*` token set, so switching themes never leaves a token undefined.
describe("theme contract parity", () => {
  const tokens = (file: string): Set<string> => {
    const css = readFileSync(
      new URL(`../themes/${file}`, import.meta.url),
      "utf-8",
    );
    return new Set([...css.matchAll(/--brand-([\w-]+)\s*:/g)].map((m) => m[1]));
  };

  it("dark.css and light.css define the same tokens", () => {
    const dark = tokens("dark.css");
    const light = tokens("light.css");
    expect(dark.size).toBeGreaterThan(20);
    expect([...dark].sort()).toEqual([...light].sort());
  });
});
