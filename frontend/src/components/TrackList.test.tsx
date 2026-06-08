// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";

// TrackList cannot be rendered in a unit test as-is: its load effect lists
// the (non-memoized) `loadTracks` / `refreshUndoStatus` callbacks in its
// dependency array, and `loadTracks` calls `setLoading(true)` synchronously.
// So every render schedules a state update that triggers another render —
// an unbounded loop that OOMs the test worker, regardless of how the mocked
// API promises resolve. In the running app only network latency throttles
// this; under jsdom with no real I/O it spins forever.
//
// Per the testing brief, this is reduced to a module-level smoke test that
// confirms the component imports cleanly and is a renderable function.
// Behavioral coverage (rendering rows, row-click selection, error state)
// requires refactoring the component's effect dependencies first — noted in
// the test report. The collaborating units it composes — SortMenu and
// HeartButton — are covered directly in their own test files.

// Stub the API + child-component side modules so importing TrackList pulls
// in no network client or browser-only code.
vi.mock("../services/api", () => ({ apiService: {} }));

import TrackList from "./TrackList";

describe("TrackList (import smoke)", () => {
  it("imports without throwing and exports a component function", () => {
    expect(typeof TrackList).toBe("function");
  });
});
