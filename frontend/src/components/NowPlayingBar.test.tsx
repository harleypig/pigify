// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// NowPlayingBar talks to the backend through apiService: it polls
// getPlaybackState, drives transport with play/pause/next/previous/seek, and
// fetches the waveform via getAudioAnalysis. The embedded HeartButton also
// reads aggregate loved state via checkFavorites. Mock the whole service so
// no real HTTP happens (jsdom has no backend, no Web Playback SDK).
const getPlaybackState = vi.fn();
const playTrack = vi.fn();
const pausePlayback = vi.fn();
const nextTrack = vi.fn();
const previousTrack = vi.fn();
const seekTo = vi.fn();
const getAudioAnalysis = vi.fn();
const checkFavorites = vi.fn();
vi.mock("../services/api", () => ({
  apiService: {
    getPlaybackState: (...a: unknown[]) => getPlaybackState(...a),
    playTrack: (...a: unknown[]) => playTrack(...a),
    pausePlayback: (...a: unknown[]) => pausePlayback(...a),
    nextTrack: (...a: unknown[]) => nextTrack(...a),
    previousTrack: (...a: unknown[]) => previousTrack(...a),
    seekTo: (...a: unknown[]) => seekTo(...a),
    getAudioAnalysis: (...a: unknown[]) => getAudioAnalysis(...a),
    checkFavorites: (...a: unknown[]) => checkFavorites(...a),
  },
}));

import NowPlayingBar from "./NowPlayingBar";

// A playback-state payload shaped like Spotify's /api/player/state response.
const playbackState = (playing: boolean) => ({
  item: {
    id: "track-1",
    uri: "spotify:track:track-1",
    name: "Test Track",
    duration_ms: 200000,
    artists: [{ name: "First Artist" }, { name: "Second Artist" }],
    album: {
      name: "Test Album",
      images: [{ url: "http://img/cover.jpg" }],
    },
  },
  is_playing: playing,
  progress_ms: 50000,
});

describe("NowPlayingBar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getPlaybackState.mockResolvedValue(null);
    playTrack.mockResolvedValue(undefined);
    pausePlayback.mockResolvedValue(undefined);
    nextTrack.mockResolvedValue(undefined);
    previousTrack.mockResolvedValue(undefined);
    seekTo.mockResolvedValue(undefined);
    getAudioAnalysis.mockResolvedValue({ bars: [], duration: 200 });
    // HeartButton has its own initial state passed in, so checkFavorites is
    // not strictly needed, but default it to a benign value just in case.
    checkFavorites.mockResolvedValue([{ sources: { spotify: null } }]);
  });

  it("checks loved state by the original id when the track is relinked", async () => {
    // Spotify relinks popular tracks for the user's market: the top-level id
    // is the relinked (playable) track, while linked_from carries the
    // original. Library ops (the loved-state check, save/unsave) must use the
    // original id — otherwise the saved-tracks check misses and the heart
    // reads as unloved. Regression for that bug.
    getPlaybackState.mockResolvedValue({
      item: {
        id: "relinked-id",
        uri: "spotify:track:relinked-id",
        name: "Popular Song",
        duration_ms: 200000,
        artists: [{ name: "Famous Artist" }],
        album: { name: "Album", images: [{ url: "http://img/c.jpg" }] },
        linked_from: {
          id: "original-id",
          uri: "spotify:track:original-id",
        },
      },
      is_playing: false,
      progress_ms: 0,
    });

    render(<NowPlayingBar trackUri={null} />);

    await waitFor(() =>
      expect(checkFavorites).toHaveBeenCalledWith([
        expect.objectContaining({ track_id: "original-id" }),
      ]),
    );
  });

  it("plays the provided trackUri on mount", async () => {
    render(<NowPlayingBar trackUri="spotify:track:abc" />);

    await waitFor(() =>
      expect(playTrack).toHaveBeenCalledWith("spotify:track:abc"),
    );
  });

  it("renders the idle state when no track is playing", async () => {
    // getPlaybackState defaults to null, so the bar stays empty.
    render(<NowPlayingBar trackUri={null} />);

    expect(await screen.findByText("Nothing playing")).toBeInTheDocument();
    // Transport controls are disabled while there is no track.
    expect(screen.getByRole("button", { name: "Play" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
  });

  it("renders the current track title, artists, and album art once state arrives", async () => {
    getPlaybackState.mockResolvedValue(playbackState(false));

    render(<NowPlayingBar trackUri={null} />);

    expect(await screen.findByText("Test Track")).toBeInTheDocument();
    expect(screen.getByText("First Artist, Second Artist")).toBeInTheDocument();
    // alt is intentionally empty (name is shown as text), so query by src.
    const art = document.querySelector<HTMLImageElement>(".now-playing-art");
    expect(art).not.toBeNull();
    expect(art?.src).toBe("http://img/cover.jpg");
  });

  it("shows a Pause control while playing and pauses when clicked", async () => {
    getPlaybackState.mockResolvedValue(playbackState(true));

    render(<NowPlayingBar trackUri={null} />);

    const btn = await screen.findByRole("button", { name: "Pause" });
    await userEvent.click(btn);

    expect(pausePlayback).toHaveBeenCalledTimes(1);
    expect(playTrack).not.toHaveBeenCalled();
  });

  it("shows a Play control while paused and resumes when clicked", async () => {
    getPlaybackState.mockResolvedValue(playbackState(false));

    render(<NowPlayingBar trackUri={null} />);

    const btn = await screen.findByRole("button", { name: "Play" });
    await userEvent.click(btn);

    // Resume calls playTrack() with no uri.
    await waitFor(() => expect(playTrack).toHaveBeenCalledTimes(1));
    expect(playTrack).toHaveBeenCalledWith();
  });

  it("invokes nextTrack and previousTrack from the transport controls", async () => {
    getPlaybackState.mockResolvedValue(playbackState(false));

    render(<NowPlayingBar trackUri={null} />);

    await userEvent.click(await screen.findByRole("button", { name: "Next" }));
    await userEvent.click(screen.getByRole("button", { name: "Previous" }));

    expect(nextTrack).toHaveBeenCalledTimes(1);
    expect(previousTrack).toHaveBeenCalledTimes(1);
  });

  it("fires onShowDetails when the info button is clicked", async () => {
    getPlaybackState.mockResolvedValue(playbackState(false));
    const onShowDetails = vi.fn();

    render(<NowPlayingBar trackUri={null} onShowDetails={onShowDetails} />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Show track info panel" }),
    );

    expect(onShowDetails).toHaveBeenCalledTimes(1);
  });

  it("notifies onTrackChange with the now-playing track id", async () => {
    getPlaybackState.mockResolvedValue(playbackState(false));
    const onTrackChange = vi.fn();

    render(<NowPlayingBar trackUri={null} onTrackChange={onTrackChange} />);

    // The effect fires with null on first render, then with the track id once
    // playback state lands.
    await waitFor(() => expect(onTrackChange).toHaveBeenCalledWith("track-1"));
  });

  it("seeks via the native range input when there is no waveform", async () => {
    // No waveform -> the plain track + <input type=range> seek control renders.
    getPlaybackState.mockResolvedValue(playbackState(false));
    getAudioAnalysis.mockResolvedValue({ bars: [], duration: 200 });

    render(<NowPlayingBar trackUri={null} />);

    const slider = await screen.findByRole("slider", { name: "Seek" });
    // Drive the range to its midpoint (max=1000 -> fraction 0.5 of 200000ms).
    // fireEvent.change is the reliable way to set a native <input type=range>
    // value in jsdom; userEvent can't drag a slider here.
    fireEvent.change(slider, { target: { value: "500" } });

    await waitFor(() => expect(seekTo).toHaveBeenCalledTimes(1));
    expect(seekTo).toHaveBeenCalledWith(100000);
  });

  it("renders the waveform without throwing when analysis returns bars", async () => {
    getPlaybackState.mockResolvedValue(playbackState(false));
    getAudioAnalysis.mockResolvedValue({
      bars: [0.2, 0.5, 0.8, 0.5, 0.2],
      duration: 200,
    });

    render(<NowPlayingBar trackUri={null} />);

    // Title confirms the bar mounted; the SVG waveform replaces the range.
    await screen.findByText("Test Track");
    await waitFor(() => {
      expect(document.querySelector(".progress-waveform")).not.toBeNull();
    });
    expect(getAudioAnalysis).toHaveBeenCalledWith("track-1");
    // No native slider while the waveform is shown.
    expect(screen.queryByRole("slider", { name: "Seek" })).toBeNull();
  });
});
