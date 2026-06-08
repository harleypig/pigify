import { describe, expect, it } from "vitest";
import {
  escapeHtml,
  formatDuration,
  highlightJson,
} from "./TrackInfoPanel.helpers";

describe("formatDuration", () => {
  it("renders 0/undefined as an empty (unknown) string", () => {
    expect(formatDuration()).toBe("");
    expect(formatDuration(0)).toBe("");
  });

  it("rounds to the nearest second and zero-pads", () => {
    expect(formatDuration(5_400)).toBe("0:05");
    expect(formatDuration(5_600)).toBe("0:06");
    expect(formatDuration(65_000)).toBe("1:05");
  });

  it("formats multi-minute durations", () => {
    expect(formatDuration(185_000)).toBe("3:05");
  });
});

describe("escapeHtml", () => {
  it("escapes the three HTML-significant characters", () => {
    expect(escapeHtml('<a href="x">&')).toBe('&lt;a href="x"&gt;&amp;');
  });

  it("escapes ampersands before angle brackets (no double-escape)", () => {
    expect(escapeHtml("a & b < c")).toBe("a &amp; b &lt; c");
  });
});

describe("highlightJson", () => {
  it("wraps keys, strings, numbers, booleans and null in classed spans", () => {
    const html = highlightJson({ a: "hi", b: 3, c: true, d: null });
    expect(html).toContain('<span class="tip-json-key">"a"</span>:');
    expect(html).toContain('<span class="tip-json-string">"hi"</span>');
    expect(html).toContain('<span class="tip-json-number">3</span>');
    expect(html).toContain('<span class="tip-json-bool">true</span>');
    expect(html).toContain('<span class="tip-json-null">null</span>');
  });

  it("escapes HTML inside string values", () => {
    const html = highlightJson({ x: "<script>" });
    expect(html).toContain("&lt;script&gt;");
    expect(html).not.toContain("<script>");
  });
});
