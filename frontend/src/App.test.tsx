// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock the API client so App's mount-time auth check is controllable and no
// real HTTP happens. getCurrentUser drives the auth branch; logout is asserted
// against. Every other method resolves to a harmless empty default via a Proxy
// so the authenticated tree renders without real network calls.
const getCurrentUser = vi.fn();
const logout = vi.fn();
vi.mock("./services/api", () => {
  const overrides: Record<string, unknown> = {
    getCurrentUser: (...a: unknown[]) => getCurrentUser(...a),
    logout: (...a: unknown[]) => logout(...a),
    getProfile: vi.fn().mockResolvedValue(null),
    getPlaybackState: vi.fn().mockResolvedValue(null),
    getLastfmStatus: vi.fn().mockResolvedValue({ status: { queued: 0 } }),
    getLastfmQueue: vi.fn().mockResolvedValue({ entries: [] }),
    getAccessToken: vi.fn().mockResolvedValue("tok"),
  };
  return {
    apiService: new Proxy(overrides, {
      get(target, prop: string) {
        if (prop in target) return target[prop];
        // Default for everything else: a resolved empty-array call, which
        // covers the various list fetches the authenticated tree makes.
        return vi.fn().mockResolvedValue([]);
      },
    }),
  };
});

// The Web Playback SDK connect is a no-op in tests.
vi.mock("./services/spotify", () => ({
  spotifyService: { connect: vi.fn().mockResolvedValue(undefined) },
}));

import App from "./App";

describe("App (mount smoke)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it("mounts and shows the Login screen when not authenticated", async () => {
    getCurrentUser.mockRejectedValue(new Error("401"));

    render(<App />);

    // App rendered under React 19 + jsdom, ran its mount-time auth check,
    // and fell back to the login screen.
    expect(await screen.findByText("Connect Spotify")).toBeInTheDocument();
    expect(getCurrentUser).toHaveBeenCalled();
  });

  it("returns to the login screen on logout even if the API call fails", async () => {
    getCurrentUser.mockResolvedValue({
      id: "u1",
      display_name: "Tester",
      images: [],
    });
    // The server-side logout call fails — the user must still be logged out
    // of the UI (regression test for the logout-traps-you-in-the-app bug).
    logout.mockRejectedValue(new Error("logout failed"));

    render(<App />);

    const trigger = await screen.findByRole("button", { name: /Tester/ });
    await userEvent.click(trigger);
    await userEvent.click(screen.getByRole("menuitem", { name: "Logout" }));

    expect(await screen.findByText("Connect Spotify")).toBeInTheDocument();
  });
});
