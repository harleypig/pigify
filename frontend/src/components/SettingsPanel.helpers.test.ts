import { describe, expect, it } from "vitest";
import { formatRelative, tierClass, tierLabel } from "./SettingsPanel.helpers";

describe("tierLabel", () => {
  it("maps known tiers to their labels", () => {
    expect(tierLabel("authenticated")).toBe("Connected");
    expect(tierLabel("public")).toBe("Public access only");
  });

  it("falls back to Unavailable for unknown tiers", () => {
    expect(tierLabel("none")).toBe("Unavailable");
    expect(tierLabel("")).toBe("Unavailable");
  });
});

describe("tierClass", () => {
  it("maps known tiers to their CSS classes", () => {
    expect(tierClass("authenticated")).toBe("tier-ok");
    expect(tierClass("public")).toBe("tier-public");
  });

  it("falls back to tier-none for unknown tiers", () => {
    expect(tierClass("whatever")).toBe("tier-none");
  });
});

describe("formatRelative", () => {
  const now = Date.parse("2026-06-08T12:00:00Z");

  it("returns the em dash for missing or invalid input", () => {
    expect(formatRelative(null, now)).toBe("—");
    expect(formatRelative(undefined, now)).toBe("—");
    expect(formatRelative("not a date", now)).toBe("—");
  });

  it("renders seconds for sub-minute differences", () => {
    const iso = new Date(now - 30_000).toISOString();
    expect(formatRelative(iso, now)).toBe("30s ago");
  });

  it("renders minutes under an hour", () => {
    const iso = new Date(now - 5 * 60_000).toISOString();
    expect(formatRelative(iso, now)).toBe("5m ago");
  });

  it("renders hours under a day", () => {
    const iso = new Date(now - 3 * 3_600_000).toISOString();
    expect(formatRelative(iso, now)).toBe("3h ago");
  });

  it("renders a full locale string past a day", () => {
    const iso = new Date(now - 2 * 86_400_000).toISOString();
    const out = formatRelative(iso, now);
    expect(out).not.toMatch(/ago$/);
    expect(out.length).toBeGreaterThan(0);
  });
});
