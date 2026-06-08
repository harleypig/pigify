// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const getPlaylists = vi.fn();
vi.mock("../services/api", () => ({
  apiService: {
    getPlaylists: (...a: unknown[]) => getPlaylists(...a),
  },
}));

import PlaylistSelector from "./PlaylistSelector";

const playlist = {
  id: "pl1",
  name: "Road Trip",
  description: "",
  images: [],
  owner: "me",
  track_count: 12,
  public: false,
};

describe("PlaylistSelector", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the loaded playlists", async () => {
    getPlaylists.mockResolvedValue([playlist]);

    render(
      <PlaylistSelector onSelectPlaylist={vi.fn()} selectedPlaylist={null} />,
    );

    expect(await screen.findByText("Road Trip")).toBeInTheDocument();
    expect(screen.getByText("12 tracks")).toBeInTheDocument();
  });

  it("calls onSelectPlaylist with the playlist id when clicked", async () => {
    getPlaylists.mockResolvedValue([playlist]);
    const onSelectPlaylist = vi.fn();

    render(
      <PlaylistSelector
        onSelectPlaylist={onSelectPlaylist}
        selectedPlaylist={null}
      />,
    );

    await userEvent.click(await screen.findByText("Road Trip"));

    expect(onSelectPlaylist).toHaveBeenCalledWith("pl1");
  });

  it("shows an error state when loading fails", async () => {
    getPlaylists.mockRejectedValue(new Error("boom"));

    render(
      <PlaylistSelector onSelectPlaylist={vi.fn()} selectedPlaylist={null} />,
    );

    expect(
      await screen.findByText("Failed to load playlists"),
    ).toBeInTheDocument();
  });

  it("renders an empty list without throwing", async () => {
    getPlaylists.mockResolvedValue([]);

    render(
      <PlaylistSelector onSelectPlaylist={vi.fn()} selectedPlaylist={null} />,
    );

    await waitFor(() => expect(getPlaylists).toHaveBeenCalled());
    expect(screen.getByText("Your Playlists")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
