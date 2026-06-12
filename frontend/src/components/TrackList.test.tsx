// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Track } from "../services/api";

// TrackList loads its data through apiService and composes HeartButton, which
// also reaches for apiService.checkFavorites. Mock the whole API module so no
// network client is loaded and every call resolves deterministically.
const getSortFields = vi.fn();
const listSortPresets = vi.fn();
const getAllPlaylistTracks = vi.fn();
const checkFavorites = vi.fn();
const getUndoStatus = vi.fn();
const getPlaylist = vi.fn();
vi.mock("../services/api", () => ({
  apiService: {
    getSortFields: (...a: unknown[]) => getSortFields(...a),
    listSortPresets: (...a: unknown[]) => listSortPresets(...a),
    getAllPlaylistTracks: (...a: unknown[]) => getAllPlaylistTracks(...a),
    checkFavorites: (...a: unknown[]) => checkFavorites(...a),
    getUndoStatus: (...a: unknown[]) => getUndoStatus(...a),
    getPlaylist: (...a: unknown[]) => getPlaylist(...a),
  },
}));

import TrackList from "./TrackList";

const track = (over: Partial<Track> = {}): Track => ({
  id: "id1",
  name: "Song One",
  artists: ["Artist One"],
  album: "Album One",
  duration_ms: 200000,
  uri: "spotify:track:id1",
  image_url: "http://img/one.jpg",
  explicit: false,
  ...over,
});

const TRACKS: Track[] = [
  track(),
  track({
    id: "id2",
    name: "Song Two",
    artists: ["Artist Two"],
    album: "Album Two",
    uri: "spotify:track:id2",
    image_url: "",
  }),
];

describe("TrackList", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Sort metadata is loaded once on mount; keep it empty so no hydration or
    // sorting transforms run (the rows render in load order).
    getSortFields.mockResolvedValue({ fields: [] });
    listSortPresets.mockResolvedValue([]);
    getUndoStatus.mockResolvedValue({ available: false, applied_at: null });
    getPlaylist.mockResolvedValue({
      id: "pl1",
      name: "My Playlist",
      description: "",
      images: [],
    });
    // Loved state per track — supplied so HeartButton does not fetch again.
    checkFavorites.mockResolvedValue([
      { sources: { spotify: false, lastfm: null } },
      { sources: { spotify: false, lastfm: null } },
    ]);
  });

  it("shows the loading state before tracks resolve", () => {
    // Never-resolving promise keeps the component in its initial loading state.
    getAllPlaylistTracks.mockReturnValue(new Promise(() => {}));

    render(<TrackList playlistId="pl1" onTrackSelect={vi.fn()} />);

    expect(screen.getByText("Loading tracks…")).toBeInTheDocument();
  });

  it("renders a row per track from the loaded data", async () => {
    getAllPlaylistTracks.mockResolvedValue(TRACKS);

    render(<TrackList playlistId="pl1" onTrackSelect={vi.fn()} />);

    expect(await screen.findByText("Song One")).toBeInTheDocument();
    expect(screen.getByText("Song Two")).toBeInTheDocument();
    expect(getAllPlaylistTracks).toHaveBeenCalledWith("pl1");
    // Header track count reflects the loaded rows.
    expect(screen.getByText("2 tracks")).toBeInTheDocument();
  });

  it("shows the playlist name as the header", async () => {
    getAllPlaylistTracks.mockResolvedValue(TRACKS);

    render(<TrackList playlistId="pl1" onTrackSelect={vi.fn()} />);

    expect(
      await screen.findByRole("heading", { name: "My Playlist" }),
    ).toBeInTheDocument();
  });

  it("renders an empty track list when the playlist has no tracks", async () => {
    getAllPlaylistTracks.mockResolvedValue([]);

    render(<TrackList playlistId="pl1" onTrackSelect={vi.fn()} />);

    expect(await screen.findByText("0 tracks")).toBeInTheDocument();
    expect(screen.queryByText("Song One")).not.toBeInTheDocument();
  });

  it("shows the error state when loading tracks fails", async () => {
    getAllPlaylistTracks.mockRejectedValue(new Error("boom"));

    render(<TrackList playlistId="pl1" onTrackSelect={vi.fn()} />);

    expect(
      await screen.findByText("Failed to load tracks"),
    ).toBeInTheDocument();
  });

  it("plays and focuses a track when its name is clicked", async () => {
    getAllPlaylistTracks.mockResolvedValue(TRACKS);
    const onTrackSelect = vi.fn();
    const onTrackFocus = vi.fn();

    render(
      <TrackList
        playlistId="pl1"
        onTrackSelect={onTrackSelect}
        onTrackFocus={onTrackFocus}
      />,
    );

    const name = await screen.findByRole("button", { name: "Song One" });
    await userEvent.click(name);

    expect(onTrackSelect).toHaveBeenCalledWith("spotify:track:id1");
    expect(onTrackFocus).toHaveBeenCalledWith("id1");
  });

  it("selects a row on a plain body click without playing", async () => {
    getAllPlaylistTracks.mockResolvedValue(TRACKS);
    const onTrackSelect = vi.fn();

    render(<TrackList playlistId="pl1" onTrackSelect={onTrackSelect} />);

    // Click the artists cell (row body, not the name button) — this should
    // select the row, not start playback.
    const row = (await screen.findByText("Artist One")).closest(".track-item");
    await userEvent.click(row as Element);

    expect(row).toHaveClass("selected");
    expect(onTrackSelect).not.toHaveBeenCalled();
  });

  it("opens the track info panel on right-click of the name", async () => {
    getAllPlaylistTracks.mockResolvedValue(TRACKS);
    const onTrackSelect = vi.fn();
    const onTrackFocus = vi.fn();

    render(
      <TrackList
        playlistId="pl1"
        onTrackSelect={onTrackSelect}
        onTrackFocus={onTrackFocus}
      />,
    );

    const name = await screen.findByRole("button", { name: "Song One" });
    fireEvent.contextMenu(name);

    expect(onTrackFocus).toHaveBeenCalledWith("id1");
    expect(onTrackSelect).not.toHaveBeenCalled();
  });
});
