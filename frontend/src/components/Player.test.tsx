// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Player drives playback through the browser-only Spotify Web Playback SDK
// wrapper; mock it so no real SDK is loaded.
const play = vi.fn();
const pause = vi.fn();
const resume = vi.fn();
const getCurrentState = vi.fn();
vi.mock("../services/spotify", () => ({
  spotifyService: {
    play: (...a: unknown[]) => play(...a),
    pause: (...a: unknown[]) => pause(...a),
    resume: (...a: unknown[]) => resume(...a),
    getCurrentState: (...a: unknown[]) => getCurrentState(...a),
  },
}));

import Player from "./Player";

const stateWithTrack = (paused: boolean) => ({
  paused,
  track_window: {
    current_track: {
      name: "Track Name",
      artists: [{ name: "Artist One" }, { name: "Artist Two" }],
      album: { images: [{ url: "http://img/cover.jpg" }] },
    },
  },
});

describe("Player", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    play.mockResolvedValue(undefined);
    pause.mockResolvedValue(undefined);
    resume.mockResolvedValue(undefined);
    getCurrentState.mockResolvedValue(null);
  });

  it("plays the given track uri on mount and shows the initializing state", async () => {
    render(<Player trackUri="spotify:track:xyz" />);

    await waitFor(() => expect(play).toHaveBeenCalledWith("spotify:track:xyz"));
    expect(screen.getByText("Initializing player…")).toBeInTheDocument();
  });

  it("renders track details once playback state reports a track", async () => {
    getCurrentState.mockResolvedValue(stateWithTrack(false));

    render(<Player trackUri="spotify:track:xyz" />);

    // Player only polls playback state via a 1s interval, so allow more than
    // the default 1s findBy timeout for the first state update to land.
    expect(
      await screen.findByText("Track Name", {}, { timeout: 3000 }),
    ).toBeInTheDocument();
    expect(screen.getByText("Artist One, Artist Two")).toBeInTheDocument();
  });

  it("pauses when the play/pause control is clicked while playing", async () => {
    getCurrentState.mockResolvedValue(stateWithTrack(false));

    render(<Player trackUri="spotify:track:xyz" />);

    const btn = await screen.findByRole(
      "button",
      { name: "Pause" },
      { timeout: 3000 },
    );
    await userEvent.click(btn);

    expect(pause).toHaveBeenCalledTimes(1);
  });
});
