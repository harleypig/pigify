// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import {
  evaluateScrobbleAlert,
  pickAvatarUrl,
  readDismissed,
  SCROBBLE_DISMISS_KEY,
  SCROBBLE_STALE_MS,
  scrobbleBadgeTitle,
} from "./App.helpers";

describe("pickAvatarUrl", () => {
  it("returns null for missing or empty image lists", () => {
    expect(pickAvatarUrl()).toBeNull();
    expect(pickAvatarUrl(null)).toBeNull();
    expect(pickAvatarUrl([])).toBeNull();
  });

  it("picks the smallest image by height", () => {
    const url = pickAvatarUrl([
      { url: "big", height: 640 },
      { url: "small", height: 64 },
      { url: "mid", height: 300 },
    ]);
    expect(url).toBe("small");
  });

  it("falls back to the last image when no heights are present", () => {
    const url = pickAvatarUrl([{ url: "a" }, { url: "b" }, { url: "c" }]);
    expect(url).toBe("c");
  });

  it("ignores unsized images when at least one is sized", () => {
    const url = pickAvatarUrl([
      { url: "unsized" },
      { url: "sized", height: 100 },
    ]);
    expect(url).toBe("sized");
  });
});

describe("readDismissed", () => {
  afterEach(() => {
    localStorage.clear();
  });

  it("returns null when nothing is stored", () => {
    expect(readDismissed()).toBeNull();
  });

  it("returns null for malformed JSON", () => {
    localStorage.setItem(SCROBBLE_DISMISS_KEY, "{not json");
    expect(readDismissed()).toBeNull();
  });

  it("returns null when the shape is invalid", () => {
    localStorage.setItem(SCROBBLE_DISMISS_KEY, JSON.stringify({ queued: "5" }));
    expect(readDismissed()).toBeNull();
  });

  it("round-trips a valid snapshot", () => {
    const snapshot = { queued: 3, oldestQueuedAt: "2026-01-01T00:00:00Z" };
    localStorage.setItem(SCROBBLE_DISMISS_KEY, JSON.stringify(snapshot));
    expect(readDismissed()).toEqual(snapshot);
  });

  it("accepts a null oldestQueuedAt", () => {
    const snapshot = { queued: 0, oldestQueuedAt: null };
    localStorage.setItem(SCROBBLE_DISMISS_KEY, JSON.stringify(snapshot));
    expect(readDismissed()).toEqual(snapshot);
  });
});

describe("evaluateScrobbleAlert", () => {
  const now = Date.parse("2026-06-08T12:00:00Z");

  it("is not severe and shows no banner with an empty queue", () => {
    const r = evaluateScrobbleAlert(
      { queued: 0, oldestQueuedAt: null },
      null,
      now,
    );
    expect(r).toEqual({
      isStale: false,
      isOverThreshold: false,
      severe: false,
      showBanner: false,
    });
  });

  it("flags over-threshold when more than 5 are queued", () => {
    const r = evaluateScrobbleAlert(
      { queued: 6, oldestQueuedAt: null },
      null,
      now,
    );
    expect(r.isOverThreshold).toBe(true);
    expect(r.severe).toBe(true);
    expect(r.showBanner).toBe(true);
  });

  it("is not over-threshold at exactly 5", () => {
    const r = evaluateScrobbleAlert(
      { queued: 5, oldestQueuedAt: null },
      null,
      now,
    );
    expect(r.isOverThreshold).toBe(false);
    expect(r.severe).toBe(false);
  });

  it("flags stale when the oldest entry exceeds the stale window", () => {
    const oldest = new Date(now - SCROBBLE_STALE_MS - 1000).toISOString();
    const r = evaluateScrobbleAlert(
      { queued: 1, oldestQueuedAt: oldest },
      null,
      now,
    );
    expect(r.isStale).toBe(true);
    expect(r.severe).toBe(true);
  });

  it("is not stale within the stale window", () => {
    const recent = new Date(now - 1000).toISOString();
    const r = evaluateScrobbleAlert(
      { queued: 1, oldestQueuedAt: recent },
      null,
      now,
    );
    expect(r.isStale).toBe(false);
  });

  it("suppresses the banner when the alert matches a prior dismissal", () => {
    const alert = { queued: 6, oldestQueuedAt: null };
    const r = evaluateScrobbleAlert(alert, { ...alert }, now);
    expect(r.severe).toBe(true);
    expect(r.showBanner).toBe(false);
  });

  it("re-shows the banner when the queue grows past the dismissal", () => {
    const r = evaluateScrobbleAlert(
      { queued: 8, oldestQueuedAt: null },
      { queued: 6, oldestQueuedAt: null },
      now,
    );
    expect(r.showBanner).toBe(true);
  });
});

describe("scrobbleBadgeTitle", () => {
  it("returns undefined with nothing queued", () => {
    expect(
      scrobbleBadgeTitle({ queued: 0, oldestQueuedAt: null }, false),
    ).toBeUndefined();
  });

  it("uses the singular form for one queued scrobble", () => {
    const title = scrobbleBadgeTitle(
      { queued: 1, oldestQueuedAt: null },
      false,
    );
    expect(title).toBe("1 pending scrobble — click Settings to review");
  });

  it("uses the plural form for many", () => {
    const title = scrobbleBadgeTitle(
      { queued: 4, oldestQueuedAt: null },
      false,
    );
    expect(title).toBe("4 pending scrobbles — click Settings to review");
  });

  it("adds the stale note when stale", () => {
    const title = scrobbleBadgeTitle({ queued: 4, oldestQueuedAt: null }, true);
    expect(title).toContain("oldest stuck for over 1h");
  });
});
