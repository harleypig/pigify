// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// HeartButton writes through apiService.loveTrack/unloveTrack and (when no
// initial state is provided) reads aggregate state with checkFavorites.
const checkFavorites = vi.fn();
const loveTrack = vi.fn();
const unloveTrack = vi.fn();
vi.mock("../services/api", () => ({
  apiService: {
    checkFavorites: (...a: unknown[]) => checkFavorites(...a),
    loveTrack: (...a: unknown[]) => loveTrack(...a),
    unloveTrack: (...a: unknown[]) => unloveTrack(...a),
  },
}));

import HeartButton from "./HeartButton";

const track = {
  spotify_id: "abc123",
  name: "Song",
  artist: "Artist",
};

describe("HeartButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    checkFavorites.mockResolvedValue([{ sources: { spotify: null } }]);
    loveTrack.mockResolvedValue({
      results: [{ service: "spotify", ok: true, skipped: false }],
    });
    unloveTrack.mockResolvedValue({
      results: [{ service: "spotify", ok: true, skipped: false }],
    });
  });

  it("renders an unloved toggle when not initially loved", () => {
    render(<HeartButton track={track} initialSpotifyLoved={false} />);

    const btn = screen.getByRole("button", { name: "Love track" });
    expect(btn).toBeInTheDocument();
    expect(btn).toHaveAttribute("aria-pressed", "false");
  });

  it("reflects the loved state passed via initialSpotifyLoved", () => {
    render(<HeartButton track={track} initialSpotifyLoved={true} />);

    const btn = screen.getByRole("button", { name: "Unlove track" });
    expect(btn).toHaveAttribute("aria-pressed", "true");
  });

  it("calls loveTrack and flips to loved on click when unloved", async () => {
    const onChange = vi.fn();
    render(
      <HeartButton
        track={track}
        initialSpotifyLoved={false}
        onChange={onChange}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Love track" }));

    expect(loveTrack).toHaveBeenCalledWith(track);
    expect(unloveTrack).not.toHaveBeenCalled();
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Unlove track" }),
      ).toBeInTheDocument(),
    );
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("calls unloveTrack when already loved", async () => {
    render(
      <HeartButton
        track={track}
        initialSpotifyLoved={true}
        initialLastfmLoved={null}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Unlove track" }));

    expect(unloveTrack).toHaveBeenCalledWith(track);
    expect(loveTrack).not.toHaveBeenCalled();
  });

  it("queries checkFavorites once when no initial state is given", async () => {
    render(<HeartButton track={track} />);

    await waitFor(() => expect(checkFavorites).toHaveBeenCalledTimes(1));
  });

  it("is disabled when the track has no name or artist", () => {
    render(
      <HeartButton
        track={{ name: "", artist: "" }}
        initialSpotifyLoved={false}
      />,
    );

    expect(screen.getByRole("button")).toBeDisabled();
  });
});
