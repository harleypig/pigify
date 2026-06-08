// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock the API client so App's mount-time auth check is controllable and no
// real HTTP happens. getCurrentUser drives the auth branch.
const getCurrentUser = vi.fn();
vi.mock("./services/api", () => ({
  apiService: {
    getCurrentUser: (...a: unknown[]) => getCurrentUser(...a),
    getProfile: vi.fn().mockResolvedValue(null),
    getLastfmStatus: vi.fn().mockResolvedValue({ connected: false }),
    getLastfmQueue: vi.fn().mockResolvedValue({ queued: 0, oldest: null }),
    logout: vi.fn().mockResolvedValue(undefined),
  },
}));

import App from "./App";

describe("App (mount smoke)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("mounts and shows the Login screen when not authenticated", async () => {
    getCurrentUser.mockRejectedValue(new Error("401"));

    render(<App />);

    // App rendered under React 19 + jsdom, ran its mount-time auth check,
    // and fell back to the login screen.
    expect(await screen.findByText("Login with Spotify")).toBeInTheDocument();
    expect(getCurrentUser).toHaveBeenCalled();
  });
});
